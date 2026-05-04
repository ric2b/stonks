from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from stonks.ui.workers import InfoWorker

STATS = [
    ("Open", "regularMarketOpen", "currency"),
    ("High", "dayHigh", "currency"),
    ("Low", "dayLow", "currency"),
    ("Close", "previousClose", "currency"),
    ("Volume", "volume", "large_number"),
    ("Avg Volume", "averageVolume", "large_number"),
    ("Market Cap", "marketCap", "large_number"),
    ("P/E Ratio", "trailingPE", "decimal"),
    ("EPS", "trailingEps", "currency"),
    ("52w High", "fiftyTwoWeekHigh", "currency"),
    ("52w Low", "fiftyTwoWeekLow", "currency"),
    ("Div Yield", "dividendYield", "percent"),
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


class DetailView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._value_labels = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        for i, (label_text, key, _) in enumerate(STATS):
            row = i % 6
            col_offset = (i // 6) * 2

            name_label = QLabel(label_text)
            name_label.setStyleSheet("color: gray; font-size: 12px;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

            value_label = QLabel("--")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

            grid.addWidget(name_label, row, col_offset)
            grid.addWidget(value_label, row, col_offset + 1)

            self._value_labels[key] = value_label

    def update_detail(self, ticker: str):
        for label in self._value_labels.values():
            label.setText("--")

        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()

        self._worker = InfoWorker(ticker)
        self._worker.finished.connect(self._on_info_received)
        self._worker.start()

    def _on_info_received(self, info: dict):
        for _, key, fmt_type in STATS:
            value = info.get(key)
            if key in self._value_labels:
                self._value_labels[key].setText(format_number(value, fmt_type))
