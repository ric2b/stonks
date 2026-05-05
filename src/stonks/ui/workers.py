import logging

from PySide6.QtCore import QThread, Signal

from stonks.services.stock_data import fetch_history, fetch_info, search_tickers, validate_ticker

logger = logging.getLogger(__name__)


class ValidateWorker(QThread):
    finished = Signal(bool, str)
    error = Signal(str)

    def __init__(self, ticker: str):
        super().__init__()
        self.ticker = ticker

    def run(self):
        try:
            valid = validate_ticker(self.ticker)
            self.finished.emit(valid, self.ticker)
        except Exception as e:
            self.error.emit(str(e))


class HistoryWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, ticker: str, period: str, interval: str):
        super().__init__()
        self.ticker = ticker
        self.period = period
        self.interval = interval

    def run(self):
        try:
            df = fetch_history(self.ticker, self.period, self.interval)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))


class InfoWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ticker: str):
        super().__init__()
        self.ticker = ticker

    def run(self):
        try:
            info = fetch_info(self.ticker)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class SearchWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            results = search_tickers(self.query)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class PriceUpdateWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, tickers: list[str]):
        super().__init__()
        self.tickers = tickers

    def run(self):
        results = {}
        for ticker in self.tickers:
            try:
                df = fetch_history(ticker, "2d", "1d")
                if len(df) >= 2:
                    price = df["Close"].iloc[-1]
                    prev = df["Close"].iloc[-2]
                    change_pct = ((price - prev) / prev) * 100
                elif len(df) == 1:
                    price = df["Close"].iloc[-1]
                    change_pct = 0.0
                else:
                    continue
                results[ticker] = (float(price), float(change_pct))
            except Exception:
                logger.debug("Failed to fetch price for %s", ticker)
        self.finished.emit(results)
