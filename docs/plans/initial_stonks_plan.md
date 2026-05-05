# Stonks - Implementation Plan

## Context

Build "Stonks", an open-source (GPL-3.0) desktop stock tracker for Linux (Ubuntu), inspired by the macOS native Stocks app. It's a portfolio/hobby project prioritizing simplicity and shipping speed. The app lets users maintain a stock watchlist, view interactive price charts, and see key financial stats for each ticker.

## Decisions

- **Stack**: Python + PySide6 (Qt6), PyQtGraph for charts, yfinance for data, raw sqlite3 for persistence
- **Dependency management**: uv (lockfile via `uv.lock`, standard pyproject.toml)
- **UI**: Native Linux look (inherit system Qt theme), layout mirrors macOS Stocks (sidebar + chart + detail)
- **Distribution**: Flatpak (KDE Platform runtime, which bundles Qt6)
- **License**: GPL-3.0

## UI Layout

```
+---------------------------------------------------+
|  Stonks                                           |
+----------+----------------------------------------+
| AAPL     |  [1D] [1W] [1M] [1Y] [5Y] [ALL]      |
| $198.50  |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~         |
| +1.23%   |  ~~  area chart  ~~~~~~~~~~~~         |
|----------|  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~         |
| MSFT     |----------------------------------------|
| $425.10  |  Open: 197.00    Market Cap: 3.1T      |
| -0.45%   |  High: 199.20    P/E: 32.5             |
+----------+----------------------------------------+
```

## Project Structure

```
stonks/
├── src/stonks/
│   ├── __init__.py
│   ├── main.py              # Entry point, QApplication setup
│   ├── config.py            # Constants (DB path, refresh interval, time ranges)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py   # QMainWindow with QSplitter layout
│   │   ├── watchlist.py     # Sidebar: QListWidget + add field + drag-drop reorder
│   │   ├── chart_widget.py  # PyQtGraph PlotWidget + time range buttons + crosshair
│   │   ├── detail_view.py   # QGridLayout of key stats
│   │   └── workers.py       # QThread workers for all data fetching
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stock_data.py    # yfinance wrapper (fetch_history, fetch_info, validate_ticker)
│   │   └── cache.py         # Cache layer (intraday=always fresh, daily+=cached in SQLite)
│   └── models/
│       ├── __init__.py
│       └── database.py      # SQLite schema (watchlist + price_cache) + CRUD functions
├── tests/
│   ├── conftest.py            # Shared fixtures (tmp db, mock yfinance responses)
│   ├── test_database.py       # Watchlist + cache CRUD tests
│   ├── test_stock_data.py     # yfinance wrapper tests (mocked network)
│   ├── test_cache.py          # Cache logic tests
│   └── test_integration.py    # End-to-end: add ticker -> fetch -> verify data flow
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions: lint, type check, test
├── assets/
│   └── com.stonks.Stonks.svg
├── flatpak/
│   ├── com.stonks.Stonks.yml
│   ├── com.stonks.Stonks.desktop
│   └── com.stonks.Stonks.metainfo.xml
├── pyproject.toml
├── uv.lock                    # Pinned dependency versions (committed to repo)
├── LICENSE
├── README.md
└── .gitignore
```

## Testing & CI Strategy

**Testing** (pytest):
- Dev deps in `[project.optional-dependencies]`: pytest, pytest-qt (for widget testing), ruff
- Mock yfinance responses in tests (no real network calls in CI)
- Focus on data layer + service layer tests; UI tests kept to smoke-test level via pytest-qt
- One integration test per phase that exercises the full call path

**Linting** (ruff):
- Configured in `pyproject.toml` under `[tool.ruff]` — covers linting + formatting (replaces flake8, isort, black)
- Rules: default ruff set + isort (I) + pyflakes (F) + pycodestyle (E, W)

