import sqlite3

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from stonks.config import REFRESH_INTERVAL_MS
from stonks.models.database import add_ticker, get_watchlist, remove_ticker, reorder_watchlist
from stonks.ui.workers import PriceUpdateWorker, ValidateWorker


class WatchlistItemWidget(QWidget):
    def __init__(self, ticker: str, parent=None):
        super().__init__(parent)
        self.ticker = ticker

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.ticker_label = QLabel(f"<b>{ticker}</b>")
        self.price_label = QLabel("--")
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.ticker_label)
        layout.addStretch()
        layout.addWidget(self.price_label)

    def update_price(self, price: float, change_pct: float):
        color = "#4CAF50" if change_pct >= 0 else "#F44336"
        sign = "+" if change_pct >= 0 else ""
        self.price_label.setText(
            f'${price:.2f} <span style="color:{color}">{sign}{change_pct:.2f}%</span>'
        )


class WatchlistWidget(QWidget):
    ticker_selected = Signal(str)

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._workers = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Add ticker...")
        self.search_input.returnPressed.connect(self._on_add_ticker)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list_widget)

        self._load_watchlist()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_prices)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)
        self._refresh_prices()

    def _load_watchlist(self):
        self.list_widget.clear()
        for entry in get_watchlist(self.conn):
            self._add_list_item(entry["ticker"])

    def _add_list_item(self, ticker: str):
        item = QListWidgetItem(self.list_widget)
        widget = WatchlistItemWidget(ticker)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, ticker)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _on_add_ticker(self):
        ticker = self.search_input.text().strip().upper()
        if not ticker:
            return
        self.search_input.setEnabled(False)
        worker = ValidateWorker(ticker)
        worker.finished.connect(self._on_ticker_validated)
        worker.error.connect(self._on_validate_error)
        self._workers.append(worker)
        worker.start()

    def _on_ticker_validated(self, valid: bool, ticker: str):
        self.search_input.setEnabled(True)
        if valid:
            add_ticker(self.conn, ticker)
            self._add_list_item(ticker)
            self.search_input.clear()
            self._refresh_prices()
        else:
            self.search_input.selectAll()

    def _on_validate_error(self, error: str):
        self.search_input.setEnabled(True)

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        ticker = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        remove_action = menu.addAction("Remove from watchlist")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == remove_action:
            remove_ticker(self.conn, ticker)
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def _on_selection_changed(self, current, previous):
        if current is not None:
            ticker = current.data(Qt.ItemDataRole.UserRole)
            self.ticker_selected.emit(ticker)

    def _on_rows_moved(self):
        tickers = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tickers.append(item.data(Qt.ItemDataRole.UserRole))
        reorder_watchlist(self.conn, tickers)

    def _refresh_prices(self):
        tickers = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tickers.append(item.data(Qt.ItemDataRole.UserRole))
        if not tickers:
            return
        worker = PriceUpdateWorker(tickers)
        worker.finished.connect(self._on_prices_updated)
        self._workers.append(worker)
        worker.start()

    def _on_prices_updated(self, prices: dict):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ticker = item.data(Qt.ItemDataRole.UserRole)
            widget = self.list_widget.itemWidget(item)
            if ticker in prices and widget is not None:
                price, change_pct = prices[ticker]
                widget.update_price(price, change_pct)

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def remove_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        ticker = item.data(Qt.ItemDataRole.UserRole)
        remove_ticker(self.conn, ticker)
        self.list_widget.takeItem(self.list_widget.row(item))
