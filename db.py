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
        CREATE TABLE IF NOT EXISTS favorites (
            article_id TEXT PRIMARY KEY,
            created_at TEXT
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
