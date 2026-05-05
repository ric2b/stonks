import logging
import time

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_info_cache: dict[str, tuple[dict, float]] = {}
_history_cache: dict[tuple, tuple[pd.DataFrame, float]] = {}
_INFO_TTL = 300.0
_HISTORY_TTL = 60.0


def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    key = (ticker, period, interval)
    now = time.monotonic()
    cached = _history_cache.get(key)
    if cached is not None and now - cached[1] < _HISTORY_TTL:
        return cached[0]
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    _evict_history_cache(now)
    _history_cache[key] = (df, now)
    return df


def fetch_info(ticker: str) -> dict:
    now = time.monotonic()
    cached = _info_cache.get(ticker)
    if cached is not None and now - cached[1] < _INFO_TTL:
        return cached[0]
    t = yf.Ticker(ticker)
    result = t.info
    _info_cache[ticker] = (result, now)
    return result


def batch_fetch_history(tickers: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    """Fetch history for multiple tickers in a single yfinance call."""
    if not tickers:
        return {}
    df = yf.download(tickers, period=period, interval=interval, progress=False)
    if df.empty:
        return {}

    results = {}
    if df.columns.nlevels == 1:
        # Flat columns — single ticker without MultiIndex
        if len(tickers) == 1:
            clean = df.dropna(how="all")
            if not clean.empty:
                results[tickers[0]] = clean
    else:
        # MultiIndex (price_type, ticker) — standard for yfinance 1.x
        for ticker in tickers:
            try:
                ticker_df = df.xs(ticker, level=1, axis=1).dropna(how="all")
                if not ticker_df.empty:
                    results[ticker] = ticker_df
            except KeyError:
                pass

    return results


def populate_history_cache(results: dict[str, pd.DataFrame], period: str, interval: str) -> None:
    """Store batch-fetched DataFrames into the in-memory history cache."""
    now = time.monotonic()
    _evict_history_cache(now)
    for ticker, df in results.items():
        _history_cache[(ticker, period, interval)] = (df, now)


def _evict_history_cache(now: float) -> None:
    stale = [k for k, (_, t) in _history_cache.items() if now - t >= _HISTORY_TTL]
    for k in stale:
        del _history_cache[k]


_name_cache: dict[str, str] = {}


def fetch_names(tickers: list[str]) -> dict[str, str]:
    results = {}
    for ticker in tickers:
        if ticker in _name_cache:
            results[ticker] = _name_cache[ticker]
            continue
        try:
            info = fetch_info(ticker)
            name = info.get("longName") or info.get("shortName") or ""
            if name:
                _name_cache[ticker] = name
                results[ticker] = name
        except Exception:
            pass
    return results


def search_tickers(query: str, max_results: int = 5) -> list[dict]:
    results = yf.Search(query, max_results=max_results)
    out = []
    for q in results.quotes[:max_results]:
        sym = q.get("symbol", "")
        if not sym:
            continue
        out.append(
            {
                "symbol": sym,
                "name": q.get("shortname") or q.get("longname") or sym,
                "exchange": q.get("exchDisp") or q.get("exchange") or "",
            }
        )
    return out


def validate_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return hasattr(info, "last_price") and info.last_price is not None
    except Exception:
        logger.debug("Ticker validation failed for %s", ticker)
        return False
