import threading
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

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
