import json
from datetime import date

from flask import Flask, jsonify, render_template, request

from db import get_db, init_db

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
    return jsonify({"date": selected_date or date.today().isoformat(), "articles": articles})


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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
