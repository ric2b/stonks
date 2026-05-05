import sqlite3
from pathlib import Path


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            position INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_watchlist(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT ticker, position FROM watchlist ORDER BY position").fetchall()
    return [dict(row) for row in rows]


def add_ticker(conn: sqlite3.Connection, ticker: str) -> None:
    max_pos = conn.execute("SELECT COALESCE(MAX(position), -1) FROM watchlist").fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (ticker, position) VALUES (?, ?)",
        (ticker.upper(), max_pos + 1),
    )
    conn.commit()


def remove_ticker(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


def reorder_watchlist(conn: sqlite3.Connection, tickers: list[str]) -> None:
    for position, ticker in enumerate(tickers):
        conn.execute(
            "UPDATE watchlist SET position = ? WHERE ticker = ?",
            (position, ticker.upper()),
        )
    conn.commit()
