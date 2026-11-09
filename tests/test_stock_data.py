from unittest.mock import patch

import numpy as np
import pytest

from stonks.services.stock_data import (
    HistoryData,
    batch_fetch_history,
    currency_format,
    fetch_history,
    fetch_info,
    fetch_names_and_currencies,
    fetch_prices,
    populate_history_cache,
    search_tickers,
    validate_ticker,
)


def _make_chart_response(closes=None, n=5):
    closes = closes or [103.0, 104.0, 105.0, 106.0, 107.0][:n]
    return {
        "timestamps": list(range(1704067200, 1704067200 + n * 86400, 86400)),
        "open": [100.0] * n,
        "high": [110.0] * n,
        "low": [99.0] * n,
        "close": closes,
        "volume": [1000000] * n,
        "meta": {},
    }


# ── fetch_history ────────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_returns_history_data(mock_chart):
    mock_chart.return_value = _make_chart_response()
    hd = fetch_history("AAPL", "1mo", "1d")
    assert isinstance(hd, HistoryData)
    assert not hd.empty
    assert len(hd.timestamps) == 5
    assert hd.close[-1] == 107.0
    mock_chart.assert_called_once_with("AAPL", range_="1mo", interval="1d")


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_raises_on_empty(mock_chart):
    mock_chart.return_value = None
    with pytest.raises(ValueError, match="No data returned"):
        fetch_history("INVALID", "1mo", "1d")


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_caches_result(mock_chart):
    mock_chart.return_value = _make_chart_response()
    fetch_history("AAPL", "1mo", "1d")
    fetch_history("AAPL", "1mo", "1d")
    mock_chart.assert_called_once()


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_cache_is_keyed_by_period(mock_chart):
    mock_chart.return_value = _make_chart_response()
    fetch_history("AAPL", "1mo", "1d")
    fetch_history("AAPL", "1y", "1d")
    assert mock_chart.call_count == 2


@patch("stonks.services.stock_data.time.monotonic")
@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_refetches_after_ttl(mock_chart, mock_time):
    mock_chart.return_value = _make_chart_response()
    mock_time.return_value = 0.0
    fetch_history("AAPL", "1mo", "1d")
    mock_time.return_value = 61.0
    fetch_history("AAPL", "1mo", "1d")
    assert mock_chart.call_count == 2


# ── fetch_info ───────────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.fetch_quote_summary")
@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_info_returns_dict(mock_quote, mock_summary):
    mock_quote.return_value = {"AAPL": {"marketCap": 3_000_000_000_000, "trailingPE": 32.5}}
    mock_summary.return_value = {"beta": 1.2}
    info = fetch_info("AAPL")
    assert info["marketCap"] == 3_000_000_000_000
    assert info["trailingPE"] == 32.5
    assert info["beta"] == 1.2


@patch("stonks.services.stock_data.yahoo_api.fetch_quote_summary")
@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_info_caches_result(mock_quote, mock_summary):
    mock_quote.return_value = {"AAPL": {"symbol": "AAPL"}}
    mock_summary.return_value = {}
    fetch_info("AAPL")
    fetch_info("AAPL")
    mock_quote.assert_called_once()


@patch("stonks.services.stock_data.time.monotonic")
@patch("stonks.services.stock_data.yahoo_api.fetch_quote_summary")
@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_info_refetches_after_ttl(mock_quote, mock_summary, mock_time):
    mock_quote.return_value = {"AAPL": {"symbol": "AAPL"}}
    mock_summary.return_value = {}
    mock_time.return_value = 0.0
    fetch_info("AAPL")
    mock_time.return_value = 301.0
    fetch_info("AAPL")
    assert mock_quote.call_count == 2


# ── populate_history_cache ───────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_populate_history_cache_is_found_by_fetch_history(mock_chart):
    hd = HistoryData(
        timestamps=np.arange(5, dtype=float),
        close=np.full(5, 100.0),
        volume=np.full(5, 1e6),
    )
    populate_history_cache({"AAPL": hd}, "1mo", "1d")
    result = fetch_history("AAPL", "1mo", "1d")
    mock_chart.assert_not_called()
    assert len(result.timestamps) == 5


# ── batch_fetch_history ──────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_batch_fetch_history_single_ticker(mock_chart):
    mock_chart.return_value = _make_chart_response(closes=[100.0, 101.0, 102.0], n=3)
    results = batch_fetch_history(["AAPL"], "1mo", "1d")
    assert "AAPL" in results
    assert list(results["AAPL"].close) == [100.0, 101.0, 102.0]


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_batch_fetch_history_multi_ticker(mock_chart):
    mock_chart.side_effect = [
        _make_chart_response(closes=[100.0, 101.0, 102.0], n=3),
        _make_chart_response(closes=[200.0, 201.0, 202.0], n=3),
    ]
    results = batch_fetch_history(["AAPL", "MSFT"], "1mo", "1d")
    assert set(results.keys()) == {"AAPL", "MSFT"}
    assert results["AAPL"].close[0] == 100.0
    assert results["MSFT"].close[0] == 200.0


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_batch_fetch_history_empty_returns_empty_dict(mock_chart):
    mock_chart.return_value = None
    assert batch_fetch_history(["AAPL"], "1mo", "1d") == {}


