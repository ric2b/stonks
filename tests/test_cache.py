from datetime import date
from unittest.mock import patch

import pandas as pd

from stonks.models.database import upsert_prices
from stonks.services.cache import get_history


def _make_df(start="2024-01-01", periods=5):
    dates = pd.date_range(start, periods=periods, freq="D")
    return pd.DataFrame(
        {
            "Open": range(periods),
            "High": range(periods),
            "Low": range(periods),
            "Close": range(100, 100 + periods),
            "Volume": [1000000] * periods,
        },
        index=dates,
    )


@patch("stonks.services.cache.fetch_history")
def test_intraday_always_fetches_fresh(mock_fetch, db):
    mock_fetch.return_value = _make_df()
    get_history(db, "AAPL", "1d", "5m")
    mock_fetch.assert_called_once_with("AAPL", "1d", "5m")


@patch("stonks.services.cache.fetch_history")
def test_daily_fetches_when_no_cache(mock_fetch, db):
    mock_fetch.return_value = _make_df()
    df = get_history(db, "AAPL", "1mo", "1d")
    mock_fetch.assert_called_once()
    assert len(df) == 5


@patch("stonks.services.cache.fetch_history")
def test_daily_uses_cache_when_fresh(mock_fetch, db):
    today = date.today().isoformat()
    upsert_prices(
        db,
        "AAPL",
        [
            {
                "date": today,
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 1000000,
            },
        ],
    )
    df = get_history(db, "AAPL", "1mo", "1d")
    mock_fetch.assert_not_called()
    assert len(df) == 1


@patch("stonks.services.cache.fetch_history")
def test_daily_refetches_when_stale(mock_fetch, db):
    upsert_prices(
        db,
        "AAPL",
        [
            {
                "date": "2023-01-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 1000000,
            },
        ],
    )
    mock_fetch.return_value = _make_df()
    df = get_history(db, "AAPL", "1mo", "1d")
    mock_fetch.assert_called_once()
    assert len(df) == 5
