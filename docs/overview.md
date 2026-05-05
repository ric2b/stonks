# Stonks — Overview

Desktop stock-tracking app for Linux/macOS, inspired by the macOS Stocks app.  
GPL-3.0 · Python 3.14 · PySide6 · PyQtGraph · yfinance · SQLite

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI framework | PySide6 (Qt6) |
| Charts | PyQtGraph |
| Market data | yfinance |
| Persistence | SQLite via raw `sqlite3` |
| Dependency management | uv (`uv.lock` committed) |
| Lint / format | ruff |

---

## Architecture

```
src/stonks/
├── main.py                  Entry point: QApplication, SIGINT handler, MainWindow
├── config.py                Constants: DB path, TIME_RANGES, INTRADAY_INTERVALS
├── models/
│   └── database.py          SQLite schema + CRUD helpers
├── services/
│   └── stock_data.py        yfinance wrappers with in-memory TTL cache + batch fetch
└── ui/
    ├── main_window.py       Top-level window: splitter, status bar, shortcuts, session restore, prefetch
    ├── watchlist.py         Left sidebar: live search, price refresh, drag-reorder
    ├── chart_widget.py      Price + volume chart, range tabs, crosshair, auto-refresh
    ├── detail_view.py       Stats grid (Open / High / Low / Vol / P/E / Mkt Cap / …)
    ├── workers.py           QThread workers for all network calls
    └── style.py             Adwaita dark QSS stylesheet
```

### Component layout

```
MainWindow
├── QSplitter
│   ├── WatchlistWidget          (left pane, ~260px)
│   └── right pane
│       ├── ChartWidget          (stretch 2)
│       └── DetailView           (stretch 1)
└── _StatusBar                   (fixed 24px, bottom)
```

---

## Data Flow

1. **Ticker selection** — `WatchlistWidget` emits `ticker_selected(str)`.
2. **MainWindow** receives it, saves `last_ticker` to the settings table, then fans out to:
   - `ChartWidget.update_chart(ticker)` — spawns a `HistoryWorker` (usually hits the in-memory cache)
   - `DetailView.update_detail(ticker)` — spawns an `InfoWorker` (usually hits the in-memory cache)
3. **Workers** run in `QThread`, call yfinance, and emit a signal back on the main thread.  
   All workers are kept in a `_workers: list` on their parent widget to prevent garbage collection mid-run.
4. **Company info round-trip** — once `InfoWorker` finishes, `DetailView` emits `info_received(ticker, name, exchange, currency)`. `MainWindow` forwards this to `ChartWidget.set_company_info()` to fill the chart header without a second network call.

### Prefetch

On startup and whenever the time range changes, `MainWindow` spawns a `PrefetchWorker` that batch-fetches the current period's data for **all watchlist tickers at once** using `yf.download`. Results are stored directly into the in-memory history cache. By the time the user clicks any ticker, the data is already cached and the chart renders without a loading delay.

### Time ranges

Defined in `config.TIME_RANGES` (ordered dict, also drives the tab bar and keyboard shortcuts):

| Label | yfinance period | Interval |
|---|---|---|
| 1D | 1d | 5m |
| 1W | 5d | 30m |
| 1M | 1mo | 1d |
| 3M | 3mo | 1d |
| 6M | 6mo | 1d |
| YTD | ytd | 1d |
| 1Y | 1y | 1d |
| 5Y | 5y | 1wk |
| 10Y | 10y | 1wk |
| ALL | max | 1mo |

`INTRADAY_INTERVALS = {"5m", "30m"}` — the auto-refresh timer and prefetch logic use this to decide whether to keep refreshing on a schedule.

---

## Caching

### In-memory TTL (`services/stock_data.py`)

Two module-level dicts keyed by ticker (or `(ticker, period, interval)`) with a monotonic timestamp:

| Function | TTL | Purpose |
|---|---|---|
| `fetch_info()` | 5 minutes | Eliminates company name / stats pop-in when re-selecting a ticker |
| `fetch_history()` | 60 seconds | Avoids re-fetching chart data when switching back and forth |

Stale entries are evicted from `_history_cache` on each write, keeping memory bounded.

The prefetch system populates `_history_cache` via `populate_history_cache()`, which uses the same keys and TTL as `fetch_history()`. Individual `HistoryWorker` calls then find the data already present.

### Settings (`models/database.py`)

A `settings(key, value)` key-value table stores session state:

- `last_ticker` — restored on startup; falls back to the first watchlist item
- `last_period` — restored on startup; falls back to `"1M"`

The `settings` table is created by `init_db` alongside the watchlist table, so existing databases are upgraded automatically on first run.

---

## Price Refresh

Watchlist prices are refreshed every **60 seconds** via a `QTimer` in `WatchlistWidget`. Each tick spawns a `PriceUpdateWorker` that calls `yf.download` once for **all tickers** in a single batch request, computes the day-over-day change percentage, and updates the sidebar labels.

The chart auto-refreshes every **5 minutes** when the active period is intraday (1D or 1W). The timer starts and stops automatically as you switch ranges.

---

## Chart Details

- **Gap filling** — consecutive timestamps more than 1.6× the median interval apart (weekends, holidays) get a synthetic point inserted just before the next open, holding the previous close flat. This prevents diagonal lines across non-trading periods.
- **Zoom** — x-axis only (`setMouseEnabled(x=True, y=False)`). Y auto-scales to the visible x range (`setAutoVisible(y=True)`). Zoom-out is capped at the data extent via `setLimits(maxXRange=...)`.
- **Crosshair** — vertical + horizontal dashed lines, a tracking dot on the price line, a date label floating above the chart area (parent: `ChartWidget`, never overlaps data), and a price label pinned to the right edge at the cursor's y position.
- **Volume** — rendered as a bar chart below the price chart, x-linked so it pans/zooms in sync. Hidden when no volume data is present.
- **Prices** — displayed without a currency symbol; yfinance returns values in the ticker's native currency.

---

## Shutdown

`MainWindow.closeEvent` calls `shutdown()` on `WatchlistWidget`, `ChartWidget`, and `DetailView`. Each stops its timers and calls `quit()` + `wait(2000ms)` on any in-flight worker threads before the process exits.

---

## Known Gaps / Future Work

- **No portfolio / cost-basis tracking** — purely a watchlist and chart viewer.
- **No alerts or price notifications**.
- **No chart auto-refresh for the selected ticker on non-intraday periods** — the chart only reloads on explicit user action for daily+ ranges (there is no useful new data to show mid-session anyway, but an explicit "refresh" button could be added).
- **Flatpak packaging** — scaffolding is present in `flatpak/` but has not been validated end-to-end.
