"""
The backtest engine (ledger-based).

Strategy: on the first trading day of each quarter, look up the point-in-time
top-10 roster for the universe and move the portfolio toward target weights.
Dividends are reinvested implicitly (prices are auto-adjusted).

This version tracks a per-name LEDGER (shares, average cost basis, acquisition
date) so it can model:

  * transaction costs (bps on traded notional),
  * capital-gains TAX on realized gains at each rebalance (long- vs short-term
    rate chosen by how long the position has been held),
  * rebalancing MODE:
      - "full"       : trade every name back to target (the textbook strategy),
      - "drift_band" : only trade a name when its weight has drifted more than
                       `drift_band` from target (fewer taxable events),
      - "no_sell"    : never trim a winner; only sell names that drop OUT of the
                       top 10, and steer new cash / sale proceeds into underweights
                       (closest to how a tax-conscious person actually rebalances),
  * optional periodic CONTRIBUTIONS of new cash at each rebalance.

With the defaults (full mode, cost=0, tax=0, contribution=0) the result is the
plain "growth of $1" curve and is identical to the simple model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from . import constituents


@dataclass
class Params:
    weighting: str = "capweight"
    cost_bps: float = 0.0
    tax_long: float = 0.0          # long-term cap-gains rate (held >= 1y)
    tax_short: float = 0.0         # short-term cap-gains rate (held < 1y)
    mode: str = "full"             # full | drift_band | no_sell
    drift_band: float = 0.0        # e.g. 0.05 = 5 percentage points
    contribution: float = 0.0      # new cash added at each rebalance
    top_n: Optional[int] = None    # hold only the top N names (None = whole roster, i.e. 10)
    interval: str = "Q"            # rebalance cadence: M | Q | SA | A


@dataclass
class BacktestResult:
    universe: str
    weighting: str
    equity: pd.Series                 # total portfolio value over time (base 1.0)
    rebalance_dates: List[pd.Timestamp]
    turnover: List[float]             # one-way turnover fraction at each rebalance
    rosters: List[Dict] = field(default_factory=list)
    dropped: Dict[str, int] = field(default_factory=dict)
    total_tax: float = 0.0            # cumulative tax paid, in units of base $1
    total_cost: float = 0.0          # cumulative transaction cost
    total_contrib: float = 0.0       # cumulative contributions added


def quarter_starts(start: str, end: str) -> List[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end, freq="QS"))


# Rebalance cadence -> pandas period-start frequency.
#   M  = monthly, Q = quarterly, SA = semiannual (every 2 quarters), A = annual.
_INTERVAL_FREQ = {"M": "MS", "Q": "QS", "SA": "2QS", "A": "YS"}


def period_starts(start: str, end: str, interval: str = "Q") -> List[pd.Timestamp]:
    """Rebalance dates for a given cadence (first calendar day of each period)."""
    freq = _INTERVAL_FREQ.get(interval)
    if freq is None:
        raise ValueError(f"unknown interval {interval!r}; use one of {list(_INTERVAL_FREQ)}")
    return list(pd.date_range(start=start, end=end, freq=freq))


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
    s = prices[ticker].loc[:when].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _apply_cap(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    """Iteratively cap any weight at `cap`, redistributing excess pro-rata.

    If the cap is mathematically infeasible (n * cap < 1) we fall back to equal
    weights -- the closest feasible answer -- rather than under-allocating.
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


def _target_weights(
    universe: str,
    rebal_date: pd.Timestamp,
    prices: pd.DataFrame,
    weighting: str,
    dropped: Dict[str, int],
    top_n: Optional[int] = None,
) -> Dict[str, float]:
    """Target weights for the names we can actually price on the rebalance date.

    `top_n` slices the (cap-ranked) roster to the largest N names before pricing,
    so top_n=1/3/5 hold only the biggest 1/3/5 companies. None = whole roster.
    """
    roster = constituents.members_asof(universe, rebal_date.to_pydatetime())
    if top_n is not None:
        roster = roster[:top_n]
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
        return {t: 1.0 / len(priceable) for t in priceable}

    est_caps = {}
    for ticker, (cap, px_now, snap_date) in priceable.items():
        ref = _price_on_or_before(prices, ticker, snap_date)
        est_caps[ticker] = cap * (px_now / ref) if (ref and ref > 0) else cap
    total = sum(est_caps.values())
    weights = {t: c / total for t, c in est_caps.items()}
    if weighting == "capweight_cap20":
        weights = _apply_cap(weights, cap=0.20)
    return weights


