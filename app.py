import json
import os
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

from db import get_db, get_meta, init_db
from ingest import DEFAULT_JOURNALS, run_ingest, run_ingest_range

app = Flask(__name__)


def row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "abstract": row["abstract"],
        "journal": row["journal"],
        "publish_date": row["publish_date"],
        "url": row["url"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "key_takeaway": row["key_takeaway"],
        "study_type": row["study_type"],
        "primary_outcome": row["primary_outcome"],
        "outcome_direction": row["outcome_direction"],
        "pico": {
            "P": row["pico_p"],
            "I": row["pico_i"],
            "C": row["pico_c"],
            "O": row["pico_o"],
        },
        "impact": {"level": row["impact_level"], "reason": row["impact_reason"]},
    }


def get_favorites(conn):
    rows = conn.execute("SELECT article_id FROM favorites").fetchall()
    return {row["article_id"] for row in rows}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/articles")
def list_articles():
    init_db()
    selected_date = request.args.get("date")
    tag = request.args.get("tag")
    limit = int(request.args.get("limit", 50))
    conn = get_db()
    query = "SELECT * FROM articles"
    params = []
    if selected_date:
        query += " WHERE publish_date = ?"
        params.append(selected_date)
    query += " ORDER BY publish_date DESC"
    rows = conn.execute(query, params).fetchall()
    favorites = get_favorites(conn)
    last_sync = get_meta(conn, "last_sync")
    conn.close()
    articles = []
    for row in rows:
        article = row_to_dict(row)
        article["favorite"] = article["id"] in favorites
        articles.append(article)
    if tag:
        articles = [a for a in articles if tag in a["tags"]]
    if limit:
        articles = articles[:limit]
    if selected_date:
        effective_date = selected_date
    elif articles:
        effective_date = articles[0]["publish_date"]
    else:
        effective_date = date.today().isoformat()
    return jsonify(
        {
            "date": effective_date,
            "last_sync": last_sync,
            "articles": articles,
        }
    )


@app.route("/api/articles/<article_id>")
def get_article(article_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    favorites = get_favorites(conn)
    conn.close()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    article = row_to_dict(row)
    article["favorite"] = article["id"] in favorites
    return jsonify(article)


@app.route("/api/favorites", methods=["GET"])
def list_favorites():
    init_db()
    conn = get_db()
    rows = conn.execute("SELECT article_id FROM favorites").fetchall()
    conn.close()
    return jsonify({"favorites": [row["article_id"] for row in rows]})


@app.route("/api/favorites/<article_id>", methods=["POST"])
def toggle_favorite(article_id):
    init_db()
    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT 1 FROM favorites WHERE article_id = ?", (article_id,)
    ).fetchone()
    if existing:
        cur.execute("DELETE FROM favorites WHERE article_id = ?", (article_id,))
        favorite = False
    else:
        cur.execute(
            "INSERT INTO favorites (article_id, created_at) VALUES (?, datetime('now'))",
            (article_id,),
        )
        favorite = True
    conn.commit()
    conn.close()
    return jsonify({"favorite": favorite})


@app.route("/api/refresh", methods=["POST"])
def refresh_articles():
    date_str = request.args.get("date")
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    days = int(request.args.get("days", 3))
    max_per_journal = int(request.args.get("max_per_journal", 5))
    if start_str or end_str:
        if not (start_str and end_str):
            return jsonify({"error": "start and end required"}), 400
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "invalid date range"}), 400
        if start_date > end_date:
            return jsonify({"error": "start after end"}), 400
        stored = run_ingest_range(
            DEFAULT_JOURNALS, start_date, end_date, max_per_journal
        )
    elif date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "invalid date"}), 400
        stored = run_ingest_range(
            DEFAULT_JOURNALS, target_date, target_date, max_per_journal
        )
    else:
        stored = run_ingest(DEFAULT_JOURNALS, days, max_per_journal)
    conn = get_db()
    last_sync = get_meta(conn, "last_sync")
    conn.close()
    return jsonify({"stored": stored, "last_sync": last_sync})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
