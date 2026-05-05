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
├── config.py                Constants: DB path, TIME_RANGES, refresh interval
├── models/
│   └── database.py          SQLite schema + CRUD helpers
├── services/
│   ├── stock_data.py        yfinance wrappers with in-memory TTL cache
│   └── cache.py             SQLite OHLCV cache helpers (not yet wired to chart)
└── ui/
    ├── main_window.py       Top-level window: splitter, status bar, shortcuts, session restore
    ├── watchlist.py         Left sidebar: live search, price refresh, drag-reorder
    ├── chart_widget.py      Price + volume chart, range tabs, crosshair
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
   - `ChartWidget.update_chart(ticker)` — spawns a `HistoryWorker`
   - `DetailView.update_detail(ticker)` — spawns an `InfoWorker`
3. **Workers** run in `QThread`, call yfinance, and emit a signal back on the main thread.  
   All workers are kept in a `_workers: list` on their parent widget to prevent garbage collection mid-run.
4. **Company info round-trip** — once `InfoWorker` finishes, `DetailView` emits `info_received(ticker, name, exchange, currency)`. `MainWindow` forwards this to `ChartWidget.set_company_info()` to fill the chart header without a second network call.

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

---

## Caching

### In-memory TTL (`services/stock_data.py`)

Two module-level dicts keyed by ticker (or `(ticker, period, interval)`) with a monotonic timestamp:

| Function | TTL | Purpose |
|---|---|---|
| `fetch_info()` | 5 minutes | Eliminates company name / stats pop-in when re-selecting a ticker |
| `fetch_history()` | 60 seconds | Avoids re-fetching chart data when switching back and forth |

### SQLite price cache (`models/database.py`, `services/cache.py`)

A `price_cache(ticker, date, open, high, low, close, volume)` table exists and has CRUD helpers (`get_cached_prices`, `upsert_prices`). The original design was to use this for daily+ intervals (intraday always fetched fresh). It is **not currently wired** to `HistoryWorker` — the chart fetches via `fetch_history()` which only uses the in-memory TTL cache above.

### Settings (`models/database.py`)

A `settings(key, value)` key-value table stores session state. Currently used for:

- `last_ticker` — restored on startup; falls back to the first watchlist item
- `last_period` — restored on startup; falls back to `"1M"`

The `settings` table is created by `init_db` alongside the other tables, so existing databases are migrated automatically on first run.

---

## Price Refresh

Watchlist prices are refreshed in the background every **60 seconds** via a `QTimer` in `WatchlistWidget`. Each tick spawns a single `PriceUpdateWorker` that fetches a 2-day daily window for every ticker in the list and computes the day-over-day change percentage. The current chart is **not** auto-refreshed; it shows the data from the last explicit load (ticker selection or range change).

---

## Chart Details

- **Gap filling** — consecutive timestamps more than 1.6× the median interval apart (weekends, holidays) get a synthetic point inserted just before the next open, holding the previous close flat. This prevents diagonal lines across non-trading periods.
- **Zoom** — x-axis only (`setMouseEnabled(x=True, y=False)`). Y auto-scales to the visible x range (`setAutoVisible(y=True)`). Zoom-out is capped at the data extent via `setLimits(maxXRange=...)`.
- **Crosshair** — vertical + horizontal dashed lines, a tracking dot on the price line, a date label floating above the chart area (parent: `ChartWidget`, never overlaps data), and a price label pinned to the right edge at the cursor's y position.
- **Volume** — rendered as a bar chart below the price chart, x-linked so it pans/zooms in sync. Hidden when no volume data is present.

---

## Known Gaps / Future Work

- **SQLite price cache not wired** — `HistoryWorker` calls `fetch_history()` directly. Wiring `cache.py` into the fetch path would reduce cold-start latency and allow offline browsing of previously viewed ranges.
- **Currency symbols in detail stats** — `detail_view.py` still prefixes currency-typed values (Open, High, Low, EPS, etc.) with `$`. These should respect the ticker's actual currency, consistent with how the chart header now handles it.
- **No auto-refresh for the chart** — the chart only reloads on explicit user action. A background refresh for the active ticker (especially on 1D) would keep intraday data current.
- **No portfolio / cost-basis tracking** — purely a watchlist and chart viewer.
- **No alerts or price notifications**.
- **Flatpak packaging** — scaffolding is present in `flatpak/` but has not been validated end-to-end.
