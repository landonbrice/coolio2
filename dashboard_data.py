#!/usr/bin/env python3
"""
DATA LAYER for the live rebalancing-bot dashboard (coolio2).

Single responsibility: produce ``output/dashboard_state.json``. It ALWAYS
succeeds and ALWAYS writes a valid state file -- LIVE if Yahoo is reachable,
CACHED otherwise (the parquet price panel + benchmark cache make the offline
path work with no network). It writes NO HTML.

This module REUSES the existing engine by name (it never reimplements
target-weight or pricing logic):

  * nasdaq_rebalancer.constituents  -- point-in-time roster + names/metadata
  * nasdaq_rebalancer.prices        -- cached USD adjusted-close price panel
  * nasdaq_rebalancer.backtest      -- _target_weights (price-drift cap scaling)
  * nasdaq_rebalancer.benchmark     -- S&P 500 total-return series
  * rebalance_now                   -- live cap->weight helper + load_holdings

RESEARCH / NOT FINANCIAL ADVICE. The bot recommends; a human trades. No order
placement, no auto-trade, no yfinance writes -- output is advisory JSON only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

from nasdaq_rebalancer import backtest, benchmark, constituents, prices
from rebalance_now import load_holdings
from rebalance_now import target_weights_from_caps as rebalance_now_target_weights

# ---------------------------------------------------------------------------
# FROZEN PARAMETERS (module constants -- the build defaults the data layer
# hardcodes; see the IMPLEMENTATION SPEC). Bare ``python dashboard_data.py``
# must reproduce the sample JSON shape, so these are the argparse defaults too.
# ---------------------------------------------------------------------------
UNIVERSE = "nasdaq10"        # the validated edge cell per docs/RESULTS.md
WEIGHTING = "capweight"      # most tax-robust, on the efficient frontier
TOP_N = 10
DEPLOY_CASH = 3000.0         # fresh cash to deploy in the demo
DRIFT_BAND = 0.05            # 5 percentage-point alert/trade band
MIN_TRADE = 50.0             # ignore buy/sell actions smaller than this $
CADENCE = "Q"               # quarterly; drives next_rebalance_date
HOLDINGS_PATH = "holdings.json"  # load if present, else all-cash $DEPLOY_CASH
START = "2006-01-01"         # window start for price panel + benchmark

OUT = os.environ.get("REBAL_OUTPUT_DIR", "output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def last_panel_px(panel: pd.DataFrame, t: str):
    """Last non-null price for ticker ``t`` in the cached panel, or None."""
    if t not in panel.columns:
        return None
    s = panel[t].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def try_live_caps(tickers):
    """Return (caps:dict[t->float], px:dict[t->float], ok:bool). Never raises.

    Modeled on rebalance_now.live_market_caps but hardened so the cloud sandbox
    403/offline path silently falls through to the cached panel. Market cap is
    Yahoo's fast_info.market_cap (current price x shares outstanding) -- no
    fragile shares-outstanding API, and we never touch the slow/rate-limited
    .info scrape.
    """
    try:
        import yfinance as yf
    except Exception:
        return {}, {}, False
    caps, px = {}, {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info               # battle-tested, no .info scrape
            mc = getattr(fi, "market_cap", None) or (fi.get("market_cap") if hasattr(fi, "get") else None)
            last = getattr(fi, "last_price", None) or (fi.get("last_price") if hasattr(fi, "get") else None)
            if mc and last and float(mc) > 0 and float(last) > 0:
                caps[t] = float(mc)
                px[t] = float(last)
        except Exception:
            continue                                  # skip names we can't price live
    ok = len([c for c in caps.values() if c > 0]) >= TOP_N   # need a full top-10 to trust "live"
    return caps, px, ok


def next_rebalance(today: pd.Timestamp):
    """First calendar day of the next Jan/Apr/Jul/Oct strictly after today."""
    q_months = [1, 4, 7, 10]
    y, m = today.year, today.month
    nxt = next((mm for mm in q_months if mm > m), None)
    s = f"{y + 1}-01-01" if nxt is None else f"{y}-{nxt:02d}-01"
    d = pd.Timestamp(s)
    days = int((d.normalize() - today.normalize()).days)
    return s, days


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--deploy-cash", type=float, default=DEPLOY_CASH,
                   help="fresh cash to deploy in the plan (default %(default)s)")
    p.add_argument("--universe", default=UNIVERSE,
                   choices=["nasdaq10", "us10", "global10"],
                   help="constituent universe (default %(default)s)")
    p.add_argument("--weighting", default=WEIGHTING,
                   choices=["capweight", "capweight_cap20", "equal"],
                   help="target weighting scheme (default %(default)s)")
    p.add_argument("--top-n", type=int, default=TOP_N,
                   help="hold the top N names (default %(default)s)")
    p.add_argument("--holdings", default=HOLDINGS_PATH,
                   help="path to holdings JSON (default %(default)s)")
    return p.parse_args(argv)


def build_state(deploy_cash, universe, weighting, top_n, holdings_path):
    """Compute the full dashboard state dict. Never raises on missing live data.

    Raises only if there is genuinely nothing to show (no cached panel AND live
    failed); main() catches that and writes a minimal error state.
    """
    notes = []
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    TODAY = pd.Timestamp(date.today())

    # --- candidate tickers + cached price panel (the offline backbone) -------
    candidates = constituents.all_tickers(universe)
    panel = prices.get_price_panel(
        candidates, START, TODAY.strftime("%Y-%m-%d"), use_cache=True
    )

    # --- cached-fallback weights (source of truth; always works) -------------
    dropped: dict = {}
    cached_weights = backtest._target_weights(
        universe, TODAY, panel, weighting, dropped, top_n=top_n
    )
    if dropped:
        notes.append(
            "Could not price (dropped from target): "
            + ", ".join(f"{t} x{n}" for t, n in sorted(dropped.items()))
        )
    if not cached_weights:
        raise RuntimeError("no priceable names in cached panel")

    # implied current caps (cached path), mirroring _target_weights' est_caps so
    # the displayed cap is internally consistent with the weight.
    snap = backtest._snapshot_date_for(universe, TODAY.to_pydatetime())
    roster_caps = dict(constituents.members_asof(universe, TODAY.to_pydatetime()))  # billions

    def implied_cap_usd(t):
        ref = backtest._price_on_or_before(panel, t, snap)
        cap_b = roster_caps.get(t, 0.0)
        lpx = last_panel_px(panel, t)
        val_b = cap_b * (lpx / ref) if (ref and ref > 0 and lpx) else cap_b
        return val_b * 1e9

    # --- attempt live (promote to "live" only with a usable ranked top-10) ---
    live_caps, live_px, live_ok = try_live_caps(candidates)
    if live_ok:
        top10_live = dict(sorted(live_caps.items(), key=lambda kv: kv[1], reverse=True)[:top_n])
        weights = rebalance_now_target_weights(top10_live, weighting)
        market_caps = dict(top10_live)                # absolute $ caps from Yahoo
        px = dict(live_px)
        data_source = "live"
        price_as_of = as_of[:10]
        notes.append(
            "Live market caps via Yahoo fast_info (current price x shares "
            "outstanding); target weights cap-weighted over today's top-10."
        )
    else:
        weights = cached_weights
        market_caps = {t: implied_cap_usd(t) for t in weights}
        px = {t: (last_panel_px(panel, t) or 0.0) for t in weights}
        data_source = "cached"
        price_as_of = panel.index[-1].strftime("%Y-%m-%d")
        notes.append(
            f"Live market-cap fetch unavailable (Yahoo unreachable); using cached "
            f"price panel through {price_as_of} with engine price-drift cap scaling."
        )
        notes.append(
            f"Target weights are current-cap-weighted over the point-in-time "
            f"{universe} roster (snapshot {snap.strftime('%Y-%m-%d')})."
        )

    # ranked top-10 (by target weight, highest first)
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    top10 = [
        {
            "ticker": t,
            "name": constituents.name_of(t),
            "market_cap": float(market_caps.get(t, 0.0)),
            "rank": i,
            "target_weight": float(w),
        }
        for i, (t, w) in enumerate(ranked, 1)
    ]
    rank_of = {row["ticker"]: row["rank"] for row in top10}

    # --- deployment plan ($deploy_cash of FRESH cash; all BUY) ---------------
    deployment_plan = []
    for t, w in ranked:
        price_t = px.get(t) or last_panel_px(panel, t) or 0.0
        dollars = deploy_cash * w
        shares = (dollars / price_t) if price_t > 0 else 0.0
        deployment_plan.append({
            "ticker": t,
            "name": constituents.name_of(t),
            "target_weight": float(w),
            "dollars": round(float(dollars), 2),
            "shares": round(float(shares), 4),
            "price": round(float(price_t), 2),
            "action": "BUY",
        })

    # --- holdings + portfolio summary ----------------------------------------
    holdings = load_holdings(holdings_path)            # {} -> cash 0 / no positions
    holdings_present = os.path.exists(holdings_path)

    if holdings_present:
        cash = float(holdings.get("cash", 0.0))
        positions = {t: float(s) for t, s in holdings.get("positions", {}).items()}

        def price_for(t):
            return px.get(t) or last_panel_px(panel, t) or 0.0

        positions_value = 0.0
        for t, sh in positions.items():
            p_t = price_for(t)
            if p_t <= 0:
                notes.append(f"Held name {t} has no price; excluded from value.")
                continue
            positions_value += sh * p_t
        total_value = cash + positions_value
    else:
        cash = float(deploy_cash)
        positions = {}
        positions_value = 0.0
        total_value = float(deploy_cash)
        notes.append(
            f"No {holdings_path} found -- treating portfolio as all-cash "
            f"${deploy_cash:,.0f} starting position for the vs-holdings view."
        )

    portfolio = {
        "total_value": round(float(total_value), 2),
        "cash": round(float(cash), 2),
        "positions_value": round(float(positions_value), 2),
        "num_positions": int(len([s for s in positions.values() if s])),
        "positions": {t: positions[t] for t in positions},
        "holdings_present": holdings_present,
    }

    # --- vs-holdings comparison + drift alert --------------------------------
    target_names = set(weights)
    held_names = set(positions)
    rows = []
    drift_alert = False
    for t in (target_names | held_names):
        price_t = px.get(t) or last_panel_px(panel, t) or 0.0
        cur_shares = float(positions.get(t, 0.0))
        cur_val = cur_shares * price_t
        cur_w = (cur_val / total_value) if total_value > 0 else 0.0
        tgt_w = float(weights.get(t, 0.0))
        drift = cur_w - tgt_w                           # signed weight fraction
        tgt_val = total_value * tgt_w
        delta = tgt_val - cur_val                       # + = buy, - = sell

        new_entrant = (t in target_names) and (t not in held_names)
        dropped_out = (t in held_names) and (t not in target_names)

        if dropped_out:
            action = "SELL"
            delta = -cur_val                            # sell the whole position
        elif abs(drift) > DRIFT_BAND and abs(delta) >= MIN_TRADE:
            action = "BUY" if delta > 0 else "SELL"
        else:
            action = "HOLD"

        if abs(drift) > DRIFT_BAND:
            drift_alert = True

        rows.append({
            "ticker": t,
            "name": constituents.name_of(t),
            "current_shares": cur_shares,
            "price": round(float(price_t), 2),
            "current_value": round(float(cur_val), 2),
            "current_weight": round(float(cur_w), 4),
            "target_weight": round(float(tgt_w), 4),
            "drift": round(float(drift), 4),
            "action": action,
            "dollar_delta": round(float(delta), 2),
            "new_entrant": new_entrant,
            "dropped_out": dropped_out,
        })

    # sort: by target rank (top-10 first, in rank order), then ticker for the rest
    def sort_key(r):
        return (rank_of.get(r["ticker"], 10 ** 6), r["ticker"])

    rows.sort(key=sort_key)

    # --- next quarterly rebalance --------------------------------------------
    next_rebalance_date, days_to_rebalance = next_rebalance(TODAY)

    # --- benchmark context (reuse benchmark.load_sp500) ----------------------
    try:
        sp = benchmark.load_sp500(START, TODAY.strftime("%Y-%m-%d"), use_cache=True)
        spx_last = float(sp.iloc[-1])
        prior = sp[sp.index <= sp.index[-1] - pd.Timedelta(days=365)]
        spx_1y = float(prior.iloc[-1]) if not prior.empty else spx_last
        trailing_1y = (spx_last / spx_1y - 1.0) if spx_1y > 0 else 0.0
        symbol = "^SP500TR" if spx_last > 1000 else "SPY"
        bench = {
            "available": True,
            "symbol": symbol,
            "label": "S&P 500 (Total Return)",
            "level": round(spx_last, 2),
            "trailing_1y_return": round(trailing_1y, 4),
            "as_of": sp.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as exc:  # noqa: BLE001 - never abort on benchmark failure
        bench = {"available": False}
        notes.append(f"Benchmark unavailable ({exc}).")

    notes.append("Research / not financial advice. The bot recommends; a human trades.")

    state = {
        "as_of": as_of,
        "price_as_of": price_as_of,
        "data_source": data_source,
        "meta": {
            "universe": universe,
            "weighting": weighting,
            "top_n": top_n,
            "deploy_cash": float(deploy_cash),
            "drift_band": DRIFT_BAND,
            "cadence": CADENCE,
            "holdings_present": holdings_present,
            "holdings_path": holdings_path,
        },
        "top10": top10,
        "deployment_plan": deployment_plan,
        "portfolio": portfolio,
        "vs_holdings": rows,
        "drift_alert": drift_alert,
        "next_rebalance_date": next_rebalance_date,
        "days_to_rebalance": days_to_rebalance,
        "benchmark": bench,
        "notes": notes,
    }
    return state, data_source, as_of


def _write_atomic(state):
    os.makedirs(OUT, exist_ok=True)
    final = os.path.join(OUT, "dashboard_state.json")
    tmp = final + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, final)
    return final


def main(argv=None):
    args = parse_args(argv)
    try:
        state, data_source, as_of = build_state(
            args.deploy_cash, args.universe, args.weighting, args.top_n, args.holdings
        )
        _write_atomic(state)
        print(f"Wrote {os.path.join(OUT, 'dashboard_state.json')} "
              f"(source={data_source}, as_of={as_of})")
        return 0
    except Exception as exc:  # noqa: BLE001
        # Truly nothing to show: write a minimal error state so the HTML build
        # can still render an error card, and signal failure with a non-zero rc.
        as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        err_state = {
            "as_of": as_of,
            "price_as_of": "",
            "data_source": "cached",
            "meta": {
                "universe": args.universe, "weighting": args.weighting,
                "top_n": args.top_n, "deploy_cash": float(args.deploy_cash),
                "drift_band": DRIFT_BAND, "cadence": CADENCE,
                "holdings_present": os.path.exists(args.holdings),
                "holdings_path": args.holdings,
            },
            "top10": [], "deployment_plan": [],
            "portfolio": {
                "total_value": 0.0, "cash": 0.0, "positions_value": 0.0,
                "num_positions": 0, "positions": {}, "holdings_present": False,
            },
            "vs_holdings": [], "drift_alert": False,
            "next_rebalance_date": next_rebalance(pd.Timestamp(date.today()))[0],
            "days_to_rebalance": next_rebalance(pd.Timestamp(date.today()))[1],
            "benchmark": {"available": False},
            "notes": ["Catastrophic failure building dashboard state."],
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            _write_atomic(err_state)
            print(f"Wrote {os.path.join(OUT, 'dashboard_state.json')} "
                  f"(ERROR state: {exc})", file=sys.stderr)
        except Exception as exc2:  # noqa: BLE001
            print(f"FATAL: could not write error state: {exc2}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
