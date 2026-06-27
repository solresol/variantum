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
