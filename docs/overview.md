# Stonks — Overview

Desktop stock-tracking app for Linux/macOS, inspired by the macOS Stocks app.  
GPL-3.0 · Python 3.14 · PySide6 · PyQtGraph · Yahoo Finance HTTP API · SQLite

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI framework | PySide6 (Qt6) |
| Charts | PyQtGraph |
| Market data | Yahoo Finance HTTP API via `urllib` (no third-party client) |
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
│   ├── yahoo_api.py         Raw Yahoo Finance endpoints; cookie/crumb session shared across threads
│   └── stock_data.py        Domain functions over yahoo_api with thread-safe TTL caches + batch fetch
└── ui/
    ├── main_window.py       Top-level window: splitter, status bar, shortcuts, session restore, prefetch
    ├── watchlist.py         Left sidebar: live search, price refresh, drag-reorder
    ├── chart_widget.py      Price + volume chart, range tabs, crosshair, auto-refresh
    ├── detail_view.py       Stats grid (Open / High / Low / Vol / P/E / Mkt Cap / …)
    ├── workers.py           run_async(): background thread → main-thread callback
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
   - `ChartWidget.update_chart(ticker)` — `run_async(fetch_history, ...)` (usually hits the in-memory cache)
   - `DetailView.update_detail(ticker)` — `run_async(fetch_info, ...)` (usually hits the in-memory cache)
3. **Background work** — `run_async(fn, *args, on_done=..., on_error=...)` runs `fn` on a daemon thread and delivers the result or exception to the callback on the main thread via a single long-lived QObject. There are no `QThread` objects, so nothing can be destroyed while still running, and in-flight requests never delay quitting. Callbacks must check they still apply (current ticker, request id, search text) since responses can arrive out of order.
4. **Company info round-trip** — once `fetch_info` returns, `DetailView` emits `info_received(ticker, name, exchange, currency)`. `MainWindow` forwards this to `ChartWidget.set_company_info()` to fill the chart header without a second network call.

### Prefetch

On startup and whenever the time range changes, `MainWindow` runs `batch_fetch_history` in the background, fetching the current period's data for **all watchlist tickers** in parallel (up to 8 at a time). Results are stored directly into the in-memory history cache. By the time the user clicks any ticker, the data is already cached and the chart renders without a loading delay.

### Time ranges

Defined in `config.TIME_RANGES` (ordered dict, also drives the tab bar and keyboard shortcuts):

| Label | Yahoo `range` | Interval |
|---|---|---|
| 1D | 1d | 2m |
| 1W | 5d | 5m |
| 1M | 1mo | 30m |
| 3M | 3mo | 1h |
| 6M | 6mo | 1h |
| YTD | ytd | 1h |
| 1Y | 1y | 1d |
| 5Y | 5y | 1wk |
| 10Y | 10y | 1wk |
| ALL | max | 1mo |

`INTRADAY_INTERVALS = {"2m", "5m", "30m", "1h"}` — the auto-refresh timer and prefetch logic use this to decide whether to keep refreshing on a schedule.

---

## Caching

### In-memory TTL (`services/stock_data.py`)

Module-level `TTLCache` instances (a dict guarded by a lock, since worker threads read and write them concurrently):

| Cache | TTL | Purpose |
|---|---|---|
| `_info_cache` (`fetch_info()`) | 5 minutes | Eliminates stats pop-in when re-selecting a ticker |
| `_history_cache` (`fetch_history()`) | 60 seconds | Avoids re-fetching chart data when switching back and forth |
| `_news_cache` (`fetch_news()`) | 5 minutes | Avoids re-fetching news when re-selecting a ticker |
| `_meta_cache` (`fetch_names_and_currencies()`) | never | Company name + currency per ticker |

`get()` (used by the `fetch_*` functions) only returns entries younger than the TTL. Expired entries are retained for an hour so `peek_history()` / `peek_info()` / `peek_news()` can return them with an `is_fresh` flag: on selection the UI renders whatever is cached synchronously (no loading flash) and refreshes in the background when it is stale. Only data never seen in the last hour shows the chart's loading spinner. Entries older than the retention period are swept at most once per period on write, keeping memory bounded.

The prefetch populates `_history_cache` via `populate_history_cache()`, using the same keys as `fetch_history()`.

### Settings (`models/database.py`)

A `settings(key, value)` key-value table stores session state:

- `last_ticker` — restored on startup; falls back to the first watchlist item
- `last_period` — restored on startup; falls back to `"1M"`

The `settings` table is created by `init_db` alongside the watchlist table, so existing databases are upgraded automatically on first run.

---

## Price Refresh

Watchlist prices are refreshed every **60 seconds** via a `QTimer` in `WatchlistWidget`. Each tick calls `fetch_prices` once for **all tickers** in a single batch quote request and updates the sidebar labels, and retries the name/currency lookup for any ticker still missing it. A tick is skipped while the previous one is still in flight; a failed tick is simply retried on the next one.

The chart auto-refreshes every **5 minutes** when the active period uses an intraday interval (1D through YTD, see `INTRADAY_INTERVALS`). The refresh keeps the current plot on screen and only replaces it when new data arrives; a failed refresh leaves it untouched. Each history request gets an id so a slow response for a previous ticker or range is discarded.

---

## Chart Details

- **Gap filling** — consecutive timestamps more than 1.6× the median interval apart (weekends, holidays) get a synthetic point inserted just before the next open, holding the previous close flat. This prevents diagonal lines across non-trading periods.
- **Zoom** — x-axis only (`setMouseEnabled(x=True, y=False)`). Y auto-scales to the visible x range (`setAutoVisible(y=True)`). Zoom-out is capped at the data extent via `setLimits(maxXRange=...)`.
- **Crosshair** — vertical + horizontal dashed lines, a tracking dot on the price line, a date label floating above the chart area (parent: `ChartWidget`, never overlaps data), and a price label pinned to the right edge at the cursor's y position.
- **Volume** — rendered as a bar chart below the price chart, x-linked so it pans/zooms in sync. Hidden when no volume data is present.
- **Prices** — shown in the ticker's native currency, formatted with `currency_format()` once the currency is known.

---

## Shutdown

No explicit worker shutdown is needed: background tasks run on daemon threads, which are abandoned when the process exits. Requests use a 15s socket timeout (`yahoo_api._TIMEOUT`) so a stalled connection can't block a thread forever.

---

## Known Gaps / Future Work

- **No portfolio / cost-basis tracking** — purely a watchlist and chart viewer.
- **No alerts or price notifications**.
- **No chart auto-refresh for the selected ticker on non-intraday periods** — the chart only reloads on explicit user action for daily+ ranges (there is no useful new data to show mid-session anyway, but an explicit "refresh" button could be added).
