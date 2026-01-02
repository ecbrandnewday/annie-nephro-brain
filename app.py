import argparse
import json
import os
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request

from ai import summarize_article_with_openai
from db import get_article_summary as get_cached_summary, get_db, get_meta, init_db, upsert_article_summary
from ingest import DEFAULT_JOURNALS, run_ingest, run_ingest_range

app = Flask(__name__)


def _parse_tags(args):
    values = []
    raw_list = args.getlist("tags")
    if raw_list:
        values.extend(raw_list)
    raw_single = args.get("tag")
    if raw_single:
        values.append(raw_single)
    tags = []
    for raw in values:
        for part in raw.split(","):
            value = part.strip()
            if value and value != "ALL":
                tags.append(value)
    return sorted(set(tags))


def row_to_dict(row, include_abstract=False):
    tags = json.loads(row["tags"]) if row["tags"] else []
    payload = {
        "id": row["id"],
        "title": row["title"],
        "journal": row["journal"],
        "publish_date": row["publish_date"],
        "url": row["url"],
        "tags": tags,
        "key_takeaway": row["key_takeaway"],
        "study_type": row["study_type"],
        "primary_outcome": row["primary_outcome"],
        "outcome_direction": row["outcome_direction"],
        "pico_p": row["pico_p"],
        "pico_i": row["pico_i"],
        "pico_c": row["pico_c"],
        "pico_o": row["pico_o"],
        "impact_level": row["impact_level"],
        "impact_reason": row["impact_reason"],
    }
    payload["abstract"] = row["abstract"] if include_abstract else None
    return payload


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/articles")
def list_articles():
    init_db()
    selected_date = request.args.get("date")
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    include_abstract = request.args.get("include_abstract", "0") == "1"
    tags = _parse_tags(request.args)
    limit = int(request.args.get("limit", 200))
    offset = int(request.args.get("offset", 0))
    conn = get_db()
    query = "SELECT DISTINCT articles.* FROM articles"
    join = ""
    where_clauses = []
    params = []
    if tags:
        join = " JOIN article_tags ON article_tags.article_id = articles.id"
        placeholders = ",".join(["?"] * len(tags))
        where_clauses.append(f"article_tags.tag IN ({placeholders})")
        params.extend(tags)
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
        where_clauses.append("publish_date BETWEEN ? AND ?")
        params.extend([start_str, end_str])
    elif selected_date:
        where_clauses.append("publish_date = ?")
        params.append(selected_date)
    if join:
        query += join
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY publish_date DESC"
    if limit:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    last_sync = get_meta(conn, "last_sync")
    conn.close()
    articles = []
    for row in rows:
        article = row_to_dict(row, include_abstract=include_abstract)
        articles.append(article)
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


@app.route("/api/articles/range")
def list_articles_range():
    init_db()
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    tags = _parse_tags(request.args)
    include_abstract = request.args.get("include_abstract", "0") == "1"
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    if not start_str or not end_str:
        return jsonify({"error": "請提供 start 與 end（YYYY-MM）"}), 400
    try:
        start_month = datetime.strptime(start_str, "%Y-%m").date().replace(day=1)
        end_month = datetime.strptime(end_str, "%Y-%m").date().replace(day=1)
    except ValueError:
        return jsonify({"error": "月份格式錯誤，請使用 YYYY-MM"}), 400
    if start_month > end_month:
        return jsonify({"error": "起始月份不可晚於結束月份"}), 400
    month_span = (end_month.year - start_month.year) * 12 + (end_month.month - start_month.month) + 1
    if month_span > 12:
        return jsonify({"error": "查詢區間最多 12 個月"}), 400
    next_month = (end_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_date = next_month - timedelta(days=1)
    start_date = start_month

    conn = get_db()
    params = [start_date.isoformat(), end_date.isoformat()]
    join = ""
    where_clauses = ["publish_date BETWEEN ? AND ?"]
    if tags:
        join = " JOIN article_tags ON article_tags.article_id = articles.id"
        placeholders = ",".join(["?"] * len(tags))
        where_clauses.append(f"article_tags.tag IN ({placeholders})")
        params.extend(tags)
    where = "WHERE " + " AND ".join(where_clauses)
    count_query = f"SELECT COUNT(DISTINCT articles.id) FROM articles{join} {where}"
    total_row = conn.execute(count_query, params).fetchone()
    total = total_row[0] if total_row else 0
    data_query = (
        f"SELECT DISTINCT articles.* FROM articles{join} {where} "
        "ORDER BY publish_date DESC LIMIT ? OFFSET ?"
    )
    rows = conn.execute(data_query, params + [limit, offset]).fetchall()
    conn.close()
    items = [row_to_dict(row, include_abstract=include_abstract) for row in rows]
    return jsonify({"total": total, "items": items})


@app.route("/api/articles/<article_id>")
def get_article(article_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    article = row_to_dict(row, include_abstract=True)
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
        if isinstance(payload, dict):
            conn.close()
            status = 200 if payload.get("ok", True) else 500
            return jsonify(payload), status
        conn.close()
        return jsonify({"ok": False, "summary": "UNKNOWN", "error": "invalid cached summary"}), 500
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
        start_month = start_date.replace(day=1)
        end_month = end_date.replace(day=1)
        month_span = (
            (end_month.year - start_month.year) * 12
            + (end_month.month - start_month.month)
            + 1
        )
        if month_span > 12:
            return jsonify({"error": "range too long (max 12 months)"}), 400
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
    parser = argparse.ArgumentParser(description="Run Nephro Brain API server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 5000)),
        help="Port to listen on (defaults to $PORT or 5000).",
    )
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=True)
