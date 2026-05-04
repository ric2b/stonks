from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stonks.services.stock_data import fetch_history, fetch_info, validate_ticker


@pytest.fixture
def mock_history_df():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [103.0, 104.0, 105.0, 106.0, 107.0],
            "Volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        },
        index=dates,
    )


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_history_returns_dataframe(mock_ticker_cls, mock_history_df):
    mock_ticker_cls.return_value.history.return_value = mock_history_df
    df = fetch_history("AAPL", "1mo", "1d")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5
    assert "Close" in df.columns
    mock_ticker_cls.return_value.history.assert_called_once_with(period="1mo", interval="1d")


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_history_raises_on_empty(mock_ticker_cls):
    mock_ticker_cls.return_value.history.return_value = pd.DataFrame()
    with pytest.raises(ValueError, match="No data returned"):
        fetch_history("INVALID", "1mo", "1d")


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_info_returns_dict(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {"marketCap": 3_000_000_000_000, "trailingPE": 32.5}
    info = fetch_info("AAPL")
    assert info["marketCap"] == 3_000_000_000_000
    assert info["trailingPE"] == 32.5


@patch("stonks.services.stock_data.yf.Ticker")
def test_validate_ticker_valid(mock_ticker_cls):
    fast_info = MagicMock()
    fast_info.last_price = 198.50
    mock_ticker_cls.return_value.fast_info = fast_info
    assert validate_ticker("AAPL") is True


@patch("stonks.services.stock_data.yf.Ticker")
def test_validate_ticker_invalid(mock_ticker_cls):
    fast_info = MagicMock()
    fast_info.last_price = None
    mock_ticker_cls.return_value.fast_info = fast_info
    assert validate_ticker("XYZXYZ") is False


@patch("stonks.services.stock_data.yf.Ticker")
def test_validate_ticker_exception(mock_ticker_cls):
    mock_ticker_cls.return_value.fast_info = property(lambda s: (_ for _ in ()).throw(Exception()))
    mock_ticker_cls.side_effect = Exception("Network error")
    assert validate_ticker("AAPL") is False
