from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stonks.services.stock_data import (
    batch_fetch_history,
    currency_format,
    fetch_currencies,
    fetch_history,
    fetch_info,
    fetch_names,
    populate_history_cache,
    search_tickers,
    validate_ticker,
)
from stonks.ui.workers import PriceUpdateWorker


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


# ── fetch_history ────────────────────────────────────────────────────────────


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
def test_fetch_history_caches_result(mock_ticker_cls, mock_history_df):
    mock_ticker_cls.return_value.history.return_value = mock_history_df
    fetch_history("AAPL", "1mo", "1d")
    fetch_history("AAPL", "1mo", "1d")
    mock_ticker_cls.return_value.history.assert_called_once()


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_history_cache_is_keyed_by_period(mock_ticker_cls, mock_history_df):
    mock_ticker_cls.return_value.history.return_value = mock_history_df
    fetch_history("AAPL", "1mo", "1d")
    fetch_history("AAPL", "1y", "1d")
    assert mock_ticker_cls.return_value.history.call_count == 2


@patch("stonks.services.stock_data.time.monotonic")
@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_history_refetches_after_ttl(mock_ticker_cls, mock_time, mock_history_df):
    mock_ticker_cls.return_value.history.return_value = mock_history_df
    mock_time.return_value = 0.0
    fetch_history("AAPL", "1mo", "1d")
    mock_time.return_value = 61.0  # past _HISTORY_TTL of 60s
    fetch_history("AAPL", "1mo", "1d")
    assert mock_ticker_cls.return_value.history.call_count == 2


# ── fetch_info ───────────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_info_returns_dict(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {"marketCap": 3_000_000_000_000, "trailingPE": 32.5}
    info = fetch_info("AAPL")
    assert info["marketCap"] == 3_000_000_000_000
    assert info["trailingPE"] == 32.5


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_info_caches_result(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {"symbol": "AAPL"}
    fetch_info("AAPL")
    fetch_info("AAPL")
    mock_ticker_cls.assert_called_once()


@patch("stonks.services.stock_data.time.monotonic")
@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_info_refetches_after_ttl(mock_ticker_cls, mock_time):
    mock_ticker_cls.return_value.info = {"symbol": "AAPL"}
    mock_time.return_value = 0.0
    fetch_info("AAPL")
    mock_time.return_value = 301.0  # past _INFO_TTL of 300s
    fetch_info("AAPL")
    assert mock_ticker_cls.call_count == 2


# ── populate_history_cache ───────────────────────────────────────────────────


@patch("stonks.services.stock_data.yf.Ticker")
def test_populate_history_cache_is_found_by_fetch_history(mock_ticker_cls, mock_history_df):
    populate_history_cache({"AAPL": mock_history_df}, "1mo", "1d")
    df = fetch_history("AAPL", "1mo", "1d")
    mock_ticker_cls.assert_not_called()
    assert len(df) == 5


# ── batch_fetch_history ──────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yf.download")
def test_batch_fetch_history_single_ticker_flat_columns(mock_download):
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    mock_download.return_value = pd.DataFrame(
        {"Close": [100.0, 101.0, 102.0], "Volume": [1e6, 1e6, 1e6]}, index=dates
    )
    results = batch_fetch_history(["AAPL"], "1mo", "1d")
    assert "AAPL" in results
    assert list(results["AAPL"]["Close"]) == [100.0, 101.0, 102.0]


@patch("stonks.services.stock_data.yf.download")
def test_batch_fetch_history_multi_ticker(mock_download):
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    mi = pd.MultiIndex.from_tuples(
        [("Close", "AAPL"), ("Close", "MSFT"), ("Volume", "AAPL"), ("Volume", "MSFT")]
    )
    data = [[100.0, 200.0, 1e6, 2e6]] * 3
    mock_download.return_value = pd.DataFrame(data, index=dates, columns=mi)
    results = batch_fetch_history(["AAPL", "MSFT"], "1mo", "1d")
    assert set(results.keys()) == {"AAPL", "MSFT"}
    assert results["AAPL"]["Close"].iloc[0] == 100.0
    assert results["MSFT"]["Close"].iloc[0] == 200.0


@patch("stonks.services.stock_data.yf.download")
def test_batch_fetch_history_empty_returns_empty_dict(mock_download):
    mock_download.return_value = pd.DataFrame()
    assert batch_fetch_history(["AAPL"], "1mo", "1d") == {}


def test_batch_fetch_history_no_tickers_returns_empty_dict():
    assert batch_fetch_history([], "1mo", "1d") == {}


@patch("stonks.services.stock_data.yf.download")
def test_batch_fetch_history_skips_missing_tickers(mock_download):
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    mi = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Volume", "AAPL")])
    data = [[100.0, 1e6]] * 3
    mock_download.return_value = pd.DataFrame(data, index=dates, columns=mi)
    results = batch_fetch_history(["AAPL", "MSFT"], "1mo", "1d")
    assert "AAPL" in results
    assert "MSFT" not in results


# ── validate_ticker ──────────────────────────────────────────────────────────


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
def test_validate_ticker_exception_returns_false(mock_ticker_cls):
    mock_ticker_cls.side_effect = Exception("Network error")
    assert validate_ticker("AAPL") is False


# ── currency_format ──────────────────────────────────────────────────────────


def test_currency_format_prefix_currencies():
    assert currency_format("USD") == ("$", "")
    assert currency_format("GBP") == ("£", "")
    assert currency_format("JPY") == ("¥", "")
    assert currency_format("HKD") == ("HK$", "")


def test_currency_format_suffix_currencies():
    assert currency_format("EUR") == ("", "€")
    assert currency_format("SEK") == ("", "kr")
    assert currency_format("DKK") == ("", "kr")
    assert currency_format("GBp") == ("", "p")


def test_currency_format_unknown_returns_empty():
    assert currency_format("XYZ") == ("", "")
    assert currency_format("") == ("", "")


# ── PriceUpdateWorker retry ─────────────────────────────────────────────────


@patch("stonks.ui.workers.time.sleep")
@patch("stonks.ui.workers.fetch_prices")
def test_price_update_worker_retries_transient_failures(mock_fetch, mock_sleep, qtbot):
    mock_fetch.side_effect = [
        ({"AAPL": (150.0, 1.5)}, set()),
        ({}, set()),
        ({"MSFT": (400.0, 2.0)}, set()),
    ]

    worker = PriceUpdateWorker(["AAPL", "MSFT"])
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args[0] == {"AAPL": (150.0, 1.5), "MSFT": (400.0, 2.0)}
    assert mock_fetch.call_count == 3
    assert mock_sleep.call_args_list[0].args[0] == 0.5
    assert mock_sleep.call_args_list[1].args[0] == 1.0


@patch("stonks.ui.workers.time.sleep")
@patch("stonks.ui.workers.fetch_prices")
def test_price_update_worker_does_not_retry_no_data_tickers(mock_fetch, mock_sleep, qtbot):
    mock_fetch.return_value = ({"AAPL": (150.0, 1.5)}, {"DELISTED"})

    worker = PriceUpdateWorker(["AAPL", "DELISTED"])
    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args[0] == {"AAPL": (150.0, 1.5)}
    assert mock_fetch.call_count == 1
    mock_sleep.assert_not_called()


# ── search_tickers ──────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yf.Search")
def test_search_tickers_returns_results(mock_search):
    mock_search.return_value.quotes = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchDisp": "NASDAQ"},
        {"symbol": "AAPL.MX", "shortname": "Apple Inc.", "exchDisp": "Mexico"},
    ]
    results = search_tickers("AAPL")
    assert len(results) == 2
    assert results[0]["symbol"] == "AAPL"
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["exchange"] == "NASDAQ"


