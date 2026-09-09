#!/usr/bin/env python3
"""
The reminder/recommendation tool. Run this (e.g. quarterly, via your OS
scheduler) to see TODAY's target top-10 portfolio and exactly what to buy/sell to
get there from your current holdings.

USAGE (on a machine that can reach Yahoo Finance):

    python rebalance_now.py                       # uses us10, cap-weighted
    python rebalance_now.py --universe nasdaq10
    python rebalance_now.py --holdings holdings.json --notify

It will:
  1. Pull LIVE market caps for the candidate names and rank the current top 10.
  2. Compute your target dollar allocation (cap-weighted by default).
  3. Compare to your current holdings (holdings.json) and print BUY/SELL/HOLD.
  4. Flag any name that dropped OUT of the top 10 (sell it) or is NEW IN (buy it).
  5. Optionally fire a desktop notification (--notify).

holdings.json format:
    { "cash": 2500.0, "positions": { "AAPL": 12, "MSFT": 5, "NVDA": 8 } }
(positions are SHARE counts). See holdings.example.json.

NOT financial advice. It tells you what the mechanical strategy implies; you
decide whether to act, and you bear the tax consequences.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

from nasdaq_rebalancer import backtest, constituents


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--universe", default="us10", choices=["nasdaq10", "us10", "global10"])
    p.add_argument("--weighting", default="capweight",
                   choices=["capweight", "capweight_cap20", "equal"])
    p.add_argument("--holdings", default="holdings.json",
                   help="path to your holdings JSON (optional)")
    p.add_argument("--notify", action="store_true", help="fire a desktop notification")
    p.add_argument("--min-trade", type=float, default=50.0,
                   help="ignore buy/sell actions smaller than this $ amount")
    p.add_argument("--no-sell", action="store_true",
                   help="don't recommend trimming winners; only sell names that fell "
                        "OUT of the top 10, and steer cash into the underweights")
    p.add_argument("--whole-shares", action="store_true",
                   help="express trades in whole share counts (no fractional shares)")
    p.add_argument("--cash-buffer", type=float, default=0.0,
                   help="fraction of the portfolio to keep in cash, e.g. 0.02 = 2%%")
    return p.parse_args()


def live_market_caps(tickers):
    """Best-effort current market cap + price per ticker via yfinance fast_info."""
    import yfinance as yf

    caps, px = {}, {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            mc = getattr(fi, "market_cap", None) or fi.get("market_cap")
            last = getattr(fi, "last_price", None) or fi.get("last_price")
            if mc and last:
                caps[t] = float(mc)
                px[t] = float(last)
        except Exception:  # noqa: BLE001 - skip names we can't price live
            continue
    return caps, px


def universe_filter(universe, ticker):
    meta = constituents.TICKER_META.get(ticker, {})
    if universe == "nasdaq10":
        return meta.get("exchange") == "NASDAQ"
    return True  # us10 / global10: candidate list is already scoped


def target_weights_from_caps(caps, weighting):
    total = sum(caps.values())
    weights = {t: c / total for t, c in caps.items()}
    if weighting == "equal":
        weights = {t: 1.0 / len(caps) for t in caps}
    elif weighting == "capweight_cap20":
        weights = backtest._apply_cap(weights, cap=0.20)
    return weights


def load_holdings(path):
    if not os.path.exists(path):
        return {"cash": 0.0, "positions": {}}
    with open(path) as f:
        data = json.load(f)
    data.setdefault("cash", 0.0)
    data.setdefault("positions", {})
    return data


def notify(title, message):
    """Cross-platform best-effort desktop notification."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                            f'display notification "{message}" with title "{title}"'],
                           check=False)
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False)
        elif sys.platform.startswith("win"):
            ps = (f'powershell -Command "[Windows.UI.Notifications.ToastNotificationManager]'
                  f'; Write-Output \'{title}: {message}\'"')
            subprocess.run(ps, shell=True, check=False)
    except Exception:  # noqa: BLE001
        pass


