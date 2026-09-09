#!/usr/bin/env python3
"""
Extra analyses for the IC report, consuming the cached panel (instant):

  #2  Satellite blend: 70% S&P 500 TR / 30% nasdaq10 strategy, rebalanced
      annually, vs 100% S&P and 100% strategy. Question: how much of the
      concentration edge survives at a fraction of the single-factor risk?

  #3  Rebalancing value: "buy the 2013 top-10 and never rebalance" vs the
      quarterly-rebalanced top-10, both cap-weighted, 2013 -> today. The gap
      is the alpha attributable to the *rebalancing rule itself* (not just
      owning big-caps).

Also rolls up the sweep matrix by universe and recomputes the tax short-list,
so the whole report is driven by one JSON.

Outputs: output/analysis_data.json, output/satellite_curve.png
"""
from __future__ import annotations

import datetime as dt
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nasdaq_rebalancer import backtest, benchmark, constituents, metrics
from nasdaq_rebalancer import prices as price_mod

OUT = os.environ.get("REBAL_OUTPUT_DIR", "output")
COST_BPS = 5.0
TAX_LONG, TAX_SHORT = 0.20, 0.37
START = "2006-01-01"
S2013 = "2013-01-01"

# Tax short-list (mirrors tax_rerun.py) — (label, top_n, weighting, mode, interval)
SHORTLIST = [
    ("cap-weight top10 (baseline)", 10, "capweight",  "full",       "Q"),
    ("equal full (pre-tax winner)", 10, "equal",      "full",       "Q"),
    ("equal drift_band",            10, "equal",      "drift_band", "Q"),
    ("equal no_sell",               10, "equal",      "no_sell",    "Q"),
    ("equal full, annual",          10, "equal",      "full",       "A"),
    ("top5 equal full (max CAGR)",   5, "equal",      "full",       "SA"),
    ("top3 equal full",              3, "equal",      "full",       "Q"),
]


def stat_dict(s, x=None):
    d = {"cagr": s.cagr, "vol": s.vol, "sharpe": s.sharpe,
         "maxdd": s.max_drawdown, "multiple": s.multiple}
    if x is not None:
        d["xsp"] = x
    return d


def xsp(eq, sp, start, end):
    a, b = metrics.align(eq, sp.loc[start:end])
    return float(a.iloc[-1] / b.iloc[-1])


def strat_curve(panel, start, end, weighting="capweight", mode="full",
                interval="Q", top_n=10, tax=False):
    return backtest.run_backtest(
        "nasdaq10", panel, start, end, weighting=weighting, cost_bps=COST_BPS,
        mode=mode, drift_band=0.05, top_n=top_n, interval=interval,
        tax_long=(TAX_LONG if tax else 0.0),
        tax_short=(TAX_SHORT if tax else 0.0),
    ).equity


def blend_annual(spy_ret, strat_ret, w_spy=0.70):
    """70/30 portfolio, rebalanced to target at the first trading day of each year."""
    df = pd.DataFrame({"spy": spy_ret, "strat": strat_ret}).dropna()
    w_strat = 1.0 - w_spy
    a, b = w_spy, w_strat            # sleeve values, total starts at 1.0
    out, prev_year = [], df.index[0].year
    for date, row in df.iterrows():
        if date.year != prev_year:   # rebalance at year boundary
            tot = a + b
            a, b = w_spy * tot, w_strat * tot
            prev_year = date.year
        a *= (1.0 + row["spy"])
        b *= (1.0 + row["strat"])
        out.append(a + b)
    return pd.Series(out, index=df.index)


def buy_and_hold(panel, t0, weighting="capweight", top_n=10):
    """Buy the top_n roster as-of t0 at target weights, hold fixed shares forever."""
    w = backtest._target_weights("nasdaq10", t0, panel, weighting, {}, top_n=top_n)
    cols = list(w)
    sub = panel[cols].loc[t0:].ffill()
    shares = pd.Series(w) / sub.iloc[0]
    eq = (sub * shares).sum(axis=1)
    return (eq / eq.iloc[0]).dropna(), w


