CREATE TABLE IF NOT EXISTS corpora (
    id SERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    language TEXT NOT NULL,
    source_reference TEXT NOT NULL DEFAULT 'TBD',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS passages (
    id SERIAL PRIMARY KEY,
    corpus_id INTEGER NOT NULL REFERENCES corpora(id) ON DELETE CASCADE,
    passage_key TEXT NOT NULL UNIQUE,
    passage_number INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    source_text TEXT NOT NULL,
    selected_by TEXT NOT NULL DEFAULT '',
    source_reference TEXT NOT NULL DEFAULT 'TBD',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (corpus_id, passage_number)
);

CREATE TABLE IF NOT EXISTS translation_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    profile_version INTEGER NOT NULL DEFAULT 1,
    label TEXT NOT NULL,
    style_kind TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL,
    default_model TEXT NOT NULL DEFAULT 'gpt-5.5',
    default_max_output_tokens INTEGER NOT NULL DEFAULT 2400,
    priority INTEGER NOT NULL DEFAULT 4,
    is_focal BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, profile_version)
);

CREATE TABLE IF NOT EXISTS translation_runs (
    id SERIAL PRIMARY KEY,
    passage_id INTEGER NOT NULL REFERENCES passages(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES translation_profiles(id) ON DELETE CASCADE,
    run_index INTEGER NOT NULL DEFAULT 1,
    model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    translation_text TEXT NOT NULL DEFAULT '',
    response_id TEXT NOT NULL DEFAULT '',
    usage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL DEFAULT '',
    public_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    public_block_reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (passage_id, profile_id, run_index),
    CHECK (status IN ('pending', 'running', 'completed', 'approved', 'failed'))
);

CREATE INDEX IF NOT EXISTS translation_runs_passage_status_idx
    ON translation_runs (passage_id, status);

CREATE INDEX IF NOT EXISTS translation_runs_profile_status_idx
    ON translation_runs (profile_id, status);

CREATE TABLE IF NOT EXISTS review_sets (
    id SERIAL PRIMARY KEY,
    pack_slug TEXT NOT NULL,
    set_slug TEXT NOT NULL,
    set_label TEXT NOT NULL,
    source_corpus TEXT NOT NULL,
    seed INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (pack_slug, set_slug)
);

CREATE TABLE IF NOT EXISTS review_items (
    id SERIAL PRIMARY KEY,
    review_set_id INTEGER NOT NULL REFERENCES review_sets(id) ON DELETE CASCADE,
    passage_id INTEGER NOT NULL REFERENCES passages(id) ON DELETE CASCADE,
    web_passage_id INTEGER NOT NULL UNIQUE,
    display_order INTEGER NOT NULL,
    treatment TEXT NOT NULL,
    focal_run_id INTEGER NOT NULL REFERENCES translation_runs(id),
    helper_profile_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (review_set_id, display_order),
    UNIQUE (review_set_id, passage_id),
    CHECK (treatment IN ('parallage', 'single'))
);

CREATE INDEX IF NOT EXISTS review_items_set_order_idx
    ON review_items (review_set_id, display_order);
