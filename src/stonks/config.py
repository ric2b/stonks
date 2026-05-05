import os
from pathlib import Path

APP_NAME = "Stonks"

DB_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "stonks"
DB_PATH = DB_DIR / "stonks.db"

REFRESH_INTERVAL_MS = 60_000

TIME_RANGES = {
    "1D": ("1d", "2m"),
    "1W": ("5d", "5m"),
    "1M": ("1mo", "30m"),
    "3M": ("3mo", "1h"),
    "6M": ("6mo", "1h"),
    "YTD": ("ytd", "1h"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "10Y": ("10y", "1wk"),
    "ALL": ("max", "1mo"),
}

INTRADAY_INTERVALS = {"2m", "5m", "30m", "1h"}
