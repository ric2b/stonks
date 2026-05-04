import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QMainWindow, QSplitter, QVBoxLayout, QWidget

from stonks.ui.chart_widget import ChartWidget
from stonks.ui.detail_view import DetailView
from stonks.ui.watchlist import WatchlistWidget


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Stonks")
        self.setMinimumSize(900, 600)

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

    def _on_ticker_selected(self, ticker: str):
        self.chart.update_chart(ticker)
        self.detail_view.update_detail(ticker)
