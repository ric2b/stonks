from stonks.models.database import (
    add_ticker,
    get_cached_prices,
    get_watchlist,
    remove_ticker,
    reorder_watchlist,
    upsert_prices,
)


def test_add_and_get_watchlist(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    watchlist = get_watchlist(db)
    assert len(watchlist) == 2
    assert watchlist[0]["ticker"] == "AAPL"
    assert watchlist[1]["ticker"] == "MSFT"
    assert watchlist[0]["position"] < watchlist[1]["position"]


def test_add_duplicate_ticker(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "AAPL")
    assert len(get_watchlist(db)) == 1


def test_add_ticker_uppercases(db):
    add_ticker(db, "aapl")
    watchlist = get_watchlist(db)
    assert watchlist[0]["ticker"] == "AAPL"


def test_remove_ticker(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    remove_ticker(db, "AAPL")
    watchlist = get_watchlist(db)
    assert len(watchlist) == 1
    assert watchlist[0]["ticker"] == "MSFT"


def test_remove_ticker_clears_price_cache(db):
    add_ticker(db, "AAPL")
    upsert_prices(db, "AAPL", [{"date": "2024-01-01", "close": 150.0}])
    remove_ticker(db, "AAPL")
    assert get_cached_prices(db, "AAPL", "2024-01-01", "2024-12-31") == []


def test_reorder_watchlist(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    add_ticker(db, "GOOGL")
    reorder_watchlist(db, ["GOOGL", "AAPL", "MSFT"])
    watchlist = get_watchlist(db)
    assert [w["ticker"] for w in watchlist] == ["GOOGL", "AAPL", "MSFT"]


def test_upsert_and_get_cached_prices(db):
    rows = [
        {
            "date": "2024-01-01",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 103.0,
            "volume": 1000000,
        },
        {
            "date": "2024-01-02",
            "open": 103.0,
            "high": 107.0,
            "low": 102.0,
            "close": 106.0,
            "volume": 1200000,
        },
    ]
    upsert_prices(db, "AAPL", rows)
    cached = get_cached_prices(db, "AAPL", "2024-01-01", "2024-01-02")
    assert len(cached) == 2
    assert cached[0]["close"] == 103.0
    assert cached[1]["volume"] == 1200000


def test_upsert_replaces_existing(db):
    upsert_prices(db, "AAPL", [{"date": "2024-01-01", "close": 100.0}])
    upsert_prices(db, "AAPL", [{"date": "2024-01-01", "close": 150.0}])
    cached = get_cached_prices(db, "AAPL", "2024-01-01", "2024-01-01")
    assert cached[0]["close"] == 150.0


def test_get_cached_prices_date_range(db):
    rows = [
        {"date": "2024-01-01", "close": 100.0},
        {"date": "2024-01-15", "close": 110.0},
        {"date": "2024-02-01", "close": 120.0},
    ]
    upsert_prices(db, "AAPL", rows)
    cached = get_cached_prices(db, "AAPL", "2024-01-10", "2024-01-20")
    assert len(cached) == 1
    assert cached[0]["date"] == "2024-01-15"