def main():
    args = parse_args()

    candidates = [t for t in constituents.all_tickers(args.universe)
                  if universe_filter(args.universe, t)]
    print(f"Ranking current top 10 for '{args.universe}' from {len(candidates)} "
          f"candidates (live Yahoo market caps)...\n")
    caps, px = live_market_caps(candidates)
    if not caps:
        print("ERROR: could not fetch live market caps. Are you online / is Yahoo "
              "reachable? (This sandbox blocks Yahoo; run locally.)", file=sys.stderr)
        return 1

    top10 = dict(sorted(caps.items(), key=lambda kv: kv[1], reverse=True)[:10])
    weights = target_weights_from_caps(top10, args.weighting)

    holdings = load_holdings(args.holdings)
    # Total portfolio value = cash + live value of current positions.
    pos = holdings["positions"]
    pos_value = 0.0
    for t, sh in pos.items():
        if t in px:
            pos_value += sh * px[t]
        else:
            # price a held name not in our candidate map
            try:
                import yfinance as yf
                last = yf.Ticker(t).fast_info.get("last_price")
                if last:
                    px[t] = float(last)
                    pos_value += sh * px[t]
            except Exception:  # noqa: BLE001
                pass
    total = holdings["cash"] + pos_value
    investable = total * (1.0 - max(0.0, args.cash_buffer))  # dollars we'll allocate

    print(f"=== Current top 10 ({args.universe}, {args.weighting}) ===")
    for i, (t, w) in enumerate(sorted(weights.items(), key=lambda kv: kv[1], reverse=True), 1):
        print(f"  {i:>2}. {t:<7} {constituents.name_of(t):<28} target {w*100:5.1f}%  "
              f"(${investable * w:,.0f})")

    print(f"\nPortfolio value: ${total:,.2f}  (cash ${holdings['cash']:,.2f} + "
          f"positions ${pos_value:,.2f})")
    if args.cash_buffer > 0:
        print(f"Holding {args.cash_buffer:.0%} (${total - investable:,.0f}) as a cash "
              f"buffer; allocating ${investable:,.0f}.")
    flags = [m for m, on in (("no-sell", args.no_sell),
                             ("whole-shares", args.whole_shares)) if on]
    if flags:
        print(f"Mode: {', '.join(flags)}")

    # Build the action plan.
    print("\n=== Rebalance plan ===")
    actions = []
    held = set(pos)
    target_names = set(weights)

    for t in sorted(target_names | held):
        price_t = px.get(t, 0.0)
        cur_val = pos.get(t, 0) * price_t
        tgt_val = investable * weights.get(t, 0.0)
        delta = tgt_val - cur_val

        dropped_out = t not in target_names and t in held
        new_entrant = t in target_names and t not in held

        # --no-sell: never trim a name that's still in the top 10; only fully
        # sell names that dropped OUT. (Buys still happen, funded by cash + the
        # proceeds of those forced exits.)
        if args.no_sell and delta < 0 and not dropped_out:
            continue
        if dropped_out:
            delta = -cur_val  # sell the whole position

        if abs(delta) < args.min_trade:
            continue

        verb = "BUY " if delta > 0 else "SELL"
        if args.whole_shares and price_t > 0:
            shares = int(abs(delta) // price_t) if delta > 0 else round(abs(delta) / price_t)
            if shares <= 0:
                continue
            qty = f"{shares} sh (~${shares * price_t:,.0f})"
        else:
            qty = f"${abs(delta):,.0f}"
        tag = "  <-- NEW entrant" if new_entrant else \
              ("  <-- DROPPED out of top 10, sell fully" if dropped_out else "")
        actions.append(f"  {verb} {qty} {t} ({constituents.name_of(t)}){tag}")

    if actions:
        print("\n".join(actions))
    else:
        print("  Already within tolerance -- nothing to do. ")

    dropped = held - target_names
    new_in = target_names - held
    headline = f"Rebalance {args.universe}: {len(actions)} trades"
    if dropped:
        headline += f" | OUT: {', '.join(sorted(dropped))}"
    if new_in:
        headline += f" | IN: {', '.join(sorted(new_in))}"
    print(f"\n{headline}")

    if args.notify:
        notify("Portfolio rebalance reminder", headline)

    return 0


if __name__ == "__main__":
    sys.exit(main())
