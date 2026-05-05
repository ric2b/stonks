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
