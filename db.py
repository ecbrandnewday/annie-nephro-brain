import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite3")


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
