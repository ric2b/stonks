import http.cookiejar
import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart"
_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"
_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_NEWS_URL = "https://finance.yahoo.com/xhr/ncp"

_lock = threading.Lock()
_opener: urllib.request.OpenerDirector | None = None
_crumb: str | None = None


def _fetch_fresh_session() -> tuple[urllib.request.OpenerDirector, str]:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    try:
        opener.open("https://fc.yahoo.com")
    except urllib.error.HTTPError:
        pass
    crumb = opener.open("https://query1.finance.yahoo.com/v1/test/getcrumb").read().decode()
    return opener, crumb


def _ensure_session() -> tuple[urllib.request.OpenerDirector, str]:
    global _opener, _crumb
    if _opener is not None and _crumb is not None:
        return _opener, _crumb
    with _lock:
        if _opener is not None and _crumb is not None:
            return _opener, _crumb
        opener, crumb = _fetch_fresh_session()
        _opener = opener
        _crumb = crumb
        return opener, crumb


def _reset_session():
    global _opener, _crumb
    with _lock:
        _opener = None
        _crumb = None


def _get(url: str, params: dict | None = None) -> dict:
    opener, crumb = _ensure_session()
    if params is None:
        params = {}
    params["crumb"] = crumb
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        return json.loads(opener.open(full_url).read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _reset_session()
            opener, crumb = _fetch_fresh_session()
            with _lock:
                _opener = opener
                _crumb = crumb
            params["crumb"] = crumb
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            return json.loads(opener.open(full_url).read())
        raise


def _post(url: str, params: dict, body: dict) -> dict:
    opener, crumb = _ensure_session()
    params["crumb"] = crumb
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return json.loads(opener.open(req).read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _reset_session()
            opener, crumb = _fetch_fresh_session()
            with _lock:
                _opener = opener
                _crumb = crumb
            params["crumb"] = crumb
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(
                full_url,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            return json.loads(opener.open(req).read())
        raise


def batch_quote(tickers: list[str]) -> dict[str, dict]:
    """Fetch quote data for multiple tickers in one call.

    Returns {ticker: {field: value}} with flat field names matching the
    yfinance info dict convention (dayHigh, volume, etc.).
    """
    if not tickers:
        return {}
    data = _get(_QUOTE_URL, {"symbols": ",".join(tickers)})
    results = {}
    for q in data.get("quoteResponse", {}).get("result", []):
        sym = q.get("symbol")
        if not sym:
            continue
        results[sym] = _normalize_quote(q)
    return results


_QUOTE_FIELD_MAP = {
    "regularMarketDayHigh": "dayHigh",
    "regularMarketDayLow": "dayLow",
    "regularMarketVolume": "volume",
    "averageDailyVolume3Month": "averageVolume",
    "epsTrailingTwelveMonths": "trailingEps",
}


def _normalize_quote(q: dict) -> dict:
    out = {}
    for k, v in q.items():
        mapped = _QUOTE_FIELD_MAP.get(k)
        if mapped:
            out[mapped] = v
        out[k] = v
    return out


def fetch_quote_summary(
    ticker: str,
    modules: str = "price,summaryDetail,defaultKeyStatistics",
) -> dict:
    """Fetch detailed info for a single ticker via quoteSummary.

    Returns a flat dict with raw numeric values.
    """
    data = _get(f"{_SUMMARY_URL}/{ticker}", {"modules": modules})
    results = data.get("quoteSummary", {}).get("result", [])
    if not results:
        return {}
    merged = {}
    for module_data in results[0].values():
        if isinstance(module_data, dict):
            for k, v in module_data.items():
                if isinstance(v, dict) and "raw" in v:
                    merged[k] = v["raw"]
                elif isinstance(v, list):
                    merged[k] = v
                elif not isinstance(v, dict):
                    merged[k] = v
    return merged


def fetch_chart(ticker: str, range_: str, interval: str) -> dict | None:
    """Fetch OHLCV history for a ticker.

    Returns {"timestamps": [...], "open": [...], "high": [...],
             "low": [...], "close": [...], "volume": [...]}
    or None if no data.
    """
    data = _get(f"{_CHART_URL}/{ticker}", {"range": range_, "interval": interval})
    results = data.get("chart", {}).get("result")
    if not results:
        return None
    result = results[0]
    timestamps = result.get("timestamp")
    if not timestamps:
        return None
    quote = result["indicators"]["quote"][0]
    return {
        "timestamps": timestamps,
        "open": quote.get("open", []),
        "high": quote.get("high", []),
        "low": quote.get("low", []),
        "close": quote.get("close", []),
        "volume": quote.get("volume", []),
        "meta": result.get("meta", {}),
    }


def search(query: str, max_results: int = 5) -> list[dict]:
    """Search for tickers. Returns list of {symbol, shortname, exchDisp, ...}."""
    data = _get(_SEARCH_URL, {"q": query, "quotesCount": max_results})
    return data.get("quotes", [])[:max_results]


def fetch_news(ticker: str, max_items: int = 8) -> list[dict]:
    """Fetch latest news for a ticker."""
    data = _post(
        _NEWS_URL,
        {"queryRef": "latestNews", "serviceKey": "ncp_fin"},
        {"serviceConfig": {"snippetCount": max_items, "s": [ticker]}},
    )
    stream = data.get("data", {}).get("tickerStream", {}).get("stream", [])
    return [article for article in stream if not article.get("ad", [])]


def validate_ticker(ticker: str) -> bool:
    """Check if a ticker exists and has price data."""
    try:
        data = _get(f"{_CHART_URL}/{ticker}", {"range": "1d", "interval": "1d"})
        results = data.get("chart", {}).get("result")
        return results is not None and len(results) > 0
    except Exception:
        logger.debug("Ticker validation failed for %s", ticker)
        return False
