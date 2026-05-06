import numpy as np

from stonks.ui.chart_widget import _fill_closed_market_gaps, _price_decimals

# ── _price_decimals ─────────────────────────────────────────────────────────


def test_price_decimals_empty_array():
    assert _price_decimals(np.array([])) == 2


def test_price_decimals_single_value():
    assert _price_decimals(np.array([100.0])) == 2


def test_price_decimals_large_spread():
    assert _price_decimals(np.array([100.0, 200.0])) == 2


def test_price_decimals_medium_spread():
    assert _price_decimals(np.array([100.0, 105.0])) == 3


def test_price_decimals_small_spread():
    assert _price_decimals(np.array([1.00, 1.50])) == 4


def test_price_decimals_tiny_spread():
    assert _price_decimals(np.array([0.001, 0.002])) == 5


# ── _fill_closed_market_gaps ────────────────────────────────────────────────


def test_gap_fill_no_gaps():
    ts = np.array([1.0, 2.0, 3.0, 4.0])
    px = np.array([10.0, 11.0, 12.0, 13.0])
    new_ts, new_px = _fill_closed_market_gaps(ts, px)
    np.testing.assert_array_equal(new_ts, ts)
    np.testing.assert_array_equal(new_px, px)


def test_gap_fill_single_point():
    ts = np.array([1.0])
    px = np.array([10.0])
    new_ts, new_px = _fill_closed_market_gaps(ts, px)
    np.testing.assert_array_equal(new_ts, [1.0])
    np.testing.assert_array_equal(new_px, [10.0])


def test_gap_fill_inserts_synthetic_point():
    ts = np.array([1.0, 2.0, 3.0, 100.0])
    px = np.array([10.0, 11.0, 12.0, 15.0])
    new_ts, new_px = _fill_closed_market_gaps(ts, px)
    assert len(new_ts) == 5
    assert new_ts[3] == 99.0  # one second before the gap resumes
    assert new_px[3] == 12.0  # holds previous close


def test_gap_fill_multiple_gaps():
    ts = np.array([1.0, 2.0, 100.0, 101.0, 200.0])
    px = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    new_ts, new_px = _fill_closed_market_gaps(ts, px)
    assert len(new_ts) == 7
    assert new_px[2] == 11.0  # holds close before first gap
    assert new_px[5] == 13.0  # holds close before second gap


def test_gap_fill_two_points():
    ts = np.array([1.0, 2.0])
    px = np.array([10.0, 11.0])
    new_ts, new_px = _fill_closed_market_gaps(ts, px)
    np.testing.assert_array_equal(new_ts, ts)
    np.testing.assert_array_equal(new_px, px)
