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
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.commit()
    return conn


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
    conn.execute("DELETE FROM price_cache WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


def reorder_watchlist(conn: sqlite3.Connection, tickers: list[str]) -> None:
    for position, ticker in enumerate(tickers):
        conn.execute(
            "UPDATE watchlist SET position = ? WHERE ticker = ?",
            (position, ticker.upper()),
        )
    conn.commit()


def get_cached_prices(
    conn: sqlite3.Connection, ticker: str, start_date: str, end_date: str
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM price_cache WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date",
        (ticker.upper(), start_date, end_date),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_prices(conn: sqlite3.Connection, ticker: str, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO price_cache (ticker, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                ticker.upper(),
                row["date"],
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                row.get("volume"),
            )
            for row in rows
        ],
    )
    conn.commit()
