import threading
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from stonks.config import TIME_RANGES
from stonks.models.database import add_ticker
from stonks.services import yahoo_api
from stonks.ui.main_window import MainWindow
from stonks.ui.workers import run_async

QUOTE = {
    "symbol": "AAPL",
    "regularMarketPrice": 150.0,
    "regularMarketChangePercent": 1.5,
    "longName": "Apple Inc.",
    "currency": "USD",
}

CHART = {
    "timestamps": [1704067200 + i * 3600 for i in range(10)],
    "open": [100.0] * 10,
    "high": [110.0] * 10,
    "low": [90.0] * 10,
    "close": [100.0 + i for i in range(10)],
    "volume": [1000] * 10,
    "meta": {},
}


@pytest.fixture
def yahoo():
    with (
        patch.object(yahoo_api, "batch_quote", return_value={"AAPL": QUOTE}) as batch_quote,
        patch.object(yahoo_api, "fetch_quote_summary", side_effect=lambda _t: {"beta": 1.2}),
        patch.object(yahoo_api, "fetch_chart", return_value=CHART),
        patch.object(yahoo_api, "fetch_news", return_value=[]),
    ):
        yield batch_quote


def _sidebar_row(window: MainWindow, row: int = 0):
    item = window.watchlist.list_widget.item(row)
    return window.watchlist.list_widget.itemWidget(item)


def test_run_async_delivers_result_on_main_thread(qtbot):
    received = []
    run_async(
        lambda x: x * 2,
        21,
        on_done=lambda r: received.append((r, threading.current_thread())),
    )
    qtbot.waitUntil(lambda: bool(received), timeout=2000)
    assert received == [(42, threading.main_thread())]


def test_run_async_delivers_errors_on_main_thread(qtbot):
    errors = []

    def boom():
        raise ValueError("nope")

    run_async(boom, on_error=lambda e: errors.append((str(e), threading.current_thread())))
    qtbot.waitUntil(lambda: bool(errors), timeout=2000)
    assert errors == [("nope", threading.main_thread())]


