package main

import (
	"database/sql"
	"net/http"
	"net/http/cgi"
	"strings"

	"github.com/solresol/variantum/cgi/shared"
)

type Rating struct {
	Rating       *int   `json:"rating"`
	MostTrusted  bool   `json:"most_trusted"`
	LeastTrusted bool   `json:"least_trusted"`
	Notes        string `json:"notes"`
	UpdatedAt    string `json:"updated_at"`
}

type StateResponse struct {
	Reviewer  string            `json:"reviewer"`
	PackSlug  string            `json:"pack_slug"`
	PassageID int               `json:"passage_id"`
	Ratings   map[string]Rating `json:"ratings"`
}

func handleState(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		shared.ErrorResponse(w, http.StatusMethodNotAllowed, "GET required")
		return
	}
	reviewer, err := shared.Reviewer(r)
	if err != nil {
		shared.ErrorResponse(w, http.StatusForbidden, err.Error())
		return
	}
	packSlug := strings.TrimSpace(r.URL.Query().Get("pack_slug"))
	if packSlug == "" {
		shared.ErrorResponse(w, http.StatusBadRequest, "pack_slug is required")
		return
	}
	passageID, err := shared.RequiredInt(r, "passage_id")
	if err != nil {
		shared.ErrorResponse(w, http.StatusBadRequest, err.Error())
		return
	}

	db, err := shared.OpenDB()
	if err != nil {
		shared.ErrorResponse(w, http.StatusInternalServerError, "database error")
		return
	}
	defer db.Close()

	rows, err := db.Query(`
		SELECT vr.variant_id, vr.rating, vr.most_trusted, vr.least_trusted, vr.notes, vr.updated_at
		FROM variant_ratings vr
		JOIN (
			SELECT variant_id, MAX(id) AS latest_id
			FROM variant_ratings
			WHERE pack_slug = ?
			  AND passage_id = ?
			  AND reviewer_username = ?
			GROUP BY variant_id
		) latest ON latest.latest_id = vr.id
		ORDER BY vr.variant_id
	`, packSlug, passageID, reviewer)
	if err != nil {
		shared.ErrorResponse(w, http.StatusInternalServerError, "query error")
		return
	}
	defer rows.Close()

	ratings := map[string]Rating{}
	for rows.Next() {
		var variantID string
		var rating sql.NullInt64
		var mostTrusted int
		var leastTrusted int
		var notes string
		var updatedAt string
		if err := rows.Scan(&variantID, &rating, &mostTrusted, &leastTrusted, &notes, &updatedAt); err != nil {
			shared.ErrorResponse(w, http.StatusInternalServerError, "scan error")
			return
		}
		var ratingPtr *int
		if rating.Valid {
			value := int(rating.Int64)
			ratingPtr = &value
		}
		ratings[variantID] = Rating{
			Rating:       ratingPtr,
			MostTrusted:  mostTrusted != 0,
			LeastTrusted: leastTrusted != 0,
			Notes:        notes,
			UpdatedAt:    updatedAt,
		}
	}

	shared.JSONResponse(w, http.StatusOK, StateResponse{
		Reviewer:  reviewer,
		PackSlug:  packSlug,
		PassageID: passageID,
		Ratings:   ratings,
	})
}

func main() {
	if err := cgi.Serve(http.HandlerFunc(handleState)); err != nil {
		panic(err)
	}
}
