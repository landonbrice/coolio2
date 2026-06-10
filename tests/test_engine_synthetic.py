"""
Offline engine tests using SYNTHETIC prices.

The point: validate the backtest math (weighting, capping, rebalancing,
mark-to-market, point-in-time roster selection) without touching Yahoo, so the
engine is proven correct independently of live data access.

Run:  python -m tests.test_engine_synthetic
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from nasdaq_rebalancer import backtest, constituents, metrics


def synthetic_panel(tickers, start="2005-12-01", end="2025-12-31", seed=42):
    """Geometric-random-walk USD prices for every ticker over the window."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, end=end)
    cols = {}
    for i, t in enumerate(tickers):
        drift = 0.0002 + 0.0001 * (i % 5)        # small per-name drift
        vol = 0.012 + 0.002 * (i % 3)
        steps = rng.normal(drift, vol, len(dates))
        price = 50.0 * np.exp(np.cumsum(steps))
        cols[t] = price
    return pd.DataFrame(cols, index=dates)


def test_apply_cap():
    # Feasible case: 5 names, 25% cap (5*0.25=1.25 >= 1).
    w = {"A": 0.60, "B": 0.20, "C": 0.10, "D": 0.05, "E": 0.05}
    capped = backtest._apply_cap(w, cap=0.25)
    assert abs(sum(capped.values()) - 1.0) < 1e-9, "weights must sum to 1"
    assert all(v <= 0.25 + 1e-9 for v in capped.values()), "no weight may exceed cap"
    # Infeasible case: 3 names at 20% -> falls back to equal weights.
    fb = backtest._apply_cap({"A": 0.6, "B": 0.25, "C": 0.15}, cap=0.20)
    assert abs(sum(fb.values()) - 1.0) < 1e-9, "infeasible cap falls back to sum-1"
    assert all(abs(v - 1 / 3) < 1e-9 for v in fb.values()), "fallback is equal weight"
    print("  ok: _apply_cap caps, renormalizes, and handles infeasible caps")


def test_weights_sum_to_one():
    tickers = constituents.all_tickers("us10")
    prices = synthetic_panel(tickers)
    for weighting in ("capweight", "capweight_cap20", "equal"):
        dropped = {}
        w = backtest._target_weights(
            "us10", pd.Timestamp("2015-01-02"), prices, weighting, dropped
        )
        assert abs(sum(w.values()) - 1.0) < 1e-6, f"{weighting} weights must sum to 1"
        if weighting == "equal":
            vals = list(w.values())
            assert max(vals) - min(vals) < 1e-9, "equal weights must be identical"
        if weighting == "capweight_cap20":
            assert all(v <= 0.20 + 1e-9 for v in w.values()), "cap20 must hold"
    print("  ok: target weights sum to 1 for all three weightings")


def test_point_in_time_roster():
    # On 2008-06-01 the us10 roster must be the 2007-12-31 snapshot, NOT a later one.
    roster = constituents.members_asof("us10", pd.Timestamp("2008-06-01").to_pydatetime())
    tickers = {t for t, _ in roster}
    assert "GE" in tickers, "2007 roster should contain GE (point-in-time)"
    assert "NVDA" not in tickers, "must NOT see 2020s names in 2008 (no look-ahead)"
    print("  ok: point-in-time roster selection (no look-ahead)")


def test_full_run_sane():
    for universe in ("nasdaq10", "us10", "global10"):
        tickers = constituents.all_tickers(universe)
        prices = synthetic_panel(tickers)
        res = backtest.run_backtest(
            universe, prices, "2006-01-01", "2025-12-31",
            weighting="capweight", cost_bps=10,
        )
        eq = res.equity
        assert eq.iloc[0] == 1.0, "equity starts at 1.0"
        assert eq.notna().all(), "no NaNs in equity curve"
        assert (eq > 0).all(), "equity stays positive"
        # ~4 rebalances/year over 20 years -> ~80 (allow slack for first-day seed).
        assert 70 <= len(res.rebalance_dates) <= 90, \
            f"{universe}: unexpected rebalance count {len(res.rebalance_dates)}"
        st = metrics.compute(eq)
        assert 18 < st.years < 22, "span should be ~20 years"
        print(f"  ok: {universe} full run -> {len(res.rebalance_dates)} rebalances, "
              f"{st.multiple:.2f}x, CAGR {st.cagr*100:.1f}%")


def test_cost_reduces_return():
    tickers = constituents.all_tickers("us10")
    prices = synthetic_panel(tickers)
    free = backtest.run_backtest("us10", prices, "2006-01-01", "2025-12-31",
                                 weighting="capweight", cost_bps=0)
    pricey = backtest.run_backtest("us10", prices, "2006-01-01", "2025-12-31",
                                   weighting="capweight", cost_bps=50)
    assert pricey.equity.iloc[-1] < free.equity.iloc[-1], \
        "higher transaction costs must lower the ending value"
    print("  ok: transaction costs reduce ending value monotonically")


def main():
    tests = [
        test_apply_cap,
        test_weights_sum_to_one,
        test_point_in_time_roster,
        test_full_run_sane,
        test_cost_reduces_return,
    ]
    print("Running synthetic engine tests...")
    for t in tests:
        t()
    print(f"\nAll {len(tests)} test groups passed.")


if __name__ == "__main__":
    sys.exit(main())
