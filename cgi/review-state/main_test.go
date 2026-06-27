package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/solresol/variantum/cgi/shared"
)

func TestHandleStateReturnsLatestRatingPerVariant(t *testing.T) {
	t.Setenv("REMOTE_USER", "greta")
	t.Setenv("PARALLAGE_REVIEW_DB", filepath.Join(t.TempDir(), "reviews.db"))

	db, err := shared.OpenDB()
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	_, err = db.Exec(`
INSERT INTO variant_ratings (pack_slug, passage_id, variant_id, reviewer_username, rating, exposure_json)
VALUES
    ('stephanos-review-v1', 2330, '3302', 'greta', 2, '{"first":true}'),
    ('stephanos-review-v1', 2330, '3302', 'greta', 9, '{"second":true}'),
    ('stephanos-review-v1', 2330, '3302', 'shirley', 5, '{"other_reviewer":true}'),
    ('stephanos-review-v1', 2330, '9999', 'greta', 3, '{"other_variant":true}');
`)
	if err != nil {
		t.Fatal(err)
	}

	request := httptest.NewRequest(
		http.MethodGet,
		"/cgi-bin/review-state.cgi?pack_slug=stephanos-review-v1&passage_id=2330",
		nil,
	)
	response := httptest.NewRecorder()
	handleState(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("state status = %d, body = %s", response.Code, response.Body.String())
	}

	var state StateResponse
	if err := json.Unmarshal(response.Body.Bytes(), &state); err != nil {
		t.Fatal(err)
	}

	focal := state.Ratings["3302"]
	if focal.Rating == nil || *focal.Rating != 9 {
		t.Fatalf("expected latest focal rating 9, got %#v", focal.Rating)
	}
	other := state.Ratings["9999"]
	if other.Rating == nil || *other.Rating != 3 {
		t.Fatalf("expected other variant rating 3, got %#v", other.Rating)
	}
	if _, ok := state.Ratings["shirley"]; ok {
		t.Fatalf("state should not leak another reviewer's rows: %#v", state.Ratings)
	}
}