def test_window_loads_prices_chart_and_details(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    window = MainWindow(db)
    qtbot.addWidget(window)

    row = _sidebar_row(window)
    qtbot.waitUntil(lambda: row.price_label.text() == "$150.00", timeout=3000)
    qtbot.waitUntil(lambda: window.chart.price_label.text().startswith("$109.0"), timeout=3000)
    qtbot.waitUntil(lambda: window.detail_view._value_labels["beta"].text() == "1.20", timeout=3000)
    assert row.name_label.text() == "Apple Inc."


def test_price_refresh_recovers_after_network_failure(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    yahoo.side_effect = OSError("network down")
    window = MainWindow(db)
    qtbot.addWidget(window)
    watchlist = window.watchlist
    qtbot.waitUntil(lambda: not watchlist._price_refresh_pending, timeout=3000)
    assert _sidebar_row(window).price_label.text() == "--"

    yahoo.side_effect = None
    watchlist._refresh()
    qtbot.waitUntil(lambda: _sidebar_row(window).price_label.text() == "$150.00", timeout=3000)


def test_price_refresh_skips_tick_while_previous_is_in_flight(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    release = threading.Event()
    calls = []

    def slow_fetch_prices(tickers):
        calls.append(tickers)
        release.wait(2)
        return {"AAPL": (150.0, 1.5)}

    with patch("stonks.ui.watchlist.fetch_prices", slow_fetch_prices):
        window = MainWindow(db)
        qtbot.addWidget(window)
        window.watchlist._refresh_prices()
        window.watchlist._refresh_prices()
        release.set()
        qtbot.waitUntil(lambda: not window.watchlist._price_refresh_pending, timeout=3000)
    assert len(calls) == 1


def test_selecting_ticker_survives_chart_failure(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    with patch.object(yahoo_api, "fetch_chart", side_effect=OSError("timeout")):
        window = MainWindow(db)
        qtbot.addWidget(window)
        qtbot.waitUntil(
            lambda: window.chart._status_label.toPlainText() == "Failed to load data.",
            timeout=3000,
        )
    assert window.watchlist.list_widget.currentItem().data(Qt.ItemDataRole.UserRole) == "AAPL"


def test_failed_background_chart_refresh_keeps_current_plot(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    window = MainWindow(db)
    qtbot.addWidget(window)
    chart = window.chart
    qtbot.waitUntil(lambda: chart.price_label.text().startswith("$109.0"), timeout=3000)

    with patch("stonks.ui.chart_widget.fetch_history", side_effect=OSError("timeout")):
        chart._auto_refresh()
        qtbot.waitUntil(lambda: chart._pending_request is None, timeout=3000)

    assert chart.price_label.text().startswith("$109.0")
    assert not chart._status_label.isVisible()


def test_slow_chart_response_for_previous_ticker_is_ignored(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    release_aapl = threading.Event()
    msft_chart = {**CHART, "close": [400.0 + i for i in range(10)]}

    def fetch_chart(ticker, range_, interval):
        if ticker == "AAPL":
            release_aapl.wait(2)
            return CHART
        return msft_chart

    with patch.object(yahoo_api, "fetch_chart", side_effect=fetch_chart):
        window = MainWindow(db)
        qtbot.addWidget(window)
        window.watchlist.select_ticker("MSFT")
        qtbot.waitUntil(lambda: "409.0" in window.chart.price_label.text(), timeout=3000)
        release_aapl.set()
        qtbot.wait(200)

    assert "409.0" in window.chart.price_label.text()


def test_switching_to_cached_ticker_renders_without_loading_state(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    window = MainWindow(db)
    qtbot.addWidget(window)
    chart, detail = window.chart, window.detail_view
    qtbot.waitUntil(lambda: detail._value_labels["beta"].text() == "1.20", timeout=3000)
    window.watchlist.select_ticker("MSFT")
    qtbot.waitUntil(lambda: chart._prices is not None and chart._pending_request is None)
    qtbot.waitUntil(lambda: detail._current_ticker == "MSFT")
    qtbot.wait(100)

    window.watchlist.select_ticker("AAPL")

    # No event-loop turn has run, so anything shown came from the cache synchronously.
    assert chart.price_label.text().startswith("$109.0")
    assert not chart._status_label.isVisible()
    assert detail._value_labels["beta"].text() == "1.20"


def test_uncached_ticker_shows_loading_spinner(qtbot, db, yahoo):
    add_ticker(db, "AAPL")
    release = threading.Event()
    with patch.object(
        yahoo_api, "fetch_chart", side_effect=lambda *a, **k: (release.wait(2), CHART)[1]
    ):
        window = MainWindow(db)
        qtbot.addWidget(window)
        chart = window.chart
        assert chart.price_label.text() == "--"
        assert "Loading" in chart._status_label.toPlainText()
        first_frame = chart._status_label.toPlainText()
        qtbot.waitUntil(lambda: chart._status_label.toPlainText() != first_frame, timeout=1000)
        release.set()
        qtbot.waitUntil(lambda: not chart._status_label.isVisible(), timeout=3000)
        assert not chart._spinner_timer.isActive()


def test_switching_to_longer_cached_range_shows_the_whole_range(qtbot, db, yahoo):
    import numpy as np

    from stonks.services.stock_data import HistoryData, populate_history_cache

    day = 86400.0
    one_month = HistoryData(np.arange(30) * day, np.linspace(100, 110, 30), np.ones(30))
    three_months = HistoryData(np.arange(90) * day, np.linspace(90, 110, 90), np.ones(90))
    populate_history_cache({"AAPL": one_month}, "1mo", "30m")
    populate_history_cache({"AAPL": three_months}, "3mo", "1h")
    add_ticker(db, "AAPL")
    window = MainWindow(db)
    qtbot.addWidget(window)
    chart = window.chart
    chart.set_range_by_index(list(TIME_RANGES).index("1M"))

    chart.set_range_by_index(list(TIME_RANGES).index("3M"))

    x_min, x_max = chart.price_widget.viewRange()[0]
    assert x_min <= 0 and x_max >= 89 * day

    chart.set_range_by_index(list(TIME_RANGES).index("1M"))

    x_min, x_max = chart.price_widget.viewRange()[0]
    assert x_min >= -day and x_max <= 30 * day
