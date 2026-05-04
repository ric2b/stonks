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


def validate_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return hasattr(info, "last_price") and info.last_price is not None
    except Exception:
        logger.debug("Ticker validation failed for %s", ticker)
        return False
