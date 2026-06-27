package main

import (
	"html/template"
	"net/http"
	"net/http/cgi"
	"strings"

	"github.com/solresol/variantum/cgi/shared"
)

type ReviewerSummary struct {
	Reviewer       string
	Transactions   int
	Passages       int
	HighDifference int
	LowDifference  int
	Updated        string
}

type RecentRating struct {
	Reviewer     string
	PackSlug     string
	PassageID    int
	VariantID    string
	Rating       int
	RatingValid  bool
	MostTrusted  bool
	LeastTrusted bool
	Updated      string
}

type PageData struct {
	PackSlug  string
	Reviewer  string
	Summaries []ReviewerSummary
	Recent    []RecentRating
}

var pageTemplate = template.Must(template.New("status").Parse(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Parallage Review Status</title>
    <link rel="stylesheet" href="/assets/review.css">
</head>
<body>
    <main class="shell">
        <section class="masthead">
            <div>
                <h1>Parallage Review Status</h1>
                <p class="muted">Signed in as <strong>{{.Reviewer}}</strong>{{if .PackSlug}} · pack <code>{{.PackSlug}}</code>{{end}}</p>
            </div>
            <nav class="top-actions">
                <a class="button secondary" href="/">Home</a>
            </nav>
        </section>
        <section class="panel">
            <table>
                <thead><tr><th>Reviewer</th><th>Transactions</th><th>Passages</th><th>High difference</th><th>Low difference</th><th>Updated</th></tr></thead>
                <tbody>
                    {{range .Summaries}}
                    <tr>
                        <td>{{.Reviewer}}</td>
                        <td>{{.Transactions}}</td>
                        <td>{{.Passages}}</td>
                        <td>{{.HighDifference}}</td>
                        <td>{{.LowDifference}}</td>
                        <td>{{.Updated}}</td>
                    </tr>
                    {{else}}
                    <tr><td colspan="6">No ratings saved yet.</td></tr>
                    {{end}}
                </tbody>
            </table>
        </section>
        <section class="panel" style="margin-top: 18px;">
            <table>
                <thead><tr><th>Updated</th><th>Reviewer</th><th>Pack</th><th>Passage</th><th>Rated translation</th><th>Difference score</th></tr></thead>
                <tbody>
                    {{range .Recent}}
                    <tr>
                        <td>{{.Updated}}</td>
                        <td>{{.Reviewer}}</td>
                        <td>{{.PackSlug}}</td>
                        <td><a href="/review/{{.PackSlug}}/passages/{{.PassageID}}.html">{{.PassageID}}</a></td>
                        <td>{{.VariantID}}</td>
                        <td>{{if .RatingValid}}{{.Rating}}{{else}}—{{end}}</td>
                    </tr>
                    {{else}}
                    <tr><td colspan="6">No recent ratings.</td></tr>
                    {{end}}
                </tbody>
            </table>
        </section>
    </main>
</body>
</html>`))

func handleStatus(w http.ResponseWriter, r *http.Request) {
	reviewer, err := shared.Reviewer(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusForbidden)
		return
	}
	packSlug := strings.TrimSpace(r.URL.Query().Get("pack_slug"))

	db, err := shared.OpenDB()
	if err != nil {
		http.Error(w, "Failed to open review database: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer db.Close()

	args := []any{}
	where := ""
	if packSlug != "" {
		where = "WHERE pack_slug = ?"
		args = append(args, packSlug)
	}

	rows, err := db.Query(`
		SELECT
			reviewer_username,
			COUNT(*) AS transaction_count,
			COUNT(DISTINCT passage_id) AS passage_count,
			COALESCE(SUM(CASE WHEN rating >= 7 THEN 1 ELSE 0 END), 0) AS high_difference_count,
			COALESCE(SUM(CASE WHEN rating <= 3 THEN 1 ELSE 0 END), 0) AS low_difference_count,
			MAX(updated_at) AS updated_at
		FROM variant_ratings
		`+where+`
		GROUP BY reviewer_username
		ORDER BY reviewer_username
	`, args...)
	if err != nil {
		http.Error(w, "Failed to load summaries: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var summaries []ReviewerSummary
	for rows.Next() {
		var s ReviewerSummary
		if err := rows.Scan(&s.Reviewer, &s.Transactions, &s.Passages, &s.HighDifference, &s.LowDifference, &s.Updated); err != nil {
			http.Error(w, "Failed to scan summaries: "+err.Error(), http.StatusInternalServerError)
			return
		}
		summaries = append(summaries, s)
	}

	recentRows, err := db.Query(`
		SELECT reviewer_username, pack_slug, passage_id, variant_id, rating, most_trusted, least_trusted, updated_at
		FROM variant_ratings
		`+where+`
		ORDER BY datetime(updated_at) DESC, id DESC
		LIMIT 80
	`, args...)
	if err != nil {
		http.Error(w, "Failed to load recent ratings: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer recentRows.Close()

	var recent []RecentRating
	for recentRows.Next() {
		var rrow RecentRating
		var rating any
		var mostTrusted int
		var leastTrusted int
		if err := recentRows.Scan(&rrow.Reviewer, &rrow.PackSlug, &rrow.PassageID, &rrow.VariantID, &rating, &mostTrusted, &leastTrusted, &rrow.Updated); err != nil {
			http.Error(w, "Failed to scan recent ratings: "+err.Error(), http.StatusInternalServerError)
			return
		}
		switch value := rating.(type) {
		case int64:
			rrow.Rating = int(value)
			rrow.RatingValid = true
		case int:
			rrow.Rating = value
			rrow.RatingValid = true
		}
		rrow.MostTrusted = mostTrusted != 0
		rrow.LeastTrusted = leastTrusted != 0
		recent = append(recent, rrow)
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := pageTemplate.Execute(w, PageData{
		PackSlug:  packSlug,
		Reviewer:  reviewer,
		Summaries: summaries,
		Recent:    recent,
	}); err != nil {
		http.Error(w, "Template error: "+err.Error(), http.StatusInternalServerError)
	}
}

func main() {
	if err := cgi.Serve(http.HandlerFunc(handleStatus)); err != nil {
		panic(err)
	}
}
