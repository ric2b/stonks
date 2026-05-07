from datetime import datetime, timezone

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from stonks.services.stock_data import currency_format
from stonks.ui.workers import InfoWorker, NewsWorker, shutdown_workers

STAT_COLUMNS = [
    [
        ("Open", "regularMarketOpen", "currency"),
        ("High", "dayHigh", "currency"),
        ("Low", "dayLow", "currency"),
    ],
    [
        ("Volume", "volume", "number"),
        ("P/E", "trailingPE", "decimal"),
        ("Mkt Cap", "marketCap", "large_number"),
    ],
    [
        ("52W H", "fiftyTwoWeekHigh", "currency"),
        ("52W L", "fiftyTwoWeekLow", "currency"),
        ("Avg Vol", "averageVolume", "number"),
    ],
    [
        ("Yield", "dividendYield", "percent"),
        ("Beta", "beta", "decimal"),
        ("EPS", "trailingEps", "currency"),
    ],
]


def format_number(value, fmt_type: str, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return "--"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "--"

    if fmt_type == "currency":
        return f"{prefix}{value:,.2f}{suffix}"
    elif fmt_type == "percent":
        return f"{value * 100:.2f}%"
    elif fmt_type == "decimal":
        return f"{value:.2f}"
    elif fmt_type == "number":
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:,.0f}"
    elif fmt_type == "large_number":
        if value >= 1_000_000_000_000:
            return f"{prefix}{value / 1_000_000_000_000:.2f}T{suffix}"
        elif value >= 1_000_000_000:
            return f"{prefix}{value / 1_000_000_000:.2f}B{suffix}"
        elif value >= 1_000_000:
            return f"{prefix}{value / 1_000_000:.1f}M{suffix}"
        elif value >= 1_000:
            return f"{prefix}{value / 1_000:.1f}K{suffix}"
        return f"{prefix}{value:,.0f}{suffix}"
    return str(value)


def _relative_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except (ValueError, TypeError):
        return ""


class _StatPair(QWidget):
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(8)

        self._label = QLabel(label_text)
        self._label.setObjectName("statLabel")

        self.value_label = QLabel("--")
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self._label)
        row.addStretch()
        row.addWidget(self.value_label)
        layout.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: rgba(255,255,255,20); border: none; max-height: 1px;")
        layout.addWidget(sep)


class _NewsItem(QWidget):
    def __init__(self, title: str, provider: str, time_ago: str, url: str, parent=None):
        super().__init__(parent)
        self._url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("newsTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        meta_parts = [p for p in (provider, time_ago) if p]
        if meta_parts:
            meta_label = QLabel(" · ".join(meta_parts))
            meta_label.setObjectName("newsMeta")
            layout.addWidget(meta_label)

    def mousePressEvent(self, event):
        if self._url and event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self._url))
        super().mousePressEvent(event)


class NewsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_ticker = None
        self._workers: list[NewsWorker] = []

        self.setStyleSheet("background-color: #242424;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._news_header = QLabel("News")
        self._news_header.setObjectName("newsHeader")
        self._news_header.setContentsMargins(24, 8, 24, 0)
        self._news_header.hide()
        outer.addWidget(self._news_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._news_container = QWidget()
        self._news_layout = QVBoxLayout(self._news_container)
        self._news_layout.setContentsMargins(24, 0, 24, 12)
        self._news_layout.setSpacing(0)
        self._news_layout.addStretch()

        scroll.setWidget(self._news_container)
        outer.addWidget(scroll, 1)

    def shutdown(self):
        shutdown_workers(self._workers)

    def update_news(self, ticker: str):
        self._current_ticker = ticker
        self._clear_news()

        worker = NewsWorker(ticker)
        worker.finished.connect(lambda items, t=ticker: self._on_news_received(items, t))
        worker.finished.connect(lambda _items, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def _clear_news(self):
        self._news_header.hide()
        while self._news_layout.count() > 1:
            item = self._news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_news_received(self, items: list[dict], ticker: str):
        if ticker != self._current_ticker:
            return
        self._clear_news()
        if not items:
            return
        self._news_header.show()
        for i, article in enumerate(items):
            time_ago = _relative_time(article.get("pubDate", ""))
            news_item = _NewsItem(
                article.get("title", ""),
                article.get("provider", ""),
                time_ago,
                article.get("url", ""),
            )
            self._news_layout.insertWidget(self._news_layout.count() - 1, news_item)
            if i < len(items) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(
                    "background-color: rgba(255,255,255,20); border: none; max-height: 1px;"
                )
                self._news_layout.insertWidget(self._news_layout.count() - 1, sep)


class DetailView(QWidget):
    info_received = Signal(str, str, str, str)
    price_received = Signal(str, float, float)
    market_state_changed = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_ticker = None
        self._workers: list[InfoWorker] = []
        self._value_labels: dict[str, QLabel] = {}

        self.setStyleSheet("background-color: #242424;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "background-color: rgba(255,255,255,20); border: none;"
            " max-height: 1px; min-height: 1px;"
        )
        outer.addWidget(sep)

        cols_widget = QWidget()
        cols_layout = QHBoxLayout(cols_widget)
        cols_layout.setContentsMargins(24, 4, 24, 12)
        cols_layout.setSpacing(20)

        for col_stats in STAT_COLUMNS:
            col = QWidget()
            col_inner = QVBoxLayout(col)
            col_inner.setContentsMargins(0, 0, 0, 0)
            col_inner.setSpacing(0)
            for label_text, key, fmt_type in col_stats:
                pair = _StatPair(label_text)
                self._value_labels[key] = pair.value_label
                col_inner.addWidget(pair)
            col_inner.addStretch()
            cols_layout.addWidget(col, 1)

        outer.addWidget(cols_widget, 1)

    def shutdown(self):
        shutdown_workers(self._workers)

    def update_detail(self, ticker: str):
        self._current_ticker = ticker
        for lbl in self._value_labels.values():
            lbl.setText("--")

        worker = InfoWorker(ticker)
        worker.finished.connect(lambda info, t=ticker: self._on_info_received(info, t))
        worker.finished.connect(lambda _info, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def _on_info_received(self, info: dict, ticker: str):
        if ticker != self._current_ticker:
            return

        currency_code = info.get("currency") or ""
        pre, suf = currency_format(currency_code)

        for col_stats in STAT_COLUMNS:
            for _, key, fmt_type in col_stats:
                value = info.get(key)
                if key in self._value_labels:
                    if fmt_type in ("currency", "large_number"):
                        self._value_labels[key].setText(format_number(value, fmt_type, pre, suf))
                    else:
                        self._value_labels[key].setText(format_number(value, fmt_type))

        name = info.get("longName") or info.get("shortName") or ticker
        exchange = info.get("fullExchangeName") or info.get("exchange") or ""
        self.info_received.emit(ticker, name, exchange, currency_code)

        price = info.get("regularMarketPrice")
        if price is not None:
            change_pct = info.get("regularMarketChangePercent")
            if change_pct is None:
                prev = info.get("regularMarketPreviousClose")
                if prev and prev != 0:
                    change_pct = ((price - prev) / prev) * 100
            self.price_received.emit(ticker, float(price), float(change_pct or 0.0))

        market_state = info.get("marketState") or "CLOSED"
        delay = int(info.get("exchangeDataDelayedBy") or 0)
        self.market_state_changed.emit(market_state, delay)
