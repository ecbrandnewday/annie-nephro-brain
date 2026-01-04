import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite3")
SEED_DB_PATH = os.path.join(os.path.dirname(__file__), "seed_db.sqlite3")
SEED_LIMIT = int(os.environ.get("SEED_LIMIT", 20))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT,
            journal TEXT,
            publish_date TEXT,
            url TEXT,
            tags TEXT,
            key_takeaway TEXT,
            study_type TEXT,
            primary_outcome TEXT,
            outcome_direction TEXT,
            pico_p TEXT,
            pico_i TEXT,
            pico_c TEXT,
            pico_o TEXT,
            impact_level TEXT,
            impact_reason TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY(article_id, tag)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_tags_article ON article_tags(article_id)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS article_summaries (
            article_id TEXT PRIMARY KEY,
            summary_json TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    _seed_if_empty(conn)
    _migrate_article_tags(conn)
    conn.close()


def get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn, key, value):
    conn.execute(
        """
        INSERT INTO meta (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def get_article_summary(conn, article_id):
    row = conn.execute(
        "SELECT summary_json FROM article_summaries WHERE article_id = ?",
        (article_id,),
    ).fetchone()
    return row["summary_json"] if row else None


def upsert_article_summary(conn, article_id, summary_json, updated_at):
    conn.execute(
        """
        INSERT INTO article_summaries (article_id, summary_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(article_id) DO UPDATE SET
            summary_json = excluded.summary_json,
            updated_at = excluded.updated_at
        """,
        (article_id, summary_json, updated_at),
    )
    conn.commit()


def upsert_article_tags(conn, article_id, tags):
    if not tags:
        return
    cur = conn.cursor()
    for tag in tags:
        cur.execute(
            "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
            (article_id, tag),
        )
    conn.commit()


def _migrate_article_tags(conn):
    migrated = get_meta(conn, "article_tags_migrated")
    if migrated:
        return
    rows = conn.execute(
        "SELECT id, tags FROM articles WHERE tags IS NOT NULL AND tags != ''"
    ).fetchall()
    for row in rows:
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
        except json.JSONDecodeError:
            tags = []
        upsert_article_tags(conn, row["id"], tags)
    set_meta(conn, "article_tags_migrated", "1")


def _seed_if_empty(conn):
    if not os.path.exists(SEED_DB_PATH):
        return
    row = conn.execute("SELECT COUNT(*) FROM articles").fetchone()
    if row and row[0]:
        return
    seed_conn = sqlite3.connect(SEED_DB_PATH)
    seed_conn.row_factory = sqlite3.Row
    seed_rows = seed_conn.execute(
        "SELECT * FROM articles ORDER BY publish_date DESC LIMIT ?",
        (SEED_LIMIT,),
    ).fetchall()
    if not seed_rows:
        seed_conn.close()
        return
    columns = [
        "id",
        "title",
        "abstract",
        "journal",
        "publish_date",
        "url",
        "tags",
        "key_takeaway",
        "study_type",
        "primary_outcome",
        "outcome_direction",
        "pico_p",
        "pico_i",
        "pico_c",
        "pico_o",
        "impact_level",
        "impact_reason",
        "created_at",
        "updated_at",
    ]
    placeholders = ",".join(["?"] * len(columns))
    insert_sql = f"INSERT OR IGNORE INTO articles ({', '.join(columns)}) VALUES ({placeholders})"
    for seed_row in seed_rows:
        values = [seed_row[column] for column in columns]
        conn.execute(insert_sql, values)
    conn.commit()
    seed_conn.close()
