"""
The backtest engine.

Strategy, precisely:
  * On the first trading day of each quarter (the rebalance date), look up the
    point-in-time top-10 roster for the chosen universe.
  * Allocate the whole portfolio across those names by the chosen weighting:
      - "capweight"      : proportional to (estimated) current market cap
      - "capweight_cap20": cap-weighted but no name above 20%, excess redistributed
      - "equal"          : 10% each
  * Hold those share counts until the next quarter, letting prices drift.
  * Dividends are reinvested implicitly because we price off auto-adjusted closes.
  * Optional transaction cost (bps) is charged on turnover at each rebalance.

Cap-weight estimate: snapshot caps are year-end. At a rebalance date we scale
each name's snapshot cap by its price change since the snapshot date
(cap ~ shares x price, shares ~ roughly constant short-term), which recovers a
good estimate of the *current* cap without needing historical share counts.
Falls back to the raw snapshot cap if the snapshot-date price is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import constituents


@dataclass
class BacktestResult:
    universe: str
    weighting: str
    equity: pd.Series                 # portfolio value over time (starts at 1.0)
    rebalance_dates: List[pd.Timestamp]
    turnover: List[float]             # one-way turnover at each rebalance
    rosters: List[Dict] = field(default_factory=list)  # holdings snapshots
    dropped: Dict[str, int] = field(default_factory=dict)  # ticker -> times dropped


def quarter_starts(start: str, end: str) -> List[pd.Timestamp]:
    """First calendar day of each quarter in [start, end] (Jan/Apr/Jul/Oct 1)."""
    rng = pd.date_range(start=start, end=end, freq="QS")  # quarter start
    return list(rng)


def _snapshot_date_for(universe: str, as_of: datetime) -> pd.Timestamp:
    snaps = constituents.UNIVERSES[universe]
    chosen = sorted(snaps.keys())[0]
    for key in sorted(snaps.keys()):
        if datetime.strptime(key, "%Y-%m-%d") <= as_of:
            chosen = key
    return pd.Timestamp(chosen)


def _price_on_or_before(prices: pd.DataFrame, ticker: str, when: pd.Timestamp) -> Optional[float]:
    if ticker not in prices.columns:
        return None
    s = prices[ticker]
    s = s.loc[:when].dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _price_on_or_after(prices: pd.DataFrame, ticker: str, when: pd.Timestamp) -> Optional[float]:
    if ticker not in prices.columns:
        return None
    s = prices[ticker]
    s = s.loc[when:].dropna()
    if s.empty:
        return None
    return float(s.iloc[0])


def _target_weights(
    universe: str,
    rebal_date: pd.Timestamp,
    prices: pd.DataFrame,
    weighting: str,
    dropped: Dict[str, int],
) -> Dict[str, float]:
    """Weights for names we can actually price on the rebalance date."""
    roster = constituents.members_asof(universe, rebal_date.to_pydatetime())
    snap_date = _snapshot_date_for(universe, rebal_date.to_pydatetime())

    priceable = {}
    for ticker, cap in roster:
        px_now = _price_on_or_before(prices, ticker, rebal_date)
        if px_now is None or px_now <= 0:
            dropped[ticker] = dropped.get(ticker, 0) + 1
            continue
        priceable[ticker] = (cap, px_now, snap_date)

    if not priceable:
        return {}

    if weighting == "equal":
        w = {t: 1.0 / len(priceable) for t in priceable}
        return w

    # Cap-weighted: estimate current cap = snapshot_cap * price_now / price_at_snapshot
    est_caps = {}
    for ticker, (cap, px_now, snap_date) in priceable.items():
        ref = _price_on_or_before(prices, ticker, snap_date)
        if ref and ref > 0:
            est_caps[ticker] = cap * (px_now / ref)
        else:
            est_caps[ticker] = cap  # fall back to raw snapshot cap
    total = sum(est_caps.values())
    weights = {t: c / total for t, c in est_caps.items()}

    if weighting == "capweight_cap20":
        weights = _apply_cap(weights, cap=0.20)
    return weights


def _apply_cap(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    """Iteratively cap any weight at `cap`, redistributing excess pro-rata.

    If the cap is mathematically infeasible (n * cap < 1, i.e. too few names to
    absorb the weight) we fall back to equal weights -- the closest feasible
    answer -- rather than returning an under-allocated book.
    """
    n = len(weights)
    if n == 0:
        return {}
    if cap * n < 1.0 - 1e-9:
        return {t: 1.0 / n for t in weights}
    w = dict(weights)
    for _ in range(100):
        over = {t: x for t, x in w.items() if x > cap + 1e-12}
        if not over:
            break
        excess = sum(x - cap for x in over.values())
        for t in over:
            w[t] = cap
        under = {t: x for t, x in w.items() if x < cap - 1e-12}
        pool = sum(under.values())
        if pool <= 0:
            break
        for t in under:
            w[t] += excess * (under[t] / pool)
    return w


def run_backtest(
    universe: str,
    prices: pd.DataFrame,
    start: str,
    end: str,
    weighting: str = "capweight",
    cost_bps: float = 0.0,
) -> BacktestResult:
    """Run the quarterly-rebalanced top-10 strategy. Returns daily equity = 1.0 at start."""
    cal = prices.loc[start:end].index
    if len(cal) == 0:
        raise ValueError("No price data in the requested window.")

    rebal_dates = [d for d in quarter_starts(start, end)]
    # Map each quarter-start to the first available trading day on/after it.
    trade_dates = []
    for qd in rebal_dates:
        nxt = cal[cal >= qd]
        if len(nxt):
            trade_dates.append(nxt[0])
    # Ensure we start on the first trading day even if it isn't a quarter start.
    if not trade_dates or trade_dates[0] > cal[0]:
        trade_dates = [cal[0]] + trade_dates
    trade_dates = sorted(set(trade_dates))

    equity = pd.Series(index=cal, dtype=float)
    value = 1.0
    shares: Dict[str, float] = {}
    prev_weights: Dict[str, float] = {}
    turnovers: List[float] = []
    rosters: List[Dict] = []
    dropped: Dict[str, int] = {}

    reb_idx = 0
    for i, day in enumerate(cal):
        # Rebalance if today is a scheduled rebalance trading day.
        if reb_idx < len(trade_dates) and day == trade_dates[reb_idx]:
            # First, mark portfolio to today's prices using existing shares.
            if shares:
                value = sum(
                    sh * (_price_on_or_before(prices, t, day) or 0.0)
                    for t, sh in shares.items()
                )
            target = _target_weights(universe, day, prices, weighting, dropped)
            if target:
                # One-way turnover vs previous target weights (for cost + reporting).
                all_names = set(target) | set(prev_weights)
                turn = 0.5 * sum(
                    abs(target.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in all_names
                )
                turnovers.append(turn)
                value *= (1.0 - (cost_bps / 1e4) * turn)
                # Convert target weights into share counts at today's prices.
                shares = {}
                for t, w in target.items():
                    px = _price_on_or_before(prices, t, day)
                    if px and px > 0:
                        shares[t] = (value * w) / px
                prev_weights = target
                rosters.append({
                    "date": day,
                    "weights": {t: round(w, 4) for t, w in target.items()},
                })
            reb_idx += 1

        # Mark-to-market for the day.
        if shares:
            value = sum(
                sh * (_price_on_or_before(prices, t, day) or 0.0)
                for t, sh in shares.items()
            )
        equity.iloc[i] = value

    equity = equity.ffill().dropna()
    equity = equity / equity.iloc[0]  # normalize to 1.0 at inception
    return BacktestResult(
        universe=universe,
        weighting=weighting,
        equity=equity,
        rebalance_dates=trade_dates,
        turnover=turnovers,
        rosters=rosters,
        dropped=dropped,
    )
