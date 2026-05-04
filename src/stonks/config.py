import os
from pathlib import Path

APP_NAME = "Stonks"

DB_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "stonks"
DB_PATH = DB_DIR / "stonks.db"

REFRESH_INTERVAL_MS = 60_000

TIME_RANGES = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "ALL": ("max", "1mo"),
}

INTRADAY_INTERVALS = {"5m", "30m", "1h"}
