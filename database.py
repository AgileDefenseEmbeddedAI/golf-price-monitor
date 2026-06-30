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
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    threshold_price REAL    NOT NULL,
    alert_type      TEXT    NOT NULL DEFAULT 'below',
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
"""


def _migrate(conn):
    """Add columns to existing tables that predate the auth migration."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "user_id" not in cols:
        conn.execute(
            "ALTER TABLE products ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        )

    alert_cols = {row[1] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
    if "user_id" not in alert_cols:
        conn.execute(
            "ALTER TABLE alerts ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        )

    # Assign orphaned products (from pre-auth data) to the first existing user,
    # or create a default admin user if none exist.
    orphaned = conn.execute("SELECT COUNT(*) FROM products WHERE user_id IS NULL").fetchone()[0]
    if orphaned > 0:
        user = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if user:
            conn.execute("UPDATE products SET user_id = ? WHERE user_id IS NULL", (user["id"],))
        else:
            import secrets
            from auth import hash_password
            tmp_password = secrets.token_hex(8)
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("admin", "", hash_password(tmp_password)),
            )
            admin_id = cur.lastrowid
            conn.execute("UPDATE products SET user_id = ? WHERE user_id IS NULL", (admin_id,))
            print("\n[Golf Price Monitor] Created admin user for existing data.")
            print(f"  Username: admin")
            print(f"  Password: {tmp_password}")
            print("  (Change this password in Account Settings after first login)\n")


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
    with db() as conn:
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
