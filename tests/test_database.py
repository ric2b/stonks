from stonks.models.database import (
    add_ticker,
    get_setting,
    get_watchlist,
    remove_ticker,
    reorder_watchlist,
    set_setting,
)


def test_empty_watchlist(db):
    assert get_watchlist(db) == []


def test_add_and_get_watchlist(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    watchlist = get_watchlist(db)
    assert len(watchlist) == 2
    assert watchlist[0]["ticker"] == "AAPL"
    assert watchlist[1]["ticker"] == "MSFT"
    assert watchlist[0]["position"] < watchlist[1]["position"]


def test_add_ticker_positions_are_sequential(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    add_ticker(db, "GOOGL")
    positions = [w["position"] for w in get_watchlist(db)]
    assert positions == sorted(positions)
    assert len(set(positions)) == 3  # all distinct


def test_add_duplicate_ticker(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "AAPL")
    assert len(get_watchlist(db)) == 1


def test_add_ticker_uppercases(db):
    add_ticker(db, "aapl")
    assert get_watchlist(db)[0]["ticker"] == "AAPL"


def test_remove_ticker(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    remove_ticker(db, "AAPL")
    watchlist = get_watchlist(db)
    assert len(watchlist) == 1
    assert watchlist[0]["ticker"] == "MSFT"


def test_remove_ticker_case_insensitive(db):
    add_ticker(db, "AAPL")
    remove_ticker(db, "aapl")
    assert get_watchlist(db) == []


def test_remove_nonexistent_ticker_is_harmless(db):
    add_ticker(db, "AAPL")
    remove_ticker(db, "MSFT")
    assert len(get_watchlist(db)) == 1


def test_reorder_watchlist(db):
    add_ticker(db, "AAPL")
    add_ticker(db, "MSFT")
    add_ticker(db, "GOOGL")
    reorder_watchlist(db, ["GOOGL", "AAPL", "MSFT"])
    assert [w["ticker"] for w in get_watchlist(db)] == ["GOOGL", "AAPL", "MSFT"]


def test_get_setting_returns_default_when_missing(db):
    assert get_setting(db, "nonexistent") == ""
    assert get_setting(db, "nonexistent", "fallback") == "fallback"


def test_set_and_get_setting(db):
    set_setting(db, "last_ticker", "AAPL")
    assert get_setting(db, "last_ticker") == "AAPL"


def test_set_setting_overwrites(db):
    set_setting(db, "last_ticker", "AAPL")
    set_setting(db, "last_ticker", "MSFT")
    assert get_setting(db, "last_ticker") == "MSFT"


def test_settings_are_independent(db):
    set_setting(db, "last_ticker", "AAPL")
    set_setting(db, "last_period", "1M")
    assert get_setting(db, "last_ticker") == "AAPL"
    assert get_setting(db, "last_period") == "1M"