**GitHub Actions** (`.github/workflows/ci.yml`):
- Triggers: push to main, all PRs
- Matrix: Python 3.11, 3.12 on ubuntu-latest
- Steps: `uv sync --all-extras`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`
- Uses `astral-sh/setup-uv` action for fast uv install

---

## Phase 1: Project Scaffold

**Goal**: Empty window appears, CI runs.

- `pyproject.toml` — PEP 621 metadata, hatchling build, deps + dev deps (pytest, pytest-qt, ruff), ruff config
- `uv lock` — generates `uv.lock` with pinned versions (committed to repo)
- `src/stonks/main.py` — Creates QApplication (name="Stonks", desktop file ID for Wayland), instantiates MainWindow, `sys.exit(app.exec())`
- `src/stonks/ui/main_window.py` — QMainWindow, title "Stonks", min size 900x600, placeholder label
- `.github/workflows/ci.yml` — lint + test pipeline
- `tests/conftest.py` — empty for now
- LICENSE, README.md, .gitignore

**Verify**: `uv sync && uv run stonks` shows a window. `uv run ruff check .` passes. `uv run pytest` passes (no tests yet, but exits 0).

**Commit**: "Initial project scaffold with CI"

## Phase 2: Data Layer

**Goal**: yfinance wrapper + SQLite schema, testable without UI.

**`models/database.py`** — Two tables:
- `watchlist(id, ticker UNIQUE, position)` for ordered watchlist
- `price_cache(ticker, date, open, high, low, close, volume)` for caching daily+ data
- Functions: `init_db`, `get_watchlist`, `add_ticker`, `remove_ticker`, `reorder_watchlist`, `get_cached_prices`, `upsert_prices`
- DB path: `~/.local/share/stonks/stonks.db` (XDG_DATA_HOME)

**`services/stock_data.py`** — yfinance wrapper:
- `fetch_history(ticker, period, interval) -> pd.DataFrame`
- `fetch_info(ticker) -> dict`
- `validate_ticker(ticker) -> bool` (via `fast_info`)
- Period/interval mapping: 1D=(1d,5m), 1W=(5d,30m), 1M=(1mo,1d), 1Y=(1y,1d), 5Y=(5y,1wk), ALL=(max,1mo)

**`services/cache.py`** — Intraday intervals: always fetch fresh. Daily+: return cached if last date is today, otherwise fetch and cache.

**Tests**:
- `tests/test_database.py` — add/remove/reorder tickers, get_watchlist ordering, upsert/get cached prices, duplicate ticker handling
- `tests/test_stock_data.py` — mock yfinance responses, verify fetch_history returns expected DataFrame shape, validate_ticker returns False for nonsense tickers
- `tests/test_cache.py` — verify intraday bypasses cache, daily data uses cache when fresh
- `tests/test_integration.py` — full path: add ticker to DB -> fetch history (mocked) -> cache -> retrieve from cache

**Verify**: `uv run pytest` — all tests pass.

**Commit**: "Add data layer: yfinance wrapper, SQLite schema, caching, tests"

## Phase 3: Watchlist UI

**Goal**: Left sidebar with add/remove/reorder, price updates.

**`ui/main_window.py`** — Refactor to QSplitter (left=watchlist, right=placeholder). Sizes [250, 650].

**`ui/watchlist.py`** — WatchlistWidget containing:
- QLineEdit for adding tickers (validates in worker thread before adding)
- QListWidget with `InternalMove` drag-drop for reordering
- Custom item widgets: ticker (bold, left), price+change% (right, green/red)
- Right-click context menu: "Remove from watchlist"
- Emits `ticker_selected(str)` signal on selection change
- PriceUpdateWorker on QTimer (60s) batch-refreshes prices for all tickers

**Verify**: Add/remove tickers, drag to reorder, persists after restart.

**Commit**: "Add watchlist sidebar with add/remove/reorder"

## Phase 4: Chart Widget

**Goal**: Interactive PyQtGraph area chart with time range buttons.

**`ui/chart_widget.py`** — ChartWidget containing:
- Row of QPushButtons (QButtonGroup, exclusive, checkable) for 1D/1W/1M/1Y/5Y/ALL
- `pg.PlotWidget` with `DateAxisItem` on bottom axis
- Area fill: green if price up over period, red if down. Semi-transparent brush.
- Crosshair: vertical InfiniteLine + TextItem tracking mouse, showing date + price
- Data fetched via HistoryWorker (QThread), timestamps = `df.index.astype(np.int64) // 10**9`

