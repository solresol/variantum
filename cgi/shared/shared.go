package shared

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

const defaultDBPath = "/vhosts/parallage.symmachus.org/db/reviews.db"

func DBPath() string {
	if value := os.Getenv("PARALLAGE_REVIEW_DB"); value != "" {
		return value
	}
	return defaultDBPath
}

func OpenDB() (*sql.DB, error) {
	dsn := fmt.Sprintf("file:%s?_busy_timeout=5000&_journal_mode=WAL", DBPath())
	db, err := sql.Open("sqlite3", dsn)
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec("PRAGMA foreign_keys = ON"); err != nil {
		_ = db.Close()
		return nil, err
	}
	if err := EnsureSchema(db); err != nil {
		_ = db.Close()
		return nil, err
	}
	return db, nil
}

func EnsureSchema(db *sql.DB) error {
	_, err := db.Exec(`
CREATE TABLE IF NOT EXISTS review_batches (
    pack_slug TEXT PRIMARY KEY,
    source_corpus TEXT NOT NULL DEFAULT 'stephanos',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variant_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_slug TEXT NOT NULL,
    passage_id INTEGER NOT NULL,
    variant_id TEXT NOT NULL,
    reviewer_username TEXT NOT NULL,
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
    most_trusted INTEGER NOT NULL DEFAULT 0 CHECK (most_trusted IN (0, 1)),
    least_trusted INTEGER NOT NULL DEFAULT 0 CHECK (least_trusted IN (0, 1)),
    notes TEXT NOT NULL DEFAULT '',
    exposure_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_pack_passage
    ON variant_ratings (pack_slug, passage_id);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_reviewer
    ON variant_ratings (reviewer_username, pack_slug);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_latest
    ON variant_ratings (pack_slug, passage_id, reviewer_username, variant_id, id);
`)
	if err != nil {
		return err
	}
	if err := ensureVariantRatingsScale(db); err != nil {
		return err
	}
	if err := ensureVariantRatingsExposureColumn(db); err != nil {
		return err
	}
	return ensureVariantRatingsAppendOnly(db)
}

func ensureVariantRatingsExposureColumn(db *sql.DB) error {
	rows, err := db.Query(`PRAGMA table_info(variant_ratings)`)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var cid int
		var name string
		var columnType string
		var notNull int
		var defaultValue sql.NullString
		var pk int
		if err := rows.Scan(&cid, &name, &columnType, &notNull, &defaultValue, &pk); err != nil {
			return err
		}
		if name == "exposure_json" {
			return nil
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}
	_, err = db.Exec(`ALTER TABLE variant_ratings ADD COLUMN exposure_json TEXT NOT NULL DEFAULT '{}'`)
	return err
}

