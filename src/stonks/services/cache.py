import sqlite3
from datetime import date

import pandas as pd

from stonks.config import INTRADAY_INTERVALS
from stonks.models.database import get_cached_prices, upsert_prices
from stonks.services.stock_data import fetch_history


def get_history(conn: sqlite3.Connection, ticker: str, period: str, interval: str) -> pd.DataFrame:
    if interval in INTRADAY_INTERVALS:
        return fetch_history(ticker, period, interval)

    cached = get_cached_prices(conn, ticker, "1900-01-01", "2999-12-31")
    if cached and cached[-1]["date"] == date.today().isoformat():
        df = pd.DataFrame(cached)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df = df.drop(columns=["ticker"], errors="ignore")
        df.columns = [c.capitalize() for c in df.columns]
        return df

    df = fetch_history(ticker, period, interval)
    rows = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": row["Open"],
            "high": row["High"],
            "low": row["Low"],
            "close": row["Close"],
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
        }
        for idx, row in df.iterrows()
    ]
    upsert_prices(conn, ticker, rows)
    return df
