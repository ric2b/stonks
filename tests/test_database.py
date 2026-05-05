from stonks.models.database import (
    add_ticker,
    get_watchlist,
    remove_ticker,
    reorder_watchlist,
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


def test_reorder_watchlist(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    add_ticker(db, "GOOGL")
    reorder_watchlist(db, ["GOOGL", "AAPL", "MSFT"])
    watchlist = get_watchlist(db)
    assert [w["ticker"] for w in watchlist] == ["GOOGL", "AAPL", "MSFT"]
