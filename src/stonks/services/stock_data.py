import logging
import threading
import time
from dataclasses import dataclass

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


@dataclass(frozen=True)
class HistoryData:
    timestamps: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    @property
    def empty(self) -> bool:
        return len(self.timestamps) == 0


class TTLCache[K, V]:
    """Thread-safe dict whose entries expire after ``ttl`` seconds (never if None).

    Expired entries are kept for ``retain`` seconds so the UI can show them via
    peek() while fresh data loads.
    """

    def __init__(self, ttl: float | None, retain: float | None = None):
        self._ttl = ttl
        self._retain = retain if retain is not None else ttl
        self._data: dict[K, tuple[V, float]] = {}
        self._lock = threading.Lock()
        self._next_sweep = 0.0

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._data.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if self._ttl is not None and time.monotonic() - stored_at >= self._ttl:
            return None
        return value

    def peek(self, key: K) -> tuple[V | None, bool]:
        """Return (value, is_fresh), including expired-but-retained values."""
        with self._lock:
            entry = self._data.get(key)
        if entry is None:
            return None, False
        value, stored_at = entry
        age = time.monotonic() - stored_at
        if self._retain is not None and age >= self._retain:
            return None, False
        return value, self._ttl is None or age < self._ttl

    def set(self, key: K, value: V) -> None:
        now = time.monotonic()
        with self._lock:
            if self._retain is not None and now >= self._next_sweep:
                self._data = {k: e for k, e in self._data.items() if now - e[1] < self._retain}
                self._next_sweep = now + self._retain
            self._data[key] = (value, now)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_RETAIN = 3600.0
_info_cache: TTLCache[str, dict] = TTLCache(ttl=300.0, retain=_RETAIN)
_history_cache: TTLCache[tuple[str, str, str], HistoryData] = TTLCache(ttl=60.0, retain=_RETAIN)
_meta_cache: TTLCache[str, tuple[str, str]] = TTLCache(ttl=None)
_news_cache: TTLCache[str, list[dict]] = TTLCache(ttl=300.0, retain=_RETAIN)


def peek_history(ticker: str, period: str, interval: str) -> tuple[HistoryData | None, bool]:
    return _history_cache.peek((ticker, period, interval))


def peek_info(ticker: str) -> tuple[dict | None, bool]:
    return _info_cache.peek(ticker)


def peek_news(ticker: str) -> tuple[list[dict] | None, bool]:
    return _news_cache.peek(ticker)


def fetch_history(ticker: str, period: str, interval: str) -> HistoryData:
    key = (ticker, period, interval)
    cached = _history_cache.get(key)
    if cached is not None:
        return cached
    raw = yahoo_api.fetch_chart(ticker, range_=period, interval=interval)
    if raw is None:
        raise ValueError(f"No data returned for {ticker}")
    hd = _chart_to_history(raw)
    if hd.empty:
        raise ValueError(f"No data returned for {ticker}")
    _history_cache.set(key, hd)
    return hd


def _chart_to_history(raw: dict) -> HistoryData:
    return HistoryData(
        timestamps=np.asarray(raw["timestamps"], dtype=float),
        close=np.asarray(raw["close"], dtype=float),
        volume=np.asarray(raw["volume"], dtype=float),
    )


def fetch_info(ticker: str) -> dict:
    cached = _info_cache.get(ticker)
    if cached is not None:
        return cached
    quote = yahoo_api.batch_quote([ticker]).get(ticker, {})
    summary = yahoo_api.fetch_quote_summary(ticker)
    summary.update(quote)
    _info_cache.set(ticker, summary)
    return summary


def _fetch_one_history(ticker: str, period: str, interval: str) -> tuple[str, HistoryData | None]:
    try:
        raw = yahoo_api.fetch_chart(ticker, range_=period, interval=interval)
        if raw is not None:
            hd = _chart_to_history(raw)
            if not hd.empty:
                return ticker, hd
    except Exception:
        logger.debug("Failed to fetch history for %s", ticker)
    return ticker, None


def batch_fetch_history(tickers: list[str], period: str, interval: str) -> dict[str, HistoryData]:
    # Daemon threads rather than ThreadPoolExecutor, whose workers are joined at
    # interpreter exit and would make quitting wait for in-flight requests.
    results: dict[str, HistoryData] = {}
    lock = threading.Lock()
    limit = threading.Semaphore(8)

    def fetch(ticker: str) -> None:
        with limit:
            _, hd = _fetch_one_history(ticker, period, interval)
        if hd is not None:
            with lock:
                results[ticker] = hd

    threads = [threading.Thread(target=fetch, args=(t,), daemon=True) for t in tickers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def populate_history_cache(results: dict[str, HistoryData], period: str, interval: str) -> None:
    for ticker, hd in results.items():
        _history_cache.set((ticker, period, interval), hd)


def fetch_names_and_currencies(tickers: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Return ({ticker: name}, {ticker: currency_code}) for tickers Yahoo knows."""
    uncached = [t for t in tickers if _meta_cache.get(t) is None]
    if uncached:
        for sym, info in yahoo_api.batch_quote(uncached).items():
            name = info.get("longName") or info.get("shortName") or ""
            _meta_cache.set(sym, (name, info.get("currency") or ""))
    names, currencies = {}, {}
    for t in tickers:
        name, currency = _meta_cache.get(t) or ("", "")
        if name:
            names[t] = name
        if currency:
            currencies[t] = currency
    return names, currencies


def price_and_change(info: dict) -> tuple[float, float] | None:
    """Return (price, change_pct) from a quote dict, or None without a price."""
    price = info.get("regularMarketPrice")
    if price is None:
        return None
    change_pct = info.get("regularMarketChangePercent")
    if change_pct is None:
        prev = info.get("regularMarketPreviousClose")
        change_pct = (price - prev) / prev * 100 if prev else 0.0
    return float(price), float(change_pct)


def fetch_prices(tickers: list[str]) -> dict[str, tuple[float, float]]:
    """Return {ticker: (price, change_pct)} for tickers that have a price."""
    quotes = yahoo_api.batch_quote(tickers)
    results = {}
    for ticker in tickers:
        priced = price_and_change(quotes.get(ticker, {}))
        if priced is not None:
            results[ticker] = priced
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


def fetch_news(ticker: str, max_items: int = 8) -> list[dict]:
    cached = _news_cache.get(ticker)
    if cached is not None:
        return cached
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
    _news_cache.set(ticker, items)
    return items


def validate_ticker(ticker: str) -> bool:
    return yahoo_api.validate_ticker(ticker)