def _rebalance(ledger, cash, day, weights, prices, p: Params):
    """Mutate `ledger` toward `weights`; return (cash, turnover, tax, cost)."""
    names = set(weights) | set(ledger)
    price = {t: _price_on_or_before(prices, t, day) for t in names}
    price = {t: px for t, px in price.items() if px and px > 0}

    invested = sum(ledger[t]["shares"] * price[t] for t in ledger if t in price)
    V = cash + invested
    if V <= 0:
        return cash, 0.0, 0.0, 0.0

    roster = set(weights)
    target_v = {t: V * w for t, w in weights.items()}
    cur_v = {t: ledger.get(t, {}).get("shares", 0.0) * price.get(t, 0.0) for t in names}

    sells, buys = [], []
    for t in names:
        if t not in price:
            continue
        cur, tgt = cur_v.get(t, 0.0), target_v.get(t, 0.0)
        held = ledger.get(t)
        if p.mode == "no_sell":
            if t not in roster:
                if held and held["shares"] > 0:
                    sells.append((t, held["shares"], price[t]))   # forced exit
            elif tgt > cur:
                buys.append((t, (tgt - cur) / price[t], price[t]))  # buy-only
        elif p.mode == "drift_band":
            forced_sell = held and held["shares"] > 0 and t not in roster
            new_entrant = t in roster and not held
            drift = abs(cur - tgt) / V
            if forced_sell or new_entrant or drift > p.drift_band:
                d = (tgt - cur) / price[t]
                (sells if d < 0 else buys).append((t, abs(d), price[t]))
        else:  # full
            d = (tgt - cur) / price[t]
            if d < -1e-12:
                sells.append((t, -d, price[t]))
            elif d > 1e-12:
                buys.append((t, d, price[t]))

    tax = cost = turnover = 0.0
    cost_rate = p.cost_bps / 1e4

    # Execute sells -> realize gains, pay cost, raise cash.
    for t, sh, px in sells:
        lot = ledger.get(t)
        if not lot:
            continue
        sh = min(sh, lot["shares"])
        proceeds = sh * px
        gain = sh * (px - lot["basis"])
        rate = p.tax_long if (day - lot["acquired"]).days >= 365 else p.tax_short
        tax += max(0.0, gain) * rate
        cost += proceeds * cost_rate
        turnover += proceeds
        lot["shares"] -= sh
        if lot["shares"] <= 1e-9:
            del ledger[t]
        sell_cost = proceeds * cost_rate
        cost += sell_cost
        cash += proceeds - sell_cost          # net sell-side cost out immediately
    cash -= tax

    # Execute buys, scaled to whatever cash remains (after tax + sell costs),
    # reserving the buy-side transaction cost so cash can never go negative.
    desired = sum(sh * px for _t, sh, px in buys)
    if desired > 0 and cash > 0:
        scale = min(1.0, cash / (desired * (1.0 + cost_rate)))
        for t, sh, px in buys:
            sh *= scale
            spend = sh * px
            if sh <= 1e-12:
                continue
            buy_cost = spend * cost_rate
            cost += buy_cost
            turnover += spend
            if t in ledger:
                lot = ledger[t]
                tot = lot["shares"] + sh
                lot["basis"] = (lot["basis"] * lot["shares"] + px * sh) / tot
                lot["shares"] = tot
            else:
                ledger[t] = {"shares": sh, "basis": px, "acquired": day}
            cash -= spend + buy_cost
    return cash, (turnover / (2.0 * V)), tax, cost


def run_backtest(
    universe: str,
    prices: pd.DataFrame,
    start: str,
    end: str,
    weighting: str = "capweight",
    cost_bps: float = 0.0,
    tax_long: float = 0.0,
    tax_short: float = 0.0,
    mode: str = "full",
    drift_band: float = 0.0,
    contribution: float = 0.0,
    top_n: Optional[int] = None,
    interval: str = "Q",
) -> BacktestResult:
    p = Params(weighting=weighting, cost_bps=cost_bps, tax_long=tax_long,
               tax_short=tax_short, mode=mode, drift_band=drift_band,
               contribution=contribution, top_n=top_n, interval=interval)

    cal = prices.loc[start:end].index
    if len(cal) == 0:
        raise ValueError("No price data in the requested window.")

    qs = period_starts(start, end, interval)
    trade_dates = []
    for qd in qs:
        nxt = cal[cal >= qd]
        if len(nxt):
            trade_dates.append(nxt[0])
    if not trade_dates or trade_dates[0] > cal[0]:
        trade_dates = [cal[0]] + trade_dates
    trade_dates = sorted(set(trade_dates))

    equity = pd.Series(index=cal, dtype=float)
    ledger: Dict[str, dict] = {}
    cash = 1.0
    turnovers: List[float] = []
    rosters: List[Dict] = []
    dropped: Dict[str, int] = {}
    total_tax = total_cost = total_contrib = 0.0

    reb_idx = 0
    for i, day in enumerate(cal):
        if reb_idx < len(trade_dates) and day == trade_dates[reb_idx]:
            if reb_idx > 0 and p.contribution > 0:   # no contribution at inception
                cash += p.contribution
                total_contrib += p.contribution
            target = _target_weights(universe, day, prices, weighting, dropped, p.top_n)
            if target:
                cash, turn, tax, cost = _rebalance(ledger, cash, day, target, prices, p)
                turnovers.append(turn)
                total_tax += tax
                total_cost += cost
                rosters.append({"date": day,
                                "weights": {t: round(w, 4) for t, w in target.items()}})
            reb_idx += 1

        value = cash + sum(
            led["shares"] * (_price_on_or_before(prices, t, day) or 0.0)
            for t, led in ledger.items()
        )
        equity.iloc[i] = value

    equity = equity.ffill().dropna()
    base = equity.iloc[0]
    equity = equity / base
    return BacktestResult(
        universe=universe, weighting=weighting, equity=equity,
        rebalance_dates=trade_dates, turnover=turnovers, rosters=rosters,
        dropped=dropped, total_tax=total_tax / base, total_cost=total_cost / base,
        total_contrib=total_contrib / base,
    )
