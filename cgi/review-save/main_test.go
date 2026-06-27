package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"testing"

	"github.com/solresol/variantum/cgi/shared"
)

func postRating(t *testing.T, values url.Values) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodPost, "/cgi-bin/review-save.cgi", strings.NewReader(values.Encode()))
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	response := httptest.NewRecorder()
	handleSave(response, request)
	return response
}

func TestHandleSaveKeepsEveryRatingTransaction(t *testing.T) {
	t.Setenv("REMOTE_USER", "greta")
	t.Setenv("PARALLAGE_REVIEW_DB", filepath.Join(t.TempDir(), "reviews.db"))

	first := url.Values{
		"pack_slug":     {"stephanos-review-v1"},
		"passage_id":    {"2330"},
		"variant_id":    {"3302"},
		"rating_3302":   {"4"},
		"exposure_json": {`{"variants":{"5083":{"visible_ms":700}}}`},
	}
	second := url.Values{
		"pack_slug":     {"stephanos-review-v1"},
		"passage_id":    {"2330"},
		"variant_id":    {"3302"},
		"rating_3302":   {"8"},
		"exposure_json": {`{"variants":{"5083":{"visible_ms":130}}}`},
	}

	if response := postRating(t, first); response.Code != http.StatusSeeOther {
		t.Fatalf("first save status = %d, body = %s", response.Code, response.Body.String())
	}
	if response := postRating(t, second); response.Code != http.StatusSeeOther {
		t.Fatalf("second save status = %d, body = %s", response.Code, response.Body.String())
	}

	db, err := shared.OpenDB()
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	rows, err := db.Query(`
		SELECT rating, exposure_json
		FROM variant_ratings
		ORDER BY id
	`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()

	var ratings []int
	var exposures []string
	for rows.Next() {
		var rating int
		var exposure string
		if err := rows.Scan(&rating, &exposure); err != nil {
			t.Fatal(err)
		}
		ratings = append(ratings, rating)
		exposures = append(exposures, exposure)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if len(ratings) != 2 || ratings[0] != 4 || ratings[1] != 8 {
		t.Fatalf("expected append-only ratings [4 8], got %v", ratings)
	}
	if exposures[0] == exposures[1] {
		t.Fatalf("expected each transaction to preserve its own exposure payload, got %q", exposures[0])
	}
}
