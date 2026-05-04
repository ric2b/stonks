import sqlite3
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from stonks.config import TIME_RANGES
from stonks.ui.workers import HistoryWorker


class ChartWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._current_ticker = None
        self._current_period = "1M"
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 16px; padding: 8px;")
        layout.addWidget(self.header_label)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(8, 0, 8, 0)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for i, label in enumerate(TIME_RANGES.keys()):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(50)
            if label == "1M":
                btn.setChecked(True)
            self.button_group.addButton(btn, i)
            button_layout.addWidget(btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.button_group.idClicked.connect(self._on_range_changed)

        date_axis = pg.DateAxisItem(orientation="bottom")
        self.plot_widget = pg.PlotWidget(axisItems={"bottom": date_axis})
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.hideButtons()
        layout.addWidget(self.plot_widget)

        self._status_label = pg.TextItem(anchor=(0.5, 0.5))
        self._status_label.setVisible(False)
        self.plot_widget.addItem(self._status_label)

        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#888", width=1))
        self._vline.setVisible(False)
        self.plot_widget.addItem(self._vline)

        self._crosshair_label = pg.TextItem(anchor=(0, 1))
        self._crosshair_label.setVisible(False)
        self.plot_widget.addItem(self._crosshair_label)

        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self._timestamps = None
        self._prices = None

    def update_chart(self, ticker: str, period: str | None = None):
        self._current_ticker = ticker
        if period is not None:
            self._current_period = period

        self.header_label.setText(f"<b>{ticker}</b>")
        self._show_status("Loading...")

        period_key = self._current_period
        yf_period, yf_interval = TIME_RANGES[period_key]

        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()

        self._worker = HistoryWorker(ticker, yf_period, yf_interval)
        self._worker.finished.connect(self._on_data_received)
        self._worker.error.connect(self._on_data_error)
        self._worker.start()

    def set_range_by_index(self, index: int):
        labels = list(TIME_RANGES.keys())
        if 0 <= index < len(labels):
            btn = self.button_group.button(index)
            if btn:
                btn.setChecked(True)
                self._on_range_changed(index)

    def _show_status(self, text: str):
        self.plot_widget.clear()
        self.plot_widget.addItem(self._vline)
        self.plot_widget.addItem(self._crosshair_label)
        self.plot_widget.addItem(self._status_label)
        self._vline.setVisible(False)
        self._crosshair_label.setVisible(False)
        self._timestamps = None
        self._prices = None

        self._status_label.setText(text)
        self._status_label.setPos(0, 0)
        self._status_label.setVisible(True)
        self.plot_widget.setXRange(-1, 1)
        self.plot_widget.setYRange(-1, 1)

    def _on_range_changed(self, button_id: int):
        labels = list(TIME_RANGES.keys())
        self._current_period = labels[button_id]
        if self._current_ticker:
            self.update_chart(self._current_ticker)

    def _on_data_received(self, df):
        self._status_label.setVisible(False)
        self.plot_widget.clear()
        self.plot_widget.addItem(self._vline)
        self.plot_widget.addItem(self._crosshair_label)
        self.plot_widget.addItem(self._status_label)

        if df.empty:
            self._show_status("No data available")
            return

        timestamps = np.array([ts.timestamp() for ts in df.index])
        prices = df["Close"].values.astype(float)

        mask = ~np.isnan(prices)
        timestamps = timestamps[mask]
        prices = prices[mask]

        if len(prices) == 0:
            self._show_status("No data available")
            return

        self._timestamps = timestamps
        self._prices = prices

        is_up = prices[-1] >= prices[0]
        color = (76, 175, 80) if is_up else (244, 67, 54)
        pen = pg.mkPen(color=color, width=2)
        brush = pg.mkBrush(color=(*color, 40))

        self.plot_widget.plot(
            self._timestamps, prices, pen=pen, fillLevel=float(prices.min()), brush=brush
        )
        self.plot_widget.autoRange()

        current_price = prices[-1]
        change = prices[-1] - prices[0]
        change_pct = (change / prices[0]) * 100
        sign = "+" if change >= 0 else ""
        price_color = "#4CAF50" if change >= 0 else "#F44336"
        self.header_label.setText(
            f"<b>{self._current_ticker}</b> &nbsp; ${current_price:.2f} "
            f'<span style="color:{price_color}">{sign}{change_pct:.2f}%</span>'
        )

    def _on_data_error(self, error: str):
        self._show_status("Failed to load data. Check your connection.")

    def _on_mouse_moved(self, pos):
        if self._timestamps is None or self._prices is None:
            return

        vb = self.plot_widget.plotItem.vb
        if not vb.sceneBoundingRect().contains(pos):
            return

        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()

        idx = int(np.searchsorted(self._timestamps, x))
        idx = max(0, min(idx, len(self._timestamps) - 1))

        self._vline.setPos(float(self._timestamps[idx]))
        self._vline.setVisible(True)

        dt = datetime.fromtimestamp(int(self._timestamps[idx]))
        price = self._prices[idx]
        self._crosshair_label.setText(f"{dt.strftime('%b %d, %Y')}  ${price:.2f}")
        self._crosshair_label.setPos(float(self._timestamps[idx]), float(price))
        self._crosshair_label.setVisible(True)
