import logging
import time

from PySide6.QtCore import QThread, Signal

from stonks.services.stock_data import (
    batch_fetch_history,
    fetch_currencies,
    fetch_info,
    fetch_names,
    fetch_news,
    fetch_prices,
    populate_history_cache,
    search_tickers,
    validate_ticker,
)

logger = logging.getLogger(__name__)


_closing_workers: list[QThread] = []


def shutdown_workers(workers: list[QThread]) -> None:
    for w in workers:
        w.requestInterruption()
        w.quit()
    _closing_workers.extend(w for w in workers if w.isRunning())
    workers.clear()


def wait_for_closing_workers(timeout_ms: int = 2000) -> None:
    for w in _closing_workers:
        w.wait(timeout_ms)


class ValidateWorker(QThread):
    finished = Signal(bool, str)
    error = Signal(str)

    def __init__(self, ticker: str):
        super().__init__()
        self.setObjectName(f'ValidateWorker({ticker})')
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
        self.setObjectName(f'HistoryWorker({ticker},{period},{interval})')
        self.ticker = ticker
        self.period = period
        self.interval = interval

    def run(self):
        try:
            from stonks.services.stock_data import fetch_history

            df = fetch_history(self.ticker, self.period, self.interval)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))


class InfoWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ticker: str):
        super().__init__()
        self.setObjectName(f'InfoWorker({ticker})')
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
        self.setObjectName(f'SearchWorker({query})')
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
        self.setObjectName(f'PriceUpdateWorker({",".join(tickers)})')
        self.tickers = tickers

    def run(self):
        try:
            results, no_data = fetch_prices(self.tickers)
            missing = [t for t in self.tickers if t not in results and t not in no_data]
            delay = 0.5
            while missing and not self.isInterruptionRequested():
                time.sleep(delay)
                delay = min(delay * 2, 10)
                new_results, new_no_data = fetch_prices(missing)
                results.update(new_results)
                no_data.update(new_no_data)
                missing = [t for t in self.tickers if t not in results and t not in no_data]
            self.finished.emit(results)
        except Exception as e:
            logger.debug("Price fetch failed: %s", e)
            self.error.emit(str(e))


class NameFetchWorker(QThread):
    finished = Signal(dict, dict)

    def __init__(self, tickers: list[str]):
        super().__init__()
        self.setObjectName(f'NameFetchWorker({",".join(tickers)})')
        self.tickers = tickers

    def run(self):
        try:
            names = fetch_names(self.tickers)
            currencies = fetch_currencies(self.tickers)
            self.finished.emit(names, currencies)
        except Exception as e:
            logger.debug("Name fetch failed: %s", e)


class NewsWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, ticker: str):
        super().__init__()
        self.setObjectName(f'NewsWorker({ticker})')
        self.ticker = ticker

    def run(self):
        try:
            items = fetch_news(self.ticker)
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))


class PrefetchWorker(QThread):
    # No custom finished signal — QThread.finished fires exactly once when run()
    # returns, avoiding the double-emit that occurs when shadowing it with Signal().

    def __init__(self, tickers: list[str], period: str, interval: str):
        super().__init__()
        self.setObjectName(f'PrefetchWorker({",".join(tickers)})')
        self.tickers = tickers
        self.period = period
        self.interval = interval

    def run(self):
        try:
            results = batch_fetch_history(
                self.tickers, self.period, self.interval,
                cancelled=self.isInterruptionRequested,
            )
            populate_history_cache(results, self.period, self.interval)
        except Exception as e:
            logger.debug("Prefetch failed: %s", e)
