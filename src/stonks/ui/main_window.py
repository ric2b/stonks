import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QMainWindow, QSplitter, QStatusBar, QVBoxLayout, QWidget

from stonks.config import TIME_RANGES
from stonks.ui.chart_widget import ChartWidget
from stonks.ui.detail_view import DetailView
from stonks.ui.watchlist import WatchlistWidget


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Stonks")
        self.setMinimumSize(900, 600)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.watchlist = WatchlistWidget(conn)
        splitter.addWidget(self.watchlist)

        self.right_pane = QWidget()
        right_layout = QVBoxLayout(self.right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.chart = ChartWidget(conn)
        right_layout.addWidget(self.chart, stretch=2)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(separator)

        self.detail_view = DetailView()
        right_layout.addWidget(self.detail_view, stretch=1)

        splitter.addWidget(self.right_pane)

        splitter.setSizes([250, 650])
        self.setCentralWidget(splitter)

        self.watchlist.ticker_selected.connect(self._on_ticker_selected)

        self._setup_shortcuts()

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

    def _on_ticker_selected(self, ticker: str):
        self.chart.update_chart(ticker)
        self.detail_view.update_detail(ticker)
        self.status_bar.showMessage(f"Loading {ticker}...", 3000)
