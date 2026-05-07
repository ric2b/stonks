import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np

from stonks.services import yahoo_api

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


class HistoryData:
    """Lightweight replacement for pandas DataFrame used by the chart widget."""

    def __init__(self, timestamps: list[int | float], ohlcv: dict[str, list]):
        self._timestamps = timestamps
        self._ohlcv = ohlcv
        self.index = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]

    @property
    def empty(self) -> bool:
        return len(self._timestamps) == 0

    @property
    def columns(self) -> list[str]:
        return list(self._ohlcv.keys())

    def __getitem__(self, key: str) -> np.ndarray:
        return np.array(self._ohlcv[key], dtype=float)


_info_cache: dict[str, tuple[dict, float]] = {}
_history_cache: dict[tuple, tuple[HistoryData, float]] = {}
_INFO_TTL = 300.0
_HISTORY_TTL = 60.0


def fetch_history(ticker: str, period: str, interval: str) -> HistoryData:
    key = (ticker, period, interval)
    now = time.monotonic()
    cached = _history_cache.get(key)
    if cached is not None and now - cached[1] < _HISTORY_TTL:
        return cached[0]
    raw = yahoo_api.fetch_chart(ticker, range_=period, interval=interval)
    if raw is None:
        raise ValueError(f"No data returned for {ticker}")
    hd = _chart_to_history(raw)
    if hd.empty:
        raise ValueError(f"No data returned for {ticker}")
    _evict_history_cache(now)
    _history_cache[key] = (hd, now)
    return hd


def _chart_to_history(raw: dict) -> HistoryData:
    return HistoryData(
        raw["timestamps"],
        {
            "Close": raw["close"],
            "Open": raw["open"],
            "High": raw["high"],
            "Low": raw["low"],
            "Volume": raw["volume"],
        },
    )


def fetch_info(ticker: str, max_age: float = _INFO_TTL) -> dict:
    now = time.monotonic()
    cached = _info_cache.get(ticker)
    if cached is not None and now - cached[1] < max_age:
        return cached[0]
    quote = yahoo_api.batch_quote([ticker]).get(ticker, {})
    summary = yahoo_api.fetch_quote_summary(ticker)
    summary.update(quote)
    _info_cache[ticker] = (summary, now)
    return summary


def batch_fetch_history(
    tickers: list[str], period: str, interval: str,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, HistoryData]:
    if not tickers:
        return {}
    results = {}
    for ticker in tickers:
        if cancelled is not None and cancelled():
            break
        try:
            raw = yahoo_api.fetch_chart(ticker, range_=period, interval=interval)
            if raw is not None:
                hd = _chart_to_history(raw)
                if not hd.empty:
                    results[ticker] = hd
        except Exception:
            logger.debug("Failed to fetch history for %s", ticker)
    return results


def populate_history_cache(results: dict[str, HistoryData], period: str, interval: str) -> None:
    now = time.monotonic()
    _evict_history_cache(now)
    for ticker, hd in results.items():
        _history_cache[(ticker, period, interval)] = (hd, now)


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


def fetch_names(tickers: list[str]) -> dict[str, str]:
    uncached = [t for t in tickers if t not in _name_cache]
    if uncached:
        quotes = yahoo_api.batch_quote(uncached)
        for sym, info in quotes.items():
            name = info.get("longName") or info.get("shortName") or ""
            if name:
                _name_cache[sym] = name
    return {t: _name_cache[t] for t in tickers if t in _name_cache}


def fetch_prices(tickers: list[str]) -> tuple[dict[str, tuple[float, float]], set[str]]:
    """Return ({ticker: (price, change_pct)}, no_data_tickers)."""
    results = {}
    no_data: set[str] = set()
    try:
        quotes = yahoo_api.batch_quote(tickers)
    except Exception:
        logger.debug("Batch price fetch failed")
        return results, no_data
    for ticker in tickers:
        info = quotes.get(ticker)
        if info is None:
            continue
        price = info.get("regularMarketPrice")
        if price is None:
            no_data.add(ticker)
            continue
        change_pct = info.get("regularMarketChangePercent")
        if change_pct is None:
            prev = info.get("regularMarketPreviousClose")
            if prev and prev != 0:
                change_pct = ((price - prev) / prev) * 100
        results[ticker] = (price, change_pct if change_pct is not None else 0.0)
        _info_cache[ticker] = (info, time.monotonic())
    return results, no_data


def fetch_currencies(tickers: list[str]) -> dict[str, str]:
    results = {}
    for ticker in tickers:
        cached = _info_cache.get(ticker)
        if cached is not None:
            code = cached[0].get("currency") or ""
            if code:
                results[ticker] = code
    return results


def search_tickers(query: str, max_results: int = 5) -> list[dict]:
    raw = yahoo_api.search(query, max_results=max_results)
    out = []
    for q in raw:
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
    raw = yahoo_api.fetch_news(ticker, max_items=max_items)
    items = []
    for entry in raw:
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
    return yahoo_api.validate_ticker(ticker)
