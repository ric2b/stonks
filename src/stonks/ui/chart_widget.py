import sqlite3
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stonks.config import INTRADAY_INTERVALS, TIME_RANGES
from stonks.models.database import set_setting
from stonks.services.stock_data import currency_format
from stonks.ui.workers import HistoryWorker

_DASH = Qt.PenStyle.DashLine
_DAILY_INTERVALS = {"1d", "5d", "1wk", "1mo", "3mo"}


def _price_decimals(prices: np.ndarray) -> int:
    if len(prices) == 0:
        return 2
    spread = float(prices.max() - prices.min())
    if spread == 0:
        return 2
    if spread < 0.1:
        return 5
    if spread < 1:
        return 4
    if spread < 10:
        return 3
    return 2


def _fill_closed_market_gaps(
    timestamps: np.ndarray, prices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Insert synthetic points to hold the previous close flat across market-closed gaps.

    Any gap more than 1.5× the median interval is treated as a closure (weekends,
    holidays). A point is inserted one second before the next open at the prior
    close price, producing a horizontal step instead of a diagonal line.
    """
    if len(timestamps) < 2:
        return timestamps, prices

    diffs = np.diff(timestamps)
    threshold = np.median(diffs) * 1.6

    gap_indices = np.where(diffs > threshold)[0]
    if len(gap_indices) == 0:
        return timestamps, prices

    new_ts = list(timestamps)
    new_px = list(prices)
    for i in sorted(gap_indices, reverse=True):
        new_ts.insert(i + 1, timestamps[i + 1] - 1.0)
        new_px.insert(i + 1, prices[i])

    return np.array(new_ts), np.array(new_px)


class ChartWidget(QWidget):
    range_changed = Signal(str)  # period label, e.g. "1M"

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._current_ticker = None
        self._current_period = "1M"
        self._workers: list[HistoryWorker] = []
        self._is_up = True

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5 * 60 * 1000)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("chartHeader")
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
        tab_wrap.setObjectName("tabWrap")
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

        # ── Hover date slot (between tab bar and chart) ────
        self._hover_date = QLabel()
        self._hover_date.setObjectName("chartHoverDate")
        self._hover_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hover_date.setFixedHeight(18)
        layout.addWidget(self._hover_date)

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
        self.price_widget.setMouseEnabled(x=False, y=False)
        self.price_widget.plotItem.vb.setAutoVisible(y=True)
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

        # ── Crosshair: vertical + horizontal lines ──────────
        self._status_label = pg.TextItem(anchor=(0.5, 0.5), color="#9e9e9e")
        self._status_label.setVisible(False)
        self.price_widget.addItem(self._status_label)

        self._vline = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen("#666", width=1, style=_DASH)
        )
        self._vline.setVisible(False)
        self.price_widget.addItem(self._vline)

        self._hline = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen("#666", width=1, style=_DASH)
        )
        self._hline.setVisible(False)
        self.price_widget.addItem(self._hline)

        # Tracking dot on the chart line
        self._track_dot = pg.ScatterPlotItem(
            size=9,
            pen=pg.mkPen("#242424", width=2),
            brush=pg.mkBrush("#4cd278"),
        )
        self._track_dot.setVisible(False)
        self.price_widget.addItem(self._track_dot)

        self._hover_price = QLabel(self.price_widget)
        self._hover_price.setObjectName("chartHoverPrice")
        self._hover_price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._hover_price.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hover_price.setVisible(False)

        # ── Drag-to-compare state ──────────────────────────────
        self._drag_active = False
        self._drag_start_idx = None

        self._drag_anchor = pg.ScatterPlotItem(
            size=9,
            pen=pg.mkPen("#242424", width=2),
            brush=pg.mkBrush("#ffffff"),
        )
        self._drag_anchor.setZValue(20)
        self._drag_anchor.setVisible(False)
        self.price_widget.addItem(self._drag_anchor)

        self._drag_region = pg.PlotDataItem(pen=pg.mkPen(None))
        self._drag_region.setZValue(5)
        self._drag_region.setVisible(False)
        self.price_widget.addItem(self._drag_region)

        self.price_widget.viewport().installEventFilter(self)
        self.price_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self._timestamps = None
        self._prices = None
        self._price_fmt_decimals = 2
        self._currency_prefix = ""
        self._currency_suffix = ""

    def update_chart(self, ticker: str, period: str | None = None):
        ticker_changed = ticker != self._current_ticker
        self._current_ticker = ticker
        if period is not None:
            self._current_period = period

        self.symbol_label.setText(ticker)
        if ticker_changed:
            self.company_label.setText("")
            self.exchange_label.setText("")
            self._currency_prefix = ""
            self._currency_suffix = ""
        self.price_label.setText("--")
        self.change_label.setText("")
        self._show_status("Loading...")

        yf_period, yf_interval = TIME_RANGES[self._current_period]
        if yf_interval in INTRADAY_INTERVALS:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
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
        self._currency_prefix, self._currency_suffix = currency_format(currency)
        if self._prices is not None and len(self._prices) > 0:
            self._update_price_display()

    def set_range_by_index(self, index: int):
        labels = list(TIME_RANGES.keys())
        if 0 <= index < len(labels):
            btn = self.button_group.button(index)
            if btn:
                btn.setChecked(True)
                self._on_range_changed(index)

    def step_range(self, delta: int):
        labels = list(TIME_RANGES.keys())
        current = labels.index(self._current_period)
        self.set_range_by_index(max(0, min(current + delta, len(labels) - 1)))

    def shutdown(self):
        self._refresh_timer.stop()
        for w in self._workers:
            w.quit()
            w.wait(2000)
        self._workers.clear()

    def _hide_crosshair(self):
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self._track_dot.setVisible(False)
        self._hover_date.setText("")
        self._hover_price.setVisible(False)
        if self._drag_active:
            self._end_drag()

    def _show_status(self, text: str):
        self._hide_crosshair()
        self.price_widget.clear()
        self.price_widget.addItem(self._vline)
        self.price_widget.addItem(self._hline)
        self.price_widget.addItem(self._track_dot)
        self.price_widget.addItem(self._status_label)
        self.price_widget.addItem(self._drag_anchor)
        self.price_widget.addItem(self._drag_region)
        self.price_widget.plotItem.vb.setLimits(xMin=None, xMax=None, maxXRange=None)
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
        set_setting(self.conn, "last_period", self._current_period)
        _, interval = TIME_RANGES[self._current_period]
        if interval in INTRADAY_INTERVALS:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
        self.range_changed.emit(self._current_period)
        if self._current_ticker:
            self.update_chart(self._current_ticker)

    def _auto_refresh(self):
        if self._current_ticker:
            self.update_chart(self._current_ticker)

    def _update_price_display(self):
        if self._prices is None or len(self._prices) == 0:
            return
        d = self._price_fmt_decimals
        pre = self._currency_prefix
        suf = self._currency_suffix
        current_price = float(self._prices[-1])
        change_abs = float(self._prices[-1] - self._prices[0])
        change_pct = (change_abs / float(self._prices[0])) * 100
        sign = "+" if change_abs >= 0 else "−"
        abs_change = abs(change_abs)
        abs_pct = abs(change_pct)
        price_color = "#4cd278" if change_abs >= 0 else "#ff6b7a"

        self.price_label.setText(f"{pre}{current_price:,.{d}f}{suf}")
        self.change_label.setText(
            f'<span style="color:{price_color}">{sign}{pre}{abs_change:.{d}f}{suf} '
            f"({sign}{abs_pct:.2f}%)</span>"
        )

    def _on_data_received(self, df, ticker: str):
        if ticker != self._current_ticker:
            return

        self._status_label.setVisible(False)
        self.price_widget.clear()
        self.price_widget.addItem(self._vline)
        self.price_widget.addItem(self._hline)
        self.price_widget.addItem(self._track_dot)
        self.price_widget.addItem(self._status_label)
        self.price_widget.addItem(self._drag_anchor)
        self.price_widget.addItem(self._drag_region)

        if self._drag_active:
            self._end_drag()

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
        self._price_fmt_decimals = _price_decimals(prices)

        plot_ts, plot_prices = _fill_closed_market_gaps(timestamps, prices)

        self._is_up = prices[-1] >= prices[0]
        color = (76, 210, 120) if self._is_up else (255, 107, 122)
        pen = pg.mkPen(color=color, width=1.75)
        brush = pg.mkBrush(color=(*color, 40))

        self.price_widget.plot(
            plot_ts, plot_prices, pen=pen, fillLevel=float(plot_prices.min()), brush=brush
        )
        self.price_widget.autoRange()

        # Constrain x zoom-out to the data extent
        x_span = float(timestamps[-1]) - float(timestamps[0])
        buf = x_span * 0.01
        self.price_widget.plotItem.vb.setLimits(
            xMin=float(timestamps[0]) - buf,
            xMax=float(timestamps[-1]) + buf,
            maxXRange=x_span + buf * 2,
        )

        # Update track dot colour to match line
        self._track_dot.setBrush(pg.mkBrush(color))

        self._update_price_display()

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
            if not self._drag_active:
                self._hide_crosshair()
            return

        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()

        idx = int(np.searchsorted(self._timestamps, x))
        idx = max(0, min(idx, len(self._timestamps) - 1))

        ts = float(self._timestamps[idx])
        price = float(self._prices[idx])

        left_pressed = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if left_pressed and not self._drag_active:
            self._drag_active = True
            self._drag_start_idx = idx
            self._drag_anchor.setData([ts], [price])
            self._drag_anchor.setVisible(True)

        self._vline.setPos(ts)
        self._vline.setVisible(True)

        self._track_dot.setData([ts], [price])
        self._track_dot.setVisible(True)

        _, interval = TIME_RANGES[self._current_period]
        d = self._price_fmt_decimals
        pre = self._currency_prefix
        suf = self._currency_suffix
        pw = self.price_widget

        if self._drag_active and self._drag_start_idx is not None:
            start_ts = float(self._timestamps[self._drag_start_idx])
            start_price = float(self._prices[self._drag_start_idx])

            self._hline.setVisible(False)

            start_dt = datetime.fromtimestamp(int(start_ts))
            end_dt = datetime.fromtimestamp(int(ts))
            fmt = "%b %d, %Y" if interval in _DAILY_INTERVALS else "%b %d, %Y  %H:%M"
            change = price - start_price
            pct = (change / start_price) * 100 if start_price != 0 else 0.0
            sign = "+" if change >= 0 else "−"
            color = "#4cd278" if change >= 0 else "#ff6b7a"
            self._track_dot.setBrush(pg.mkBrush(color))
            self._hover_date.setText(
                f"{start_dt.strftime(fmt)} – {end_dt.strftime(fmt)}"
                f"&nbsp;&nbsp;&nbsp;"
                f'<span style="color:{color}; font-weight:600">'
                f"{sign}{pre}{abs(change):,.{d}f}{suf}"
                f" ({sign}{abs(pct):.2f}%)</span>"
            )
            lo, hi = sorted([self._drag_start_idx, idx])
            region_ts = self._timestamps[lo : hi + 1]
            region_prices = self._prices[lo : hi + 1]
            region_ts, region_prices = _fill_closed_market_gaps(region_ts, region_prices)
            rgb = (76, 210, 120) if change >= 0 else (255, 107, 122)
            self._drag_region.setData(
                x=region_ts,
                y=region_prices,
                pen=pg.mkPen(color=rgb, width=1.75),
                fillLevel=float(self._prices.min()),
                brush=pg.mkBrush((*rgb, 80)),
            )
            self._drag_region.setVisible(True)

            self._hover_price.setVisible(False)
        else:
            self._hline.setPos(price)
            self._hline.setVisible(True)

            dt = datetime.fromtimestamp(int(ts))
            if interval in _DAILY_INTERVALS:
                self._hover_date.setText(dt.strftime("%b %d, %Y"))
            else:
                self._hover_date.setText(dt.strftime("%b %d, %Y  %H:%M"))

            scene_pos = vb.mapViewToScene(pg.Point(ts, price))
            widget_y = self.price_widget.mapFromScene(scene_pos).y()
            lbl_h, lbl_w = 18, 100
            y_clamped = max(0, min(int(widget_y) - lbl_h // 2, pw.height() - lbl_h))
            self._hover_price.setGeometry(pw.width() - lbl_w - 2, y_clamped, lbl_w, lbl_h)
            self._hover_price.setText(f"{pre}{price:,.{d}f}{suf}")
            self._hover_price.setVisible(True)
            self._hover_price.raise_()

    def eventFilter(self, obj, event):
        if obj is self.price_widget.viewport():
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
                and self._drag_active
            ):
                self._end_drag()
        return super().eventFilter(obj, event)

    def _end_drag(self):
        self._drag_active = False
        self._drag_start_idx = None
        self._drag_anchor.setVisible(False)
        self._drag_region.setVisible(False)
        dot_color = (76, 210, 120) if self._is_up else (255, 107, 122)
        self._track_dot.setBrush(pg.mkBrush(dot_color))
