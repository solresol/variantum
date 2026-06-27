package shared

import (
	"database/sql"
	"path/filepath"
	"strings"
	"testing"

	_ "github.com/mattn/go-sqlite3"
)

func TestEnsureSchemaMigratesVariantRatingsToAppendOnly(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "reviews.db")
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	_, err = db.Exec(`
CREATE TABLE variant_ratings (
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
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (pack_slug, passage_id, variant_id, reviewer_username)
);
INSERT INTO variant_ratings (
    pack_slug, passage_id, variant_id, reviewer_username, rating, exposure_json
) VALUES ('stephanos-review-v1', 2330, '3302', 'greta', 4, '{"before":true}');
`)
	if err != nil {
		t.Fatal(err)
	}

	if err := EnsureSchema(db); err != nil {
		t.Fatal(err)
	}

	var createSQL string
	if err := db.QueryRow(`
		SELECT sql
		FROM sqlite_master
		WHERE type = 'table'
		  AND name = 'variant_ratings'
	`).Scan(&createSQL); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(createSQL, "UNIQUE (pack_slug, passage_id, variant_id, reviewer_username)") {
		t.Fatalf("variant_ratings should be append-only, schema still has unique key: %s", createSQL)
	}

	_, err = db.Exec(`
INSERT INTO variant_ratings (
    pack_slug, passage_id, variant_id, reviewer_username, rating, exposure_json
) VALUES ('stephanos-review-v1', 2330, '3302', 'greta', 8, '{"after":true}');
`)
	if err != nil {
		t.Fatalf("second transaction should insert instead of conflicting: %v", err)
	}

	var count int
	if err := db.QueryRow(`SELECT COUNT(*) FROM variant_ratings`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Fatalf("expected 2 transaction rows, got %d", count)
	}
}