func ensureVariantRatingsScale(db *sql.DB) error {
	var createSQL string
	err := db.QueryRow(`
		SELECT sql
		FROM sqlite_master
		WHERE type = 'table'
		  AND name = 'variant_ratings'
	`).Scan(&createSQL)
	if err == sql.ErrNoRows {
		return nil
	}
	if err != nil {
		return err
	}
	if !strings.Contains(createSQL, "BETWEEN -2 AND 2") {
		return nil
	}

	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DROP TABLE IF EXISTS variant_ratings_new`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
CREATE TABLE variant_ratings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_slug TEXT NOT NULL,
    passage_id INTEGER NOT NULL,
    variant_id TEXT NOT NULL,
    reviewer_username TEXT NOT NULL,
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
    most_trusted INTEGER NOT NULL DEFAULT 0 CHECK (most_trusted IN (0, 1)),
    least_trusted INTEGER NOT NULL DEFAULT 0 CHECK (least_trusted IN (0, 1)),
    notes TEXT NOT NULL DEFAULT '',
    exposure_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
INSERT INTO variant_ratings_new (
    id, pack_slug, passage_id, variant_id, reviewer_username,
    rating, most_trusted, least_trusted, notes, exposure_json, created_at, updated_at
)
SELECT
    id, pack_slug, passage_id, variant_id, reviewer_username,
    CASE WHEN rating BETWEEN 0 AND 10 THEN rating ELSE NULL END,
    most_trusted, least_trusted, notes, '{}', created_at, updated_at
FROM variant_ratings;
`); err != nil {
		return err
	}
	if _, err := tx.Exec(`DROP TABLE variant_ratings`); err != nil {
		return err
	}
	if _, err := tx.Exec(`ALTER TABLE variant_ratings_new RENAME TO variant_ratings`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
CREATE INDEX IF NOT EXISTS idx_variant_ratings_pack_passage
    ON variant_ratings (pack_slug, passage_id);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_reviewer
    ON variant_ratings (reviewer_username, pack_slug);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_latest
    ON variant_ratings (pack_slug, passage_id, reviewer_username, variant_id, id);
`); err != nil {
		return err
	}
	return tx.Commit()
}

func ensureVariantRatingsAppendOnly(db *sql.DB) error {
	var createSQL string
	err := db.QueryRow(`
		SELECT sql
		FROM sqlite_master
		WHERE type = 'table'
		  AND name = 'variant_ratings'
	`).Scan(&createSQL)
	if err == sql.ErrNoRows {
		return nil
	}
	if err != nil {
		return err
	}
	if !strings.Contains(createSQL, "UNIQUE (pack_slug, passage_id, variant_id, reviewer_username)") {
		_, err = db.Exec(`
CREATE INDEX IF NOT EXISTS idx_variant_ratings_latest
    ON variant_ratings (pack_slug, passage_id, reviewer_username, variant_id, id);
`)
		return err
	}

	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DROP TABLE IF EXISTS variant_ratings_new`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
CREATE TABLE variant_ratings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_slug TEXT NOT NULL,
    passage_id INTEGER NOT NULL,
    variant_id TEXT NOT NULL,
    reviewer_username TEXT NOT NULL,
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 0 AND 10),
    most_trusted INTEGER NOT NULL DEFAULT 0 CHECK (most_trusted IN (0, 1)),
    least_trusted INTEGER NOT NULL DEFAULT 0 CHECK (least_trusted IN (0, 1)),
    notes TEXT NOT NULL DEFAULT '',
    exposure_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
INSERT INTO variant_ratings_new (
    id, pack_slug, passage_id, variant_id, reviewer_username,
    rating, most_trusted, least_trusted, notes, exposure_json, created_at, updated_at
)
SELECT
    id, pack_slug, passage_id, variant_id, reviewer_username,
    rating, most_trusted, least_trusted, notes, exposure_json, created_at, updated_at
FROM variant_ratings;
`); err != nil {
		return err
	}
	if _, err := tx.Exec(`DROP TABLE variant_ratings`); err != nil {
		return err
	}
	if _, err := tx.Exec(`ALTER TABLE variant_ratings_new RENAME TO variant_ratings`); err != nil {
		return err
	}
	if _, err := tx.Exec(`
CREATE INDEX IF NOT EXISTS idx_variant_ratings_pack_passage
    ON variant_ratings (pack_slug, passage_id);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_reviewer
    ON variant_ratings (reviewer_username, pack_slug);

CREATE INDEX IF NOT EXISTS idx_variant_ratings_latest
    ON variant_ratings (pack_slug, passage_id, reviewer_username, variant_id, id);
`); err != nil {
		return err
	}
	return tx.Commit()
}

func Reviewer(r *http.Request) (string, error) {
	reviewer := strings.TrimSpace(os.Getenv("REMOTE_USER"))
	if reviewer == "" {
		reviewer = strings.TrimSpace(r.Header.Get("Remote-User"))
	}
	if reviewer == "" {
		return "", fmt.Errorf("REMOTE_USER not set; check HTTP auth configuration")
	}
	return reviewer, nil
}

func JSONResponse(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func ErrorResponse(w http.ResponseWriter, status int, message string) {
	JSONResponse(w, status, map[string]string{"error": message})
}

func RequiredInt(r *http.Request, name string) (int, error) {
	raw := strings.TrimSpace(r.FormValue(name))
	if raw == "" {
		return 0, fmt.Errorf("%s is required", name)
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer", name)
	}
	return value, nil
}

func SafeReturnURL(raw string, fallback string) string {
	if strings.HasPrefix(raw, "/review/") && !strings.Contains(raw, "://") {
		return raw
	}
	return fallback
}

func BoolFormValue(r *http.Request, name string) int {
	if r.FormValue(name) == "1" || r.FormValue(name) == "on" {
		return 1
	}
	return 0
}
