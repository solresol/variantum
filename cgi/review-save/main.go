package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cgi"
	"strconv"
	"strings"

	"github.com/solresol/variantum/cgi/shared"
)

func parseNullableRating(raw string) (sql.NullInt64, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return sql.NullInt64{}, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < 0 || value > 10 {
		return sql.NullInt64{}, fmt.Errorf("rating must be between 0 and 10")
	}
	return sql.NullInt64{Int64: int64(value), Valid: true}, nil
}

func parseExposureJSON(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "{}", nil
	}
	if len(raw) > 250000 {
		return "", fmt.Errorf("exposure_json is too large")
	}
	var decoded any
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		return "", fmt.Errorf("exposure_json must be valid JSON")
	}
	if _, ok := decoded.(map[string]any); !ok {
		return "", fmt.Errorf("exposure_json must be a JSON object")
	}
	return raw, nil
}

func handleSave(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST required", http.StatusMethodNotAllowed)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "Failed to parse form: "+err.Error(), http.StatusBadRequest)
		return
	}

	reviewer, err := shared.Reviewer(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusForbidden)
		return
	}
	packSlug := strings.TrimSpace(r.FormValue("pack_slug"))
	if packSlug == "" {
		http.Error(w, "pack_slug is required", http.StatusBadRequest)
		return
	}
	passageID, err := shared.RequiredInt(r, "passage_id")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	exposureJSON, err := parseExposureJSON(r.FormValue("exposure_json"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	db, err := shared.OpenDB()
	if err != nil {
		http.Error(w, "Failed to open review database: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer db.Close()

	tx, err := db.Begin()
	if err != nil {
		http.Error(w, "Failed to start transaction: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`
		INSERT INTO review_batches (pack_slug, updated_at)
		VALUES (?, datetime('now'))
		ON CONFLICT(pack_slug) DO UPDATE SET updated_at = datetime('now')
	`, packSlug); err != nil {
		http.Error(w, "Failed to record review batch: "+err.Error(), http.StatusInternalServerError)
		return
	}

	for _, variantIDRaw := range r.Form["variant_id"] {
		variantID := strings.TrimSpace(variantIDRaw)
		if variantID == "" {
			continue
		}
		rating, err := parseNullableRating(r.FormValue("rating_" + variantID))
		if err != nil {
			http.Error(w, "Variant "+variantID+": "+err.Error(), http.StatusBadRequest)
			return
		}
		notes := strings.TrimSpace(r.FormValue("notes_" + variantID))
		mostTrusted := shared.BoolFormValue(r, "most_"+variantID)
		leastTrusted := shared.BoolFormValue(r, "least_"+variantID)

		var ratingValue any = nil
		if rating.Valid {
			ratingValue = rating.Int64
		}

		if _, err := tx.Exec(`
			INSERT INTO variant_ratings (
				pack_slug, passage_id, variant_id, reviewer_username,
				rating, most_trusted, least_trusted, notes, exposure_json,
				created_at, updated_at
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
		`, packSlug, passageID, variantID, reviewer, ratingValue, mostTrusted, leastTrusted, notes, exposureJSON); err != nil {
			http.Error(w, "Failed to save variant "+variantID+": "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		http.Error(w, "Failed to commit review: "+err.Error(), http.StatusInternalServerError)
		return
	}

	fallback := fmt.Sprintf("/review/%s/passages/%d.html?saved=1", packSlug, passageID)
	http.Redirect(w, r, shared.SafeReturnURL(r.FormValue("return_url"), fallback), http.StatusSeeOther)
}

func main() {
	if err := cgi.Serve(http.HandlerFunc(handleSave)); err != nil {
		panic(err)
	}
}
