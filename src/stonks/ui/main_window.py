import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from stonks.config import TIME_RANGES
from stonks.models.database import get_setting, set_setting
from stonks.ui.chart_widget import ChartWidget
from stonks.ui.detail_view import DetailView
from stonks.ui.watchlist import WatchlistWidget
from stonks.ui.workers import PrefetchWorker


class _StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        dot = QLabel()
        dot.setObjectName("liveDot")
        dot.setFixedSize(6, 6)
        layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        live = QLabel("LIVE")
        live.setObjectName("statusText")
        layout.addWidget(live)

        self._refresh_label = QLabel()
        self._refresh_label.setObjectName("statusText")
        layout.addWidget(self._refresh_label)

        layout.addStretch()

        self._msg_label = QLabel()
        self._msg_label.setObjectName("statusText")
        layout.addWidget(self._msg_label)

        sep = QLabel("·")
        sep.setObjectName("statusText")
        layout.addWidget(sep)

        yf = QLabel("Yahoo Finance")
        yf.setObjectName("statusText")
        layout.addWidget(yf)

        self._update_refresh_time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_refresh_time)
        self._timer.start(60_000)

        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(lambda: self._msg_label.setText(""))

    def _update_refresh_time(self):
        now = datetime.now().strftime("%H:%M")
        self._refresh_label.setText(f"Refreshed · {now}")

    def show_message(self, text: str, ms: int = 3000):
        self._msg_label.setText(text)
        self._msg_timer.start(ms)


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Stonks")
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.watchlist = WatchlistWidget(conn)
        splitter.addWidget(self.watchlist)

        right_pane = QWidget()
        right_pane.setStyleSheet("background-color: #242424;")
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.chart = ChartWidget(conn)
        right_layout.addWidget(self.chart, stretch=2)

        self.detail_view = DetailView()
        right_layout.addWidget(self.detail_view, stretch=1)

        splitter.addWidget(right_pane)
        splitter.setSizes([260, 640])

        main_layout.addWidget(splitter, stretch=1)

        self.status_bar = _StatusBar()
        main_layout.addWidget(self.status_bar)

        self._workers: list[PrefetchWorker] = []

        self.watchlist.ticker_selected.connect(self._on_ticker_selected)
        self.detail_view.info_received.connect(self.chart.set_company_info)
        self.detail_view.info_received.connect(self._on_info_received)
        self.chart.range_changed.connect(self._on_chart_range_changed)

        self._restore_session()
        self._setup_shortcuts()

        self.watchlist.list_widget.setFocus()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self.watchlist.focus_search)
        QShortcut(QKeySequence("/"), self, self.watchlist.focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.watchlist.remove_selected)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

        for i in range(len(TIME_RANGES)):
            QShortcut(
                QKeySequence(str(i + 1)),
                self,
                lambda idx=i: self.chart.set_range_by_index(idx),
            )

    def _restore_session(self):
        last_period = get_setting(self.conn, "last_period", "1M")
        period_labels = list(TIME_RANGES.keys())
        if last_period in period_labels:
            self.chart.set_range_by_index(period_labels.index(last_period))

        last_ticker = get_setting(self.conn, "last_ticker", "")
        if not self.watchlist.select_ticker(last_ticker):
            self.watchlist.select_first()

        yf_period, yf_interval = TIME_RANGES[self.chart._current_period]
        self._start_prefetch(yf_period, yf_interval)

    def _on_chart_range_changed(self, period_label: str):
        yf_period, yf_interval = TIME_RANGES[period_label]
        self._start_prefetch(yf_period, yf_interval)

    def _start_prefetch(self, yf_period: str, yf_interval: str):
        tickers = self.watchlist.get_tickers()
        if not tickers:
            return
        worker = PrefetchWorker(tickers, yf_period, yf_interval)
        worker.finished.connect(lambda w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def closeEvent(self, event):
        self.watchlist.shutdown()
        self.chart.shutdown()
        self.detail_view.shutdown()
        for w in self._workers:
            w.quit()
            w.wait(2000)
        super().closeEvent(event)

    def _on_info_received(self, ticker: str, name: str, exchange: str, currency: str):
        self.watchlist.update_name(ticker, name)

    def _on_ticker_selected(self, ticker: str):
        set_setting(self.conn, "last_ticker", ticker)
        self.chart.update_chart(ticker)
        self.detail_view.update_detail(ticker)
        self.status_bar.show_message(f"Loading {ticker}…", 3000)