def test_batch_fetch_history_no_tickers_returns_empty_dict():
    assert batch_fetch_history([], "1mo", "1d") == {}


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_batch_fetch_history_skips_failed_tickers(mock_chart):
    mock_chart.side_effect = [
        _make_chart_response(closes=[100.0], n=1),
        Exception("network error"),
    ]
    results = batch_fetch_history(["AAPL", "MSFT"], "1mo", "1d")
    assert "AAPL" in results
    assert "MSFT" not in results


# ── validate_ticker ──────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.validate_ticker")
def test_validate_ticker_valid(mock_validate):
    mock_validate.return_value = True
    assert validate_ticker("AAPL") is True


@patch("stonks.services.stock_data.yahoo_api.validate_ticker")
def test_validate_ticker_invalid(mock_validate):
    mock_validate.return_value = False
    assert validate_ticker("XYZXYZ") is False


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


# ── search_tickers ──────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.search")
def test_search_tickers_returns_results(mock_search):
    mock_search.return_value = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchDisp": "NASDAQ"},
        {"symbol": "AAPL.MX", "shortname": "Apple Inc.", "exchDisp": "Mexico"},
    ]
    results = search_tickers("AAPL")
    assert len(results) == 2
    assert results[0]["symbol"] == "AAPL"
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["exchange"] == "NASDAQ"


@patch("stonks.services.stock_data.yahoo_api.search")
def test_search_tickers_skips_entries_without_symbol(mock_search):
    mock_search.return_value = [
        {"shortname": "No symbol here"},
        {"symbol": "MSFT", "shortname": "Microsoft"},
    ]
    results = search_tickers("test")
    assert len(results) == 1
    assert results[0]["symbol"] == "MSFT"


@patch("stonks.services.stock_data.yahoo_api.search")
def test_search_tickers_respects_max_results(mock_search):
    mock_search.return_value = [{"symbol": f"T{i}", "shortname": f"Ticker {i}"} for i in range(3)]
    results = search_tickers("test", max_results=3)
    assert len(results) == 3


# ── fetch_names_and_currencies ──────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_names_and_currencies_returns_both(mock_quote):
    mock_quote.return_value = {"AAPL": {"longName": "Apple Inc.", "currency": "USD"}}
    assert fetch_names_and_currencies(["AAPL"]) == ({"AAPL": "Apple Inc."}, {"AAPL": "USD"})


@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_names_and_currencies_uses_shortname_fallback(mock_quote):
    mock_quote.return_value = {"AAPL": {"shortName": "Apple"}}
    assert fetch_names_and_currencies(["AAPL"]) == ({"AAPL": "Apple"}, {})


@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_names_and_currencies_skips_unknown_tickers(mock_quote):
    mock_quote.return_value = {"AAPL": {}}
    assert fetch_names_and_currencies(["AAPL", "NOPE"]) == ({}, {})


@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_fetch_names_and_currencies_caches_per_ticker(mock_quote):
    mock_quote.return_value = {"AAPL": {"longName": "Apple Inc.", "currency": "USD"}}
    fetch_names_and_currencies(["AAPL"])
    fetch_names_and_currencies(["AAPL"])
    mock_quote.assert_called_once()


# ── fetch_prices ────────────────────────────────────────────────────────────


@patch("stonks.services.stock_data.yahoo_api.fetch_quote_summary")
@patch("stonks.services.stock_data.yahoo_api.batch_quote")
def test_price_refresh_does_not_replace_detail_info_with_quote_only_data(mock_quote, mock_summary):
    mock_quote.return_value = {"AAPL": {"regularMarketPrice": 150.0}}
    mock_summary.return_value = {"beta": 1.2}
    fetch_prices(["AAPL"])
    assert fetch_info("AAPL")["beta"] == 1.2


# ── TTLCache ────────────────────────────────────────────────────────────────


def test_ttl_cache_survives_concurrent_writers():
    import threading

    from stonks.services.stock_data import TTLCache

    cache = TTLCache(ttl=60.0)
    errors = []

    def writer(offset):
        try:
            for i in range(2000):
                cache.set((offset, i), i)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert cache.get((7, 1999)) == 1999


@patch("stonks.services.stock_data.time.monotonic")
def test_ttl_cache_without_ttl_never_expires(mock_time):
    from stonks.services.stock_data import TTLCache

    cache = TTLCache(ttl=None)
    mock_time.return_value = 0.0
    cache.set("AAPL", "Apple")
    mock_time.return_value = 1e9
    assert cache.get("AAPL") == "Apple"


@patch("stonks.services.stock_data.yahoo_api.fetch_chart")
def test_fetch_history_turns_missing_points_into_nan(mock_chart):
    response = _make_chart_response(n=3)
    response["close"] = [1.0, None, 3.0]
    response["volume"] = [10, None, 30]
    mock_chart.return_value = response
    hd = fetch_history("AAPL", "1mo", "1d")
    assert np.isnan(hd.close[1])
    assert np.isnan(hd.volume[1])
    assert hd.close[2] == 3.0
