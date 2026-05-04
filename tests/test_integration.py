from unittest.mock import patch

import pandas as pd

from stonks.models.database import add_ticker, get_cached_prices, get_watchlist
from stonks.services.cache import get_history


def _make_df():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [103.0, 104.0, 105.0],
            "Volume": [1000000, 1100000, 1200000],
        },
        index=dates,
    )


@patch("stonks.services.cache.fetch_history")
def test_full_path_add_ticker_fetch_and_cache(mock_fetch, db):
    mock_fetch.return_value = _make_df()

    add_ticker(db, "AAPL")
    watchlist = get_watchlist(db)
    assert watchlist[0]["ticker"] == "AAPL"

    df = get_history(db, "AAPL", "1mo", "1d")
    assert len(df) == 3
    assert df["Close"].iloc[-1] == 105.0

    cached = get_cached_prices(db, "AAPL", "2024-01-01", "2024-01-03")
    assert len(cached) == 3
    assert cached[0]["close"] == 103.0
    assert cached[2]["volume"] == 1200000
