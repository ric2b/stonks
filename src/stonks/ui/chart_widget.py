import sqlite3
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
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
        self._workers: list[HistoryWorker] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────
        self._header = QWidget()
        self._header.setStyleSheet("background-color: #242424;")
        header_layout = QVBoxLayout(self._header)
        header_layout.setContentsMargins(24, 16, 24, 8)
        header_layout.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        self.symbol_label = QLabel()
        self.symbol_label.setObjectName("chartSymbol")
        self.company_label = QLabel()
        self.company_label.setObjectName("chartCompany")
        self.company_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_row.addWidget(self.symbol_label)
        name_row.addWidget(self.company_label, 1)
        header_layout.addLayout(name_row)

        price_row = QHBoxLayout()
        price_row.setSpacing(12)
        self.price_label = QLabel()
        self.price_label.setObjectName("chartPrice")
        self.change_label = QLabel()
        self.change_label.setObjectName("chartChange")
        price_row.addWidget(self.price_label)
        price_row.addWidget(self.change_label)
        price_row.addStretch()
        header_layout.addLayout(price_row)

        self.exchange_label = QLabel()
        self.exchange_label.setObjectName("chartExchange")
        header_layout.addWidget(self.exchange_label)

        layout.addWidget(self._header)

        # ── Range tab pill bar ──────────────────────────────
        tab_wrap = QWidget()
        tab_wrap.setStyleSheet("background-color: #242424;")
        tab_wrap_layout = QHBoxLayout(tab_wrap)
        tab_wrap_layout.setContentsMargins(24, 6, 24, 10)

        self._tab_bar = QFrame()
        self._tab_bar.setObjectName("rangeTabBar")
        tab_bar_layout = QHBoxLayout(self._tab_bar)
        tab_bar_layout.setContentsMargins(3, 3, 3, 3)
        tab_bar_layout.setSpacing(2)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        for i, label in enumerate(TIME_RANGES.keys()):
            btn = QPushButton(label)
            btn.setObjectName("rangeBtn")
            btn.setCheckable(True)
            if label == self._current_period:
                btn.setChecked(True)
            self.button_group.addButton(btn, i)
            tab_bar_layout.addWidget(btn)

        self.button_group.idClicked.connect(self._on_range_changed)

        tab_wrap_layout.addWidget(self._tab_bar)
        tab_wrap_layout.addStretch()
        layout.addWidget(tab_wrap)

        # ── Price chart ─────────────────────────────────────
        date_axis = pg.DateAxisItem(orientation="bottom")
        self.price_widget = pg.PlotWidget(axisItems={"bottom": date_axis})
        self.price_widget.setBackground("#242424")
        self.price_widget.setMenuEnabled(False)
        self.price_widget.showGrid(x=True, y=True, alpha=0.12)
        self.price_widget.hideButtons()
        self.price_widget.getAxis("left").setTextPen(pg.mkPen("#6b6b6b"))
        self.price_widget.getAxis("bottom").setTextPen(pg.mkPen("#6b6b6b"))
        self.price_widget.getAxis("left").setPen(pg.mkPen("#303030"))
        self.price_widget.getAxis("bottom").setPen(pg.mkPen("#303030"))
        layout.addWidget(self.price_widget, stretch=1)

        # ── Volume chart ────────────────────────────────────
        self.vol_widget = pg.PlotWidget()
        self.vol_widget.setBackground("#242424")
        self.vol_widget.setMaximumHeight(50)
        self.vol_widget.setMenuEnabled(False)
        self.vol_widget.hideButtons()
        self.vol_widget.hideAxis("left")
        self.vol_widget.hideAxis("bottom")
        self.vol_widget.setMouseEnabled(x=False, y=False)
        self.vol_widget.setVisible(False)
        layout.addWidget(self.vol_widget)

        # ── Overlay items ───────────────────────────────────
        self._status_label = pg.TextItem(anchor=(0.5, 0.5), color="#9e9e9e")
        self._status_label.setVisible(False)
        self.price_widget.addItem(self._status_label)

        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#555", width=1))
        self._vline.setVisible(False)
        self.price_widget.addItem(self._vline)

        self._crosshair_label = pg.TextItem(anchor=(0, 1), color="#9e9e9e")
        self._crosshair_label.setVisible(False)
        self.price_widget.addItem(self._crosshair_label)

        self.price_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self._timestamps = None
        self._prices = None

    def update_chart(self, ticker: str, period: str | None = None):
        self._current_ticker = ticker
        if period is not None:
            self._current_period = period

        self.symbol_label.setText(ticker)
        self.company_label.setText("")
        self.price_label.setText("--")
        self.change_label.setText("")
        self.exchange_label.setText("")
        self._show_status("Loading...")

        yf_period, yf_interval = TIME_RANGES[self._current_period]
        worker = HistoryWorker(ticker, yf_period, yf_interval)
        worker.finished.connect(lambda df, t=ticker: self._on_data_received(df, t))
        worker.error.connect(lambda _err, t=ticker: self._on_data_error(t))
        worker.finished.connect(lambda _df, w=worker: self._workers.remove(w))
        worker.error.connect(lambda _err, w=worker: self._workers.remove(w))
        self._workers.append(worker)
        worker.start()

    def set_company_info(self, ticker: str, name: str, exchange: str, currency: str):
        if ticker != self._current_ticker:
            return
        self.company_label.setText(name)
        self.exchange_label.setText(f"{exchange} · {currency}")

    def set_range_by_index(self, index: int):
        labels = list(TIME_RANGES.keys())
        if 0 <= index < len(labels):
            btn = self.button_group.button(index)
            if btn:
                btn.setChecked(True)
                self._on_range_changed(index)

    def _show_status(self, text: str):
        self.price_widget.clear()
        self.price_widget.addItem(self._vline)
        self.price_widget.addItem(self._crosshair_label)
        self.price_widget.addItem(self._status_label)
        self._vline.setVisible(False)
        self._crosshair_label.setVisible(False)
        self._timestamps = None
        self._prices = None

        self.vol_widget.clear()
        self.vol_widget.setVisible(False)

        self._status_label.setText(text)
        self._status_label.setPos(0, 0)
        self._status_label.setVisible(True)
        self.price_widget.setXRange(-1, 1)
        self.price_widget.setYRange(-1, 1)

    def _on_range_changed(self, button_id: int):
        labels = list(TIME_RANGES.keys())
        self._current_period = labels[button_id]
        if self._current_ticker:
            self.update_chart(self._current_ticker)

    def _on_data_received(self, df, ticker: str):
        if ticker != self._current_ticker:
            return

        self._status_label.setVisible(False)
        self.price_widget.clear()
        self.price_widget.addItem(self._vline)
        self.price_widget.addItem(self._crosshair_label)
        self.price_widget.addItem(self._status_label)

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
        color = (76, 210, 120) if is_up else (255, 107, 122)
        pen = pg.mkPen(color=color, width=1.75)
        brush = pg.mkBrush(color=(*color, 40))

        self.price_widget.plot(
            self._timestamps, prices, pen=pen, fillLevel=float(prices.min()), brush=brush
        )
        self.price_widget.autoRange()

        current_price = prices[-1]
        change_abs = prices[-1] - prices[0]
        change_pct = (change_abs / prices[0]) * 100
        sign = "+" if change_abs >= 0 else ""
        price_color = "#4cd278" if change_abs >= 0 else "#ff6b7a"

        self.price_label.setText(f"${current_price:,.2f}")
        self.change_label.setText(
            f'<span style="color:{price_color}">{sign}{change_abs:.2f} '
            f"({sign}{change_pct:.2f}%)</span>"
        )

        # Volume bars
        if "Volume" in df.columns:
            volumes = df["Volume"].values.astype(float)
            volumes = volumes[mask]
            has_vol = np.any(volumes > 0)
            if has_vol:
                self.vol_widget.clear()
                vol_color = (*color, 90)
                bar_width = (timestamps[-1] - timestamps[0]) / max(len(timestamps) * 1.2, 1)
                bars = pg.BarGraphItem(
                    x=timestamps,
                    height=volumes,
                    width=bar_width,
                    brush=pg.mkBrush(vol_color),
                    pen=pg.mkPen(None),
                )
                self.vol_widget.addItem(bars)
                self.vol_widget.setXLink(self.price_widget)
                self.vol_widget.setVisible(True)
            else:
                self.vol_widget.setVisible(False)
        else:
            self.vol_widget.setVisible(False)

    def _on_data_error(self, ticker: str):
        if ticker != self._current_ticker:
            return
        self._show_status("Failed to load data.")

    def _on_mouse_moved(self, pos):
        if self._timestamps is None or self._prices is None:
            return

        vb = self.price_widget.plotItem.vb
        if not vb.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._crosshair_label.setVisible(False)
            return

        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()

        idx = int(np.searchsorted(self._timestamps, x))
        idx = max(0, min(idx, len(self._timestamps) - 1))

        self._vline.setPos(float(self._timestamps[idx]))
        self._vline.setVisible(True)

        dt = datetime.fromtimestamp(int(self._timestamps[idx]))
        price = self._prices[idx]
        self._crosshair_label.setText(f"{dt.strftime('%b %d, %Y')}  ${price:,.2f}")
        self._crosshair_label.setPos(float(self._timestamps[idx]), float(price))
        self._crosshair_label.setVisible(True)
