import sqlite3

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
from stonks.ui.workers import PriceUpdateWorker, SearchWorker, ValidateWorker


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
        self.price_label.setText(f"{price:,.2f}")
        color = "#4cd278" if change_pct >= 0 else "#ff6b7a"
        bg_color = "rgba(76, 210, 120, 40)" if change_pct >= 0 else "rgba(255, 107, 122, 40)"
        sign = "+" if change_pct >= 0 else ""
        self.change_label.setText(f"{sign}{change_pct:.2f}%")
        self.change_label.setStyleSheet(
            f"color: {color}; background-color: {bg_color}; "
            "border-radius: 4px; padding: 1px 5px; font-size: 11px; font-weight: 600;"
        )


class _SearchResultWidget(QWidget):
    def __init__(self, symbol: str, name: str, exchange: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(8)
        sym_lbl = QLabel(symbol)
        sym_lbl.setObjectName("searchResultSymbol")
        exch_lbl = QLabel(exchange)
        exch_lbl.setObjectName("searchResultExchange")
        top.addWidget(sym_lbl)
        top.addStretch()
        top.addWidget(exch_lbl)
        layout.addLayout(top)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("searchResultName")
        layout.addWidget(name_lbl)


class WatchlistWidget(QWidget):
    ticker_selected = Signal(str)

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._workers = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        input_wrap = QWidget()
        input_wrap.setStyleSheet("background-color: #1c1c1c;")
        input_layout = QVBoxLayout(input_wrap)
        input_layout.setContentsMargins(10, 10, 10, 6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search or add ticker...")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        self.search_input.installEventFilter(self)
        input_layout.addWidget(self.search_input)
        layout.addWidget(input_wrap)

        results_wrap = QWidget()
        results_wrap.setStyleSheet("background-color: #1c1c1c;")
        results_layout = QVBoxLayout(results_wrap)
        results_layout.setContentsMargins(10, 0, 10, 6)
        self._results_list = QListWidget()
        self._results_list.setObjectName("searchResults")
        self._results_list.setVisible(False)
        self._results_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._results_list.installEventFilter(self)
        self._results_list.itemClicked.connect(self._on_result_clicked)
        results_layout.addWidget(self._results_list)
        layout.addWidget(results_wrap)

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

        self._load_watchlist()

        QApplication.instance().focusChanged.connect(self._on_focus_changed)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_prices)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)
        self._refresh_prices()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if obj is self.search_input:
                if event.key() == Qt.Key.Key_Down and self._results_list.isVisible():
                    self._results_list.setFocus()
                    if self._results_list.currentRow() < 0:
                        self._results_list.setCurrentRow(0)
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self._hide_results()
                    return True
            elif obj is self._results_list:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self._results_list.currentItem()
                    if item:
                        self._on_result_clicked(item)
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self._hide_results()
                    self.search_input.setFocus()
                    return True
                if event.key() == Qt.Key.Key_Up and self._results_list.currentRow() == 0:
                    self.search_input.setFocus()
                    return True
        return super().eventFilter(obj, event)

    def _on_focus_changed(self, old, new):
        if new not in (self.search_input, self._results_list):
            self._hide_results()

    def _on_text_changed(self, text):
        self._search_timer.stop()
        if not text.strip():
            self._hide_results()
            return
        self._search_timer.start()

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self._results_list.clear()
        loading = QListWidgetItem("Searching…")
        loading.setFlags(Qt.ItemFlag.NoItemFlags)
        self._results_list.addItem(loading)
        self._show_results()

        worker = SearchWorker(query)
        worker.finished.connect(self._on_search_results)
        worker.finished.connect(lambda _r, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def _on_search_results(self, results: list):
        if not self.search_input.text().strip():
            return
        self._results_list.clear()
        if not results:
            empty = QListWidgetItem("No results")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._results_list.addItem(empty)
        else:
            for r in results:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, r["symbol"])
                widget = _SearchResultWidget(r["symbol"], r["name"], r["exchange"])
                item.setSizeHint(widget.sizeHint())
                self._results_list.addItem(item)
                self._results_list.setItemWidget(item, widget)
        self._show_results()

    def _show_results(self):
        count = self._results_list.count()
        row_h = 52
        self._results_list.setFixedHeight(min(count, 5) * row_h + 6)
        self._results_list.setVisible(True)

    def _hide_results(self):
        self._results_list.setVisible(False)
        self._results_list.clear()
        self._search_timer.stop()

    def _on_result_clicked(self, item: QListWidgetItem):
        symbol = item.data(Qt.ItemDataRole.UserRole)
        if not symbol:
            return
        self._hide_results()
        self.search_input.clear()
        self._add_ticker_by_symbol(symbol)

    def _on_return_pressed(self):
        if self._results_list.isVisible() and self._results_list.count() > 0:
            item = self._results_list.currentItem() or self._results_list.item(0)
            if item:
                self._on_result_clicked(item)
                return
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
            self._add_ticker_by_symbol(ticker)
            self.search_input.clear()
        else:
            self.search_input.selectAll()

    def _on_validate_error(self, error: str):
        self.search_input.setEnabled(True)

    def _add_ticker_by_symbol(self, symbol: str):
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == symbol:
                self.list_widget.setCurrentRow(i)
                return
        add_ticker(self.conn, symbol)
        self._add_list_item(symbol)
        self._update_count()
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

    def select_ticker(self, ticker: str) -> bool:
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == ticker:
                self.list_widget.setCurrentRow(i)
                return True
        return False

    def _add_list_item(self, ticker: str):
        item = QListWidgetItem(self.list_widget)
        widget = WatchlistItemWidget(ticker)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, ticker)
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

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

    def get_tickers(self) -> list[str]:
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
        ]

    def shutdown(self):
        self.refresh_timer.stop()
        self._search_timer.stop()
        for w in self._workers:
            w.quit()
            w.wait(2000)
        self._workers.clear()

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
