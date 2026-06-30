import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DATABASE_PATH", "golf_prices.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    brand       TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT 'Other',
    description TEXT    NOT NULL DEFAULT '',
    url         TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL,
    price       REAL    NOT NULL,
    retailer    TEXT    NOT NULL DEFAULT '',
    notes       TEXT    NOT NULL DEFAULT '',
    recorded_at TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    threshold_price REAL    NOT NULL,
    alert_type      TEXT    NOT NULL DEFAULT 'below',
    notes           TEXT    NOT NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    triggered_at    TEXT,
    triggered_price REAL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
"""


def _migrate(conn):
    """Add columns to alerts table for databases created before this schema version."""
    for col, typedef in [
        ("notes", "TEXT NOT NULL DEFAULT ''"),
        ("triggered_at", "TEXT"),
        ("triggered_price", "REAL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {typedef}")
        except Exception:
            pass  # column already exists


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


CATEGORIES = [
    "Drivers",
    "Fairway Woods",
    "Hybrids",
    "Irons",
    "Wedges",
    "Putters",
    "Golf Balls",
    "Golf Bags",
    "Golf Shoes",
    "Apparel",
    "Accessories",
    "Other",
]
