#!/usr/bin/env python3
"""
Tax re-run of the sweep short-list.

The sweep (sweep.py) is deliberately PRE-TAX so it isolates structure. Its own
caveat: equal-weight `full` trimming and frequent intervals look better pre-tax
than they would after capital-gains tax. This script stress-tests exactly that
by running a curated short-list of the sweep's winners BOTH no-tax and with tax
(20% long / 37% short, matching docs/RESULTS.md), over the full window, on the
cached panel (instant). It isolates one tax-relevant axis at a time:

    weighting   : cap vs equal      (top10/full/Q)        -- turnover driver #1
    mode        : full/drift/no_sell(top10/equal/Q)        -- turnover driver #2
    cadence     : Q vs A            (top10/equal/full)     -- turnover driver #3
    concentration: top10/5/3        (equal/full)           -- risk + turnover

Output: console table + output/tax_rerun.md.
"""
from __future__ import annotations

import datetime as dt
import os

from nasdaq_rebalancer import backtest, benchmark, constituents, metrics
from nasdaq_rebalancer import prices as price_mod

OUT = os.environ.get("REBAL_OUTPUT_DIR", "output")
COST_BPS = 5.0
TAX_LONG, TAX_SHORT = 0.20, 0.37
START = "2006-01-01"

# (label, universe, top_n, weighting, mode, interval)
SHORTLIST = [
    ("cap baseline (low turnover)", "nasdaq10", 10, "capweight",      "full",       "Q"),
    ("equal full  (pre-tax winner)", "nasdaq10", 10, "equal",         "full",       "Q"),
    ("equal drift_band",            "nasdaq10", 10, "equal",          "drift_band", "Q"),
    ("equal no_sell",               "nasdaq10", 10, "equal",          "no_sell",    "Q"),
    ("equal full, ANNUAL",          "nasdaq10", 10, "equal",          "full",       "A"),
    ("top5  equal full (max CAGR)", "nasdaq10",  5, "equal",          "full",       "SA"),
    ("top3  equal full",            "nasdaq10",  3, "equal",          "full",       "Q"),
]


def run(cfg, panel, sp, end, taxed: bool):
    _, uni, n, w, mode, iv = cfg
    res = backtest.run_backtest(
        uni, panel, START, end,
        weighting=w, cost_bps=COST_BPS, mode=mode, drift_band=0.05,
        top_n=n, interval=iv,
        tax_long=(TAX_LONG if taxed else 0.0),
        tax_short=(TAX_SHORT if taxed else 0.0),
    )
    s = metrics.compute(res.equity)
    a, b = metrics.align(res.equity, sp.loc[START:end])
    x = float(a.iloc[-1] / b.iloc[-1])
    years = (res.equity.index[-1] - res.equity.index[0]).days / 365.25
    ann_turnover = (sum(res.turnover) / years) if res.turnover else 0.0
    return s, x, ann_turnover


def main():
    os.makedirs(OUT, exist_ok=True)
    end = dt.date.today().isoformat()

    # Match sweep.py's ticker set exactly so we hit the existing 53-ticker cache
    # (instant). run_backtest just selects the nasdaq10 columns it needs.
    needed = set()
    for u in ("nasdaq10", "us10", "global10"):
        needed.update(constituents.all_tickers(u))
    panel = price_mod.get_price_panel(sorted(needed), START, end, use_cache=True)
    sp = benchmark.load_sp500(START, end, use_cache=True)
    sp_stats = metrics.compute(sp.loc[START:end])

    rows = []
    for cfg in SHORTLIST:
        label = cfg[0]
        s0, x0, turn = run(cfg, panel, sp, end, taxed=False)
        s1, x1, _ = run(cfg, panel, sp, end, taxed=True)
        rows.append({
            "config": label,
            "CAGR_notax": s0.cagr, "CAGR_tax": s1.cagr,
            "drag_pts": (s0.cagr - s1.cagr) * 100,
            "xsp_notax": x0, "xsp_tax": x1,
            "vol": s0.vol, "maxDD": s0.max_drawdown, "sharpe": s0.sharpe,
            "ann_turn": turn,
        })
        print(f"  {label:32s} notax {s0.cagr*100:5.1f}%  tax {s1.cagr*100:5.1f}%  "
              f"drag {(s0.cagr-s1.cagr)*100:4.1f}pt  turn/yr {turn*100:4.0f}%")

    # ---- markdown ----
    L = [f"# Tax re-run of sweep short-list\n",
         f"Full window **{START} -> {end}**, nasdaq10, 5 bps cost, dividends "
         f"reinvested. Tax = **{TAX_LONG:.0%} long / {TAX_SHORT:.0%} short** on "
         f"realized gains at each rebalance.\n",
         f"S&P 500 TR over the window: CAGR {sp_stats.cagr*100:.1f}%, "
         f"vol {sp_stats.vol*100:.1f}%, maxDD {sp_stats.max_drawdown*100:.1f}%.\n",
         "| config | CAGR no-tax | CAGR taxed | tax drag (pt/yr) | x S&P no-tax | "
         "x S&P taxed | vol% | maxDD% | turnover/yr |",
         "|:--|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for r in rows:
        L.append(f"| {r['config']} | {r['CAGR_notax']*100:.1f}% | "
                 f"{r['CAGR_tax']*100:.1f}% | {r['drag_pts']:.1f} | "
                 f"{r['xsp_notax']:.2f}x | {r['xsp_tax']:.2f}x | "
                 f"{r['vol']*100:.1f} | {r['maxDD']*100:.1f} | "
                 f"{r['ann_turn']*100:.0f}% |")
    L.append("\n**Read:** tax drag scales with turnover. Equal-weight `full` "
             "trims every winner each period (high turnover -> biggest drag); "
             "cap-weight, drift_band, no_sell, and annual cadence all cut "
             "turnover and therefore tax. Compare CAGR-taxed (not no-tax) when "
             "choosing a config for a taxable account; in a tax-advantaged "
             "account the no-tax column applies.\n")
    with open(os.path.join(OUT, "tax_rerun.md"), "w") as f:
        f.write("\n".join(L))
    print(f"\nWrote {OUT}/tax_rerun.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