@patch("stonks.services.stock_data.yf.Search")
def test_search_tickers_skips_entries_without_symbol(mock_search):
    mock_search.return_value.quotes = [
        {"shortname": "No symbol here"},
        {"symbol": "MSFT", "shortname": "Microsoft"},
    ]
    results = search_tickers("test")
    assert len(results) == 1
    assert results[0]["symbol"] == "MSFT"


@patch("stonks.services.stock_data.yf.Search")
def test_search_tickers_respects_max_results(mock_search):
    mock_search.return_value.quotes = [
        {"symbol": f"T{i}", "shortname": f"Ticker {i}"} for i in range(10)
    ]
    results = search_tickers("test", max_results=3)
    assert len(results) == 3


# ── fetch_names ─────────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_names_returns_names(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {"longName": "Apple Inc."}
    names = fetch_names(["AAPL"])
    assert names == {"AAPL": "Apple Inc."}


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_names_uses_shortname_fallback(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {"shortName": "Apple"}
    names = fetch_names(["AAPL"])
    assert names == {"AAPL": "Apple"}


@patch("stonks.services.stock_data.yf.Ticker")
def test_fetch_names_skips_tickers_with_no_name(mock_ticker_cls):
    mock_ticker_cls.return_value.info = {}
    names = fetch_names(["AAPL"])
    assert names == {}


# ── fetch_currencies ────────────────────────────────────────────────────────


def test_fetch_currencies_returns_cached_currencies():
    from stonks.services import stock_data

    stock_data._info_cache["AAPL"] = ({"currency": "USD"}, 0.0)
    result = fetch_currencies(["AAPL"])
    assert result == {"AAPL": "USD"}


def test_fetch_currencies_skips_uncached_tickers():
    result = fetch_currencies(["AAPL"])
    assert result == {}
