import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    return df


def fetch_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    return t.info


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
