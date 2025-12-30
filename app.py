import json
import os
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

from ai import debug_openai_ping, summarize, summarize_article_with_openai
from db import get_article_summary as get_cached_summary, get_db, get_meta, init_db, upsert_article_summary
from ingest import DEFAULT_JOURNALS, run_ingest, run_ingest_range

app = Flask(__name__)


def row_to_dict(row):
    tags = json.loads(row["tags"]) if row["tags"] else []
    summary = summarize(row["title"], row["abstract"], tags)
    return {
        "id": row["id"],
        "title": row["title"],
        "abstract": row["abstract"],
        "journal": row["journal"],
        "publish_date": row["publish_date"],
        "url": row["url"],
        "tags": tags,
        "key_takeaway": summary["key_takeaway"],
        "study_type": summary["study_type"],
        "primary_outcome": summary["primary_outcome"],
        "outcome_direction": summary["outcome_direction"],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/articles")
def list_articles():
    init_db()
    selected_date = request.args.get("date")
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    tag = request.args.get("tag")
    limit = int(request.args.get("limit", 200))
    conn = get_db()
    query = "SELECT * FROM articles"
    params = []
    if start_str or end_str:
        if not (start_str and end_str):
            conn.close()
            return jsonify({"error": "start and end required"}), 400
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            conn.close()
            return jsonify({"error": "invalid date range"}), 400
        if start_date > end_date:
            conn.close()
            return jsonify({"error": "start after end"}), 400
        if (end_date - start_date).days + 1 > 30:
            conn.close()
            return jsonify({"error": "range too long"}), 400
        query += " WHERE publish_date BETWEEN ? AND ?"
        params.extend([start_str, end_str])
    elif selected_date:
        query += " WHERE publish_date = ?"
        params.append(selected_date)
    query += " ORDER BY publish_date DESC"
    rows = conn.execute(query, params).fetchall()
    last_sync = get_meta(conn, "last_sync")
    conn.close()
    articles = []
    for row in rows:
        article = row_to_dict(row)
        articles.append(article)
    if tag:
        articles = [a for a in articles if tag in a["tags"]]
    if limit:
        articles = articles[:limit]
    if start_str and end_str:
        effective_date = end_str
    elif selected_date:
        effective_date = selected_date
    elif articles:
        effective_date = articles[0]["publish_date"]
    else:
        effective_date = date.today().isoformat()
    return jsonify(
        {
            "date": effective_date,
            "range": {"start": start_str, "end": end_str} if start_str and end_str else None,
            "last_sync": last_sync,
            "articles": articles,
        }
    )


@app.route("/api/articles/<article_id>")
def get_article(article_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    article = row_to_dict(row)
    return jsonify(article)


@app.route("/api/articles/<article_id>/summary", methods=["POST"])
def get_article_summary(article_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    cached = get_cached_summary(conn, article_id)
    if cached:
        try:
            payload = json.loads(cached)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and "ok" in payload:
            conn.close()
            return jsonify(payload), (200 if payload.get("ok") else 500)
    summary = summarize_article_with_openai(row["title"], row["abstract"] or "")
    if not summary.get("ok"):
        conn.close()
        return jsonify(summary), 500
    upsert_article_summary(
        conn,
        article_id,
        json.dumps(summary, ensure_ascii=False),
        datetime.utcnow().isoformat(),
    )
    conn.close()
    return jsonify(summary)


@app.route("/api/debug/openai")
def debug_openai():
    payload = debug_openai_ping()
    return jsonify(payload), (200 if payload.get("ok") else 500)


@app.route("/api/refresh", methods=["POST"])
def refresh_articles():
    date_str = request.args.get("date")
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    days = int(request.args.get("days", 3))
    max_param = request.args.get("max_per_journal")
    max_per_journal = int(max_param) if max_param else 5
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
        if (end_date - start_date).days + 1 > 30:
            return jsonify({"error": "range too long"}), 400
        if max_param is None:
            max_per_journal = 0
        stored = run_ingest_range(
            DEFAULT_JOURNALS, start_date, end_date, max_per_journal
        )
    elif date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "invalid date"}), 400
        if max_param is None:
            max_per_journal = 0
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
