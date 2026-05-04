import sqlite3

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
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

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(8, 8, 8, 0)
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

        period_key = self._current_period
        yf_period, yf_interval = TIME_RANGES[period_key]

        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()

        self._worker = HistoryWorker(ticker, yf_period, yf_interval)
        self._worker.finished.connect(self._on_data_received)
        self._worker.error.connect(self._on_data_error)
        self._worker.start()

    def _on_range_changed(self, button_id: int):
        labels = list(TIME_RANGES.keys())
        self._current_period = labels[button_id]
        if self._current_ticker:
            self.update_chart(self._current_ticker)

    def _on_data_received(self, df):
        self.plot_widget.clear()
        self.plot_widget.addItem(self._vline)
        self.plot_widget.addItem(self._crosshair_label)

        if df.empty:
            return

        timestamps = df.index.astype(np.int64) // 10**9
        prices = df["Close"].values.astype(float)

        self._timestamps = timestamps.values if hasattr(timestamps, "values") else timestamps
        self._prices = prices

        is_up = prices[-1] >= prices[0]
        color = (76, 175, 80) if is_up else (244, 67, 54)
        pen = pg.mkPen(color=color, width=2)
        brush = pg.mkBrush(color=(*color, 40))

        self.plot_widget.plot(
            self._timestamps, prices, pen=pen, fillLevel=float(prices.min()), brush=brush
        )
        self.plot_widget.autoRange()

    def _on_data_error(self, error: str):
        self.plot_widget.clear()
        self.plot_widget.addItem(self._vline)
        self.plot_widget.addItem(self._crosshair_label)
        self._timestamps = None
        self._prices = None

    def _on_mouse_moved(self, pos):
        if self._timestamps is None or self._prices is None:
            return

        vb = self.plot_widget.plotItem.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()

        idx = np.searchsorted(self._timestamps, x)
        idx = np.clip(idx, 0, len(self._timestamps) - 1)

        self._vline.setPos(self._timestamps[idx])
        self._vline.setVisible(True)

        from datetime import datetime

        dt = datetime.fromtimestamp(int(self._timestamps[idx]))
        price = self._prices[idx]
        self._crosshair_label.setText(f"{dt.strftime('%b %d, %Y')}  ${price:.2f}")
        self._crosshair_label.setPos(self._timestamps[idx], price)
        self._crosshair_label.setVisible(True)
