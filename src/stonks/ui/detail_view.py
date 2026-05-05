from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from stonks.ui.workers import InfoWorker

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


def format_number(value, fmt_type: str) -> str:
    if value is None:
        return "--"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "--"

    if fmt_type == "currency":
        return f"${value:,.2f}"
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
            return f"${value / 1_000_000_000_000:.2f}T"
        elif value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:,.0f}"
    return str(value)


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


class DetailView(QWidget):
    info_received = Signal(str, str, str, str)

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

        for col_stats in STAT_COLUMNS:
            for _, key, fmt_type in col_stats:
                value = info.get(key)
                if key in self._value_labels:
                    self._value_labels[key].setText(format_number(value, fmt_type))

        name = info.get("longName") or info.get("shortName") or ticker
        exchange = info.get("fullExchangeName") or info.get("exchange") or ""
        currency = info.get("currency") or ""
        self.info_received.emit(ticker, name, exchange, currency)