**`ui/main_window.py`** — Connect `ticker_selected` to `chart_widget.update_chart`.

**Verify**: Click ticker -> chart shows. Switch time ranges. Hover shows crosshair.

**Commit**: "Add interactive price chart with time range selector"

## Phase 5: Detail View

**Goal**: Key stats panel below chart.

**`ui/detail_view.py`** — QGridLayout (4-column: label, value, label, value):
- Stats: Open, High, Low, Close, Volume, Avg Volume, Market Cap, P/E, EPS, 52w High, 52w Low, Dividend Yield
- Sourced from `yf.Ticker.info` dict
- `format_number()` helper for currency/percentage/large numbers
- Missing fields show "--"
- Fetched via InfoWorker (QThread)

**`ui/main_window.py`** — Right pane becomes QVBoxLayout: ChartWidget (~65%) + DetailView (~35%).

**Verify**: Click ticker -> stats populate. Missing fields show "--".

**Commit**: "Add stock detail view with key financial stats"

## Phase 6: Polish

**Goal**: Error handling, loading states, keyboard shortcuts.

- **Error handling**: Wrap yfinance calls in try/except, log with `logging`, show user-friendly messages via QStatusBar or overlay label on chart area
- **Loading states**: QStackedWidget in chart area switching between "Loading..." label and plot widget. Detail view grays out during fetch.
- **Keyboard shortcuts**: Ctrl+N or / = focus add-ticker field, Delete = remove selected, 1-6 = switch time range, Ctrl+Q = quit
- **Visual**: Ticker name + company name + price as header above chart. Triangle indicators on change%.
- **`config.py`**: APP_NAME, DB_DIR, DB_PATH, REFRESH_INTERVAL_MS=60000, TIME_RANGES dict
- **`ui/workers.py`**: Extract all QThread workers (HistoryWorker, InfoWorker, ValidateWorker, PriceUpdateWorker) with `finished`/`error` signals

**Verify**: Disconnect internet -> error messages, not crashes. Loading states visible. Shortcuts work.

**Commit**: "Add error handling, loading states, keyboard shortcuts" (may split into 2 commits if the diff is large)

## Phase 7: Packaging

**Goal**: Flatpak-ready distribution.

- `flatpak/com.stonks.Stonks.yml` — KDE Platform 6.7 runtime, network + Wayland + X11 permissions, install deps from `uv.lock` exported to requirements.txt (`uv export --format requirements-txt`)
- `flatpak/com.stonks.Stonks.desktop` — Desktop entry (Finance;Office categories)
- `flatpak/com.stonks.Stonks.metainfo.xml` — AppStream metadata (required for Flathub)
- `assets/com.stonks.Stonks.svg` — Simple app icon (upward-trending chart)
- Use `flatpak-pip-generator` with exported requirements.txt for offline dependency sources

**Verify**: `flatpak-builder build-dir flatpak/com.stonks.Stonks.yml --force-clean` builds. App launches in sandbox, fetches data, icon shows in launcher.

**Commit**: "Add Flatpak packaging and desktop integration"

---

## Key Technical Decisions

1. **uv for dependency management** — fast, generates `uv.lock` for reproducible installs, uses standard pyproject.toml (no proprietary format)
2. **Raw sqlite3 over SQLAlchemy** — 2-table schema doesn't justify ORM overhead
2. **QThread workers over asyncio** — natural integration with PySide6 signals/slots
3. **Single sqlite3 connection passed around** — created in main.py, passed to widgets
4. **DateAxisItem for time axis** — auto-formats at different zoom levels
5. **Cache daily+ data only** — intraday is always fresh (changes throughout trading day)
6. **KDE Platform for Flatpak** — bundles Qt6, simpler than generic runtime + manual Qt install

## Verification (End-to-End)

1. `uv sync && uv run stonks` — app launches
2. Add "AAPL", "MSFT", "GOOGL" to watchlist — all show with prices
3. Click each ticker — chart + detail view update
4. Switch time ranges — chart redraws correctly
5. Drag to reorder, restart app — order persists
6. Remove a ticker — disappears, chart clears or shows next
7. Disconnect network, try adding a ticker — graceful error message
8. Build Flatpak — launches and works in sandbox
