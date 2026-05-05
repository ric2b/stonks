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
    QPushButton,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(4)
        self.ticker_label = QLabel(ticker)
        self.ticker_label.setObjectName("sidebarTicker")
        self.price_label = QLabel("--")
        self.price_label.setObjectName("sidebarPrice")
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.ticker_label)
        top.addStretch()
        top.addWidget(self.price_label)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        self.change_label = QLabel("")
        self.change_label.setObjectName("sidebarChange")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom.addStretch()
        bottom.addWidget(self.change_label)
        layout.addLayout(bottom)

    def update_price(self, price: float, change_pct: float):
        self.price_label.setText(f"${price:,.2f}")
        color = "#4cd278" if change_pct >= 0 else "#ff6b7a"
        bg_color = "rgba(76, 210, 120, 40)" if change_pct >= 0 else "rgba(255, 107, 122, 40)"
        sign = "+" if change_pct >= 0 else ""
        self.change_label.setText(f"{sign}{change_pct:.2f}%")
        self.change_label.setStyleSheet(
            f"color: {color}; background-color: {bg_color}; "
            "border-radius: 4px; padding: 1px 5px; font-size: 11px; font-weight: 600;"
        )


class WatchlistWidget(QWidget):
    ticker_selected = Signal(str)

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._workers = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        input_wrap = QWidget()
        input_wrap.setStyleSheet("background-color: #1c1c1c;")
        input_layout = QVBoxLayout(input_wrap)
        input_layout.setContentsMargins(10, 10, 10, 6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Add ticker...")
        self.search_input.returnPressed.connect(self._on_add_ticker)
        input_layout.addWidget(self.search_input)
        layout.addWidget(input_wrap)

        header_wrap = QWidget()
        header_wrap.setStyleSheet("background-color: #1c1c1c;")
        header_layout = QHBoxLayout(header_wrap)
        header_layout.setContentsMargins(12, 4, 12, 6)
        self.header_label = QLabel("Watchlist · 0")
        self.header_label.setObjectName("watchlistHeader")
        header_layout.addWidget(self.header_label)
        layout.addWidget(header_wrap)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list_widget, 1)

        add_wrap = QWidget()
        add_wrap.setStyleSheet("background-color: #1c1c1c;")
        add_layout = QVBoxLayout(add_wrap)
        add_layout.setContentsMargins(10, 4, 10, 10)
        self.add_btn = QPushButton("+ Add ticker")
        self.add_btn.setObjectName("addTickerBtn")
        self.add_btn.clicked.connect(self.focus_search)
        add_layout.addWidget(self.add_btn)
        layout.addWidget(add_wrap)

        self._load_watchlist()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_prices)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)
        self._refresh_prices()

    def _update_count(self):
        self.header_label.setText(f"Watchlist · {self.list_widget.count()}")

    def _load_watchlist(self):
        self.list_widget.clear()
        for entry in get_watchlist(self.conn):
            self._add_list_item(entry["ticker"])
        self._update_count()

    def select_first(self):
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

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
        worker.finished.connect(lambda _v, _t, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def _on_ticker_validated(self, valid: bool, ticker: str):
        self.search_input.setEnabled(True)
        if valid:
            add_ticker(self.conn, ticker)
            self._add_list_item(ticker)
            self._update_count()
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
            self._update_count()

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
        worker.finished.connect(lambda _prices, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
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
        self._update_count()
