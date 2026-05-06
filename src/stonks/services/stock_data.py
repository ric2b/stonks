import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "¥",
    "CAD": "CA$",
    "AUD": "A$",
    "NZD": "NZ$",
    "HKD": "HK$",
    "SGD": "S$",
    "TWD": "NT$",
    "INR": "₹",
    "KRW": "₩",
    "BRL": "R$",
    "ILS": "₪",
    "MXN": "MX$",
    "THB": "฿",
    "TRY": "₺",
    "PHP": "₱",
    "RUB": "₽",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "CZK": "Kč",
    "PLN": "zł",
    "HUF": "Ft",
    "GBp": "p",
}

_SUFFIX_CURRENCIES = {"EUR", "SEK", "NOK", "DKK", "CZK", "PLN", "HUF", "GBp"}


def currency_format(code: str) -> tuple[str, str]:
    """Return (prefix, suffix) for the given currency code."""
    symbol = CURRENCY_SYMBOLS.get(code, "")
    if not symbol:
        return ("", "")
    if code in _SUFFIX_CURRENCIES:
        return ("", symbol)
    return (symbol, "")


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


def fetch_info(ticker: str, max_age: float = _INFO_TTL) -> dict:
    now = time.monotonic()
    cached = _info_cache.get(ticker)
    if cached is not None and now - cached[1] < max_age:
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


def is_history_cached(ticker: str, period: str, interval: str) -> bool:
    key = (ticker, period, interval)
    cached = _history_cache.get(key)
    if cached is None:
        return False
    return time.monotonic() - cached[1] < _HISTORY_TTL


def _evict_history_cache(now: float) -> None:
    stale = [k for k, (_, t) in _history_cache.items() if now - t >= _HISTORY_TTL]
    for k in stale:
        del _history_cache[k]


_name_cache: dict[str, str] = {}


def _fetch_name_for_ticker(ticker: str) -> tuple[str, str]:
    if ticker in _name_cache:
        return ticker, _name_cache[ticker]
    info = fetch_info(ticker)
    name = info.get("longName") or info.get("shortName") or ""
    if name:
        _name_cache[ticker] = name
    return ticker, name


def fetch_names(tickers: list[str]) -> dict[str, str]:
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_name_for_ticker, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, name = future.result()
                if name:
                    results[ticker] = name
            except Exception:
                logger.debug("Failed to fetch name for %s", futures[future])
    return results


def fetch_prices(tickers: list[str]) -> tuple[dict[str, tuple[float, float]], set[str]]:
    """Return ({ticker: (price, change_pct)}, no_data_tickers).

    Tickers in no_data got a valid response but had no price (delisted/invalid).
    Tickers absent from both had a transient error and may be worth retrying.
    """
    results = {}
    no_data: set[str] = set()

    def _fetch_one(ticker: str) -> tuple[str, float | None, float | None]:
        info = fetch_info(ticker, max_age=_HISTORY_TTL)
        price = info.get("regularMarketPrice")
        change_pct = info.get("regularMarketChangePercent")
        if price is not None and change_pct is None:
            prev = info.get("regularMarketPreviousClose")
            if prev and prev != 0:
                change_pct = ((price - prev) / prev) * 100
        return ticker, price, change_pct

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, price, change_pct = future.result()
                if price is None:
                    no_data.add(ticker)
                    continue
                results[ticker] = (price, change_pct if change_pct is not None else 0.0)
            except Exception:
                logger.debug("Failed to fetch price for %s", futures[future])
    return results, no_data


def fetch_currencies(tickers: list[str]) -> dict[str, str]:
    """Return currency codes for tickers whose info is already cached."""
    results = {}
    for ticker in tickers:
        cached = _info_cache.get(ticker)
        if cached is not None:
            code = cached[0].get("currency") or ""
            if code:
                results[ticker] = code
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


_news_cache: dict[str, tuple[list[dict], float]] = {}
_NEWS_TTL = 300.0


def fetch_news(ticker: str, max_items: int = 8) -> list[dict]:
    now = time.monotonic()
    cached = _news_cache.get(ticker)
    if cached is not None and now - cached[1] < _NEWS_TTL:
        return cached[0]
    t = yf.Ticker(ticker)
    raw = t.news or []
    items = []
    for entry in raw[:max_items]:
        c = entry.get("content", {})
        title = c.get("title", "")
        if not title:
            continue
        url = ""
        for url_key in ("clickThroughUrl", "canonicalUrl"):
            url_obj = c.get(url_key)
            if url_obj:
                url = url_obj.get("url", "")
                if url:
                    break
        provider = c.get("provider", {}).get("displayName", "")
        pub_date = c.get("pubDate", "")
        items.append(
            {
                "title": title,
                "url": url,
                "provider": provider,
                "pubDate": pub_date,
            }
        )
    _news_cache[ticker] = (items, now)
    return items


def validate_ticker(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return hasattr(info, "last_price") and info.last_price is not None
    except Exception:
        logger.debug("Ticker validation failed for %s", ticker)
        return False