def main():
    os.makedirs(OUT, exist_ok=True)
    end = dt.date.today().isoformat()

    needed = set()
    for u in ("nasdaq10", "us10", "global10"):
        needed.update(constituents.all_tickers(u))
    panel = price_mod.get_price_panel(sorted(needed), START, end, use_cache=True)
    sp = benchmark.load_sp500(START, end, use_cache=True)

    data = {"meta": {"start": START, "end": end, "cost_bps": COST_BPS,
                     "tax_long": TAX_LONG, "tax_short": TAX_SHORT},
            "benchmark": {}}

    # ---- benchmark (full + 2013) ----
    data["benchmark"]["full"] = stat_dict(metrics.compute(sp.loc[START:end]))
    data["benchmark"]["since2013"] = stat_dict(metrics.compute(sp.loc[S2013:end]))

    # ================= #2 Satellite (full window) =================
    print("Satellite blend (70/30)...")
    strat = strat_curve(panel, START, end)              # cap-weight top10 full Q
    a, b = metrics.align(strat, sp.loc[START:end])
    strat, spy = a, b
    blend = blend_annual(spy.pct_change(), strat.pct_change(), w_spy=0.70)
    sat = {
        "spy":    stat_dict(metrics.compute(spy),   xsp(spy,   sp, START, end)),
        "strat":  stat_dict(metrics.compute(strat), xsp(strat, sp, START, end)),
        "blend":  stat_dict(metrics.compute(blend), xsp(blend, sp, START, end)),
    }
    # share of strategy's *excess* CAGR captured by the 30% sleeve
    edge = sat["strat"]["cagr"] - sat["spy"]["cagr"]
    sat["edge_capture"] = (sat["blend"]["cagr"] - sat["spy"]["cagr"]) / edge if edge else float("nan")
    data["satellite"] = sat
    _plot_satellite(spy, strat, blend, end)

    # ================= #3 Rebalancing value (2013 -> today) =================
    print("Rebalancing value (buy-2013-hold vs rebalanced)...")
    t0 = panel.loc[S2013:].index[0]
    reb = strat_curve(panel, S2013, end)                # rebalanced, cap-weight top10
    bh, roster = buy_and_hold(panel, t0, "capweight", 10)
    reb_a, bh_a = metrics.align(reb, bh)                # common dates
    rebval = {
        "window": {"start": S2013, "end": end},
        "roster_2013": list(roster.keys()),
        "rebalanced":  stat_dict(metrics.compute(reb_a), xsp(reb_a, sp, S2013, end)),
        "buy_and_hold": stat_dict(metrics.compute(bh_a), xsp(bh_a, sp, S2013, end)),
    }
    rebval["rebalancing_alpha_pts"] = (rebval["rebalanced"]["cagr"]
                                       - rebval["buy_and_hold"]["cagr"]) * 100
    data["rebalancing_value"] = rebval

    # ================= sweep rollup by universe =================
    print("Universe rollup from sweep_results.csv...")
    df = pd.read_csv(os.path.join(OUT, "sweep_results.csv"))
    uni = {}
    for u, g in df.groupby("universe"):
        best = g.loc[g["full_cagr"].idxmax()]
        bestsh = g.loc[g["full_sharpe"].idxmax()]
        uni[u] = {
            "n_configs": int(len(g)),
            "cagr_best": float(g["full_cagr"].max()),
            "cagr_median": float(g["full_cagr"].median()),
            "xsp_best": float(g["full_xsp"].max()),
            "xsp_median": float(g["full_xsp"].median()),
            "sharpe_best": float(g["full_sharpe"].max()),
            "maxdd_best_cagr": float(best["full_maxdd"]),
            "best_config": str(best["config"]),
            "best_sharpe_config": str(bestsh["config"]),
        }
    data["universe"] = uni

    # top leaderboards (full period) for the report
    def lead(sortcol, n=10):
        d = df.sort_values(sortcol, ascending=False).head(n)
        return [{"config": r["config"], "cagr": float(r["full_cagr"]),
                 "vol": float(r["full_vol"]), "sharpe": float(r["full_sharpe"]),
                 "maxdd": float(r["full_maxdd"]), "xsp": float(r["full_xsp"])}
                for _, r in d.iterrows()]
    data["leaderboard_cagr"] = lead("full_cagr")
    data["leaderboard_sharpe"] = lead("full_sharpe")

    # rebalancing cadence & mode effect (nasdaq10, equal, top10) — isolates cadence
    sub = df[(df.universe == "nasdaq10") & (df.weighting == "equal") & (df.top_n == 10)]
    data["cadence_effect"] = [
        {"mode": r["mode"], "interval": r["interval"], "cagr": float(r["full_cagr"]),
         "sharpe": float(r["full_sharpe"]), "maxdd": float(r["full_maxdd"])}
        for _, r in sub.sort_values(["mode", "interval"]).iterrows()
    ]

    # overfit diagnostics (recompute from csv)
    bt = df.loc[df["train_cagr"].idxmax()]
    bts = df.loc[df["train_sharpe"].idxmax()]
    data["overfit"] = {
        "best_train_cagr_config": str(bt["config"]),
        "best_train_cagr_test_rank": int((df["test_cagr"] > bt["test_cagr"]).sum() + 1),
        "best_train_sharpe_config": str(bts["config"]),
        "best_train_sharpe_test_rank": int((df["test_sharpe"] > bts["test_sharpe"]).sum() + 1),
        "n": int(len(df)),
        "corr_cagr_spearman": float(df[["train_cagr", "test_cagr"]].corr(method="spearman").iloc[0, 1]),
        "corr_sharpe_pearson": float(df[["train_sharpe", "test_sharpe"]].corr().iloc[0, 1]),
    }

    # ================= tax short-list =================
    print("Tax short-list...")
    tax_rows = []
    for label, n, w, mode, iv in SHORTLIST:
        e0 = strat_curve(panel, START, end, w, mode, iv, n, tax=False)
        e1 = strat_curve(panel, START, end, w, mode, iv, n, tax=True)
        s0, s1 = metrics.compute(e0), metrics.compute(e1)
        years = (e0.index[-1] - e0.index[0]).days / 365.25
        # turnover via a fresh run (no tax) to read .turnover
        res = backtest.run_backtest("nasdaq10", panel, START, end, weighting=w,
                                    cost_bps=COST_BPS, mode=mode, drift_band=0.05,
                                    top_n=n, interval=iv)
        turn = (sum(res.turnover) / years) if res.turnover else 0.0
        tax_rows.append({
            "config": label, "cagr_notax": s0.cagr, "cagr_tax": s1.cagr,
            "drag_pts": (s0.cagr - s1.cagr) * 100,
            "xsp_notax": xsp(e0, sp, START, end), "xsp_tax": xsp(e1, sp, START, end),
            "vol": s0.vol, "maxdd": s0.max_drawdown, "turnover": turn,
        })
    data["tax"] = tax_rows

    with open(os.path.join(OUT, "analysis_data.json"), "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nWrote {OUT}/analysis_data.json and satellite_curve.png")

    # console digest
    print(f"\n  Satellite: SPY {sat['spy']['cagr']*100:.1f}% | "
          f"blend70/30 {sat['blend']['cagr']*100:.1f}% | strat {sat['strat']['cagr']*100:.1f}%  "
          f"(edge captured {sat['edge_capture']*100:.0f}%, blend maxDD {sat['blend']['maxdd']*100:.0f}%)")
    print(f"  Rebalancing alpha (2013->): rebalanced {rebval['rebalanced']['cagr']*100:.1f}% "
          f"vs buy&hold {rebval['buy_and_hold']['cagr']*100:.1f}%  "
          f"= +{rebval['rebalancing_alpha_pts']:.1f} pt/yr")
    return 0


def _plot_satellite(spy, strat, blend, end):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(strat.index, strat.values, color="#1f77b4", lw=1.6, label="100% nasdaq10 strategy")
    ax.plot(blend.index, blend.values, color="#2ca02c", lw=1.8, label="70% S&P / 30% strategy")
    ax.plot(spy.index, spy.values, color="#888888", lw=1.4, label="100% S&P 500 TR")
    ax.set_yscale("log")
    ax.set_ylabel("Growth of $1 (log)")
    ax.set_title(f"Satellite blend: most of the edge, less of the risk (2006 -> {end})")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "satellite_curve.png"), dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
