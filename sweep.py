#!/usr/bin/env python3
"""
Strategy sweep & (honest) optimization.

Treats the strategy as a function of THREE structural inputs the user asked about
plus universe size, and measures TWO outputs (return and risk):

    INPUTS (vectors):
      universe   in {nasdaq10, us10, global10}
      top_n      in {1, 3, 5, 10}          # hold only the biggest N companies
      weighting  in {capweight, capweight_cap20*, equal}   # *only meaningful at n=10
      mode       in {full, drift_band, no_sell}            # the "balancing logic"
      interval   in {M, Q, SA, A}          # monthly / quarterly / semiannual / annual

    OUTPUTS:
      return -> CAGR
      risk   -> annualized vol, max drawdown
      and the two combined -> Sharpe (CAGR / vol, rf=0)

We report all three lenses the user asked for: the Pareto frontier (return vs
risk), the max-Sharpe config, and the max-CAGR config.

HONESTY: a single grid search over all ~20 years just finds whatever fit the
past best -- that's overfitting. So every config is run on a TRAIN window
(2006-2017) and a held-out TEST window (2018-2026), and we report how the
train-winners actually did out-of-sample, plus the train->test rank correlation.
Tax is OFF and cost is a flat 5bps here so the sweep isolates *structure*; layer
taxes back on (run_backtest --tax-*) before trusting any single config for a
taxable account.

Run (locally, with Yahoo reachable; the panel cache makes re-runs instant):
    python sweep.py
Outputs land in ./output/: sweep_results.csv, sweep_summary.md, sweep_pareto.png,
sweep_train_test.png
"""

from __future__ import annotations

import datetime as dt
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

UNIVERSES = ["nasdaq10", "us10", "global10"]
TOP_NS = [1, 3, 5, 10]
INTERVALS = ["M", "Q", "SA", "A"]
INTERVAL_LABEL = {"M": "monthly", "Q": "quarterly", "SA": "semiannual", "A": "annual"}
MODES = ["full", "drift_band", "no_sell"]


def weightings_for(n: int):
    if n == 1:
        return ["capweight"]                              # single name -> weighting moot
    if n == 10:
        return ["capweight", "capweight_cap20", "equal"]  # cap20 only bites at n=10
    return ["capweight", "equal"]                         # cap20 == equal for n<=5


def modes_for(n: int):
    return ["full"] if n == 1 else MODES                  # modes coincide for a single name


def combos():
    for u in UNIVERSES:
        for n in TOP_NS:
            for w in weightings_for(n):
                for m in modes_for(n):
                    for iv in INTERVALS:
                        yield {"universe": u, "top_n": n, "weighting": w,
                               "mode": m, "interval": iv}


def run_one(c, panel, sp, start, end):
    """Run one config over one window; return (stats, x_vs_sp) or None on failure."""
    res = backtest.run_backtest(
        c["universe"], panel, start, end,
        weighting=c["weighting"], cost_bps=COST_BPS,
        mode=c["mode"], drift_band=0.05,
        top_n=c["top_n"], interval=c["interval"],
    )
    eq = res.equity
    if eq is None or len(eq) < 50:
        return None
    s = metrics.compute(eq)
    a, b = metrics.align(eq, sp.loc[start:end])
    x = float(a.iloc[-1] / b.iloc[-1]) if len(a) else float("nan")
    return s, x


def pareto_front(df, xcol, ycol):
    """Indices on the upper-left frontier: maximize ycol (return), minimize xcol (risk)."""
    pts = df.sort_values([xcol, ycol], ascending=[True, False])
    front, best_y = [], -np.inf
    for idx, row in pts.iterrows():
        if row[ycol] > best_y + 1e-12:
            front.append(idx)
            best_y = row[ycol]
    return front


def label(c):
    return (f"{c['universe']}/top{c['top_n']}/{c['weighting'].replace('capweight','cap')}"
            f"/{c['mode']}/{c['interval']}")


def main():
    os.makedirs(OUT, exist_ok=True)
    today = dt.date.today().isoformat()
    windows = {
        "train": ("2006-01-01", "2017-12-31"),
        "test": ("2018-01-01", today),
        "full": ("2006-01-01", today),
    }

    needed = set()
    for u in UNIVERSES:
        needed.update(constituents.all_tickers(u))
    print(f"Loading price panel ({len(needed)} tickers)...")
    panel = price_mod.get_price_panel(sorted(needed), "2006-01-01", today, use_cache=True)
    sp = benchmark.load_sp500("2006-01-01", today, use_cache=True)
    print(f"Panel: {panel.shape[1]} priced tickers x {panel.shape[0]} days.")

    # Benchmark stats per window, for context.
    sp_stats = {}
    for w, (s0, e0) in windows.items():
        st = metrics.compute(sp.loc[s0:e0])
        sp_stats[w] = st
        print(f"  S&P {w}: CAGR {st.cagr*100:.1f}%  vol {st.vol*100:.1f}%  "
              f"Sharpe {st.sharpe:.2f}  maxDD {st.max_drawdown*100:.1f}%")

    all_combos = list(combos())
    print(f"\nSweeping {len(all_combos)} configs x {len(windows)} windows "
          f"= {len(all_combos)*len(windows)} backtests...\n")

    records = []
    for i, c in enumerate(all_combos, 1):
        row = dict(c)
        ok = True
        for w, (s0, e0) in windows.items():
            r = run_one(c, panel, sp, s0, e0)
            if r is None:
                ok = False
                break
            s, x = r
            row[f"{w}_cagr"] = s.cagr
            row[f"{w}_vol"] = s.vol
            row[f"{w}_sharpe"] = s.sharpe
            row[f"{w}_maxdd"] = s.max_drawdown
            row[f"{w}_mult"] = s.multiple
            row[f"{w}_xsp"] = x
        if ok:
            records.append(row)
        if i % 40 == 0:
            print(f"  ...{i}/{len(all_combos)}")

    df = pd.DataFrame(records)
    df["config"] = df.apply(lambda r: label(r), axis=1)
    df.to_csv(os.path.join(OUT, "sweep_results.csv"), index=False)
    print(f"\nWrote {OUT}/sweep_results.csv ({len(df)} configs)")

    # ---- Rankings (full period) ----
    by_cagr = df.sort_values("full_cagr", ascending=False)
    by_sharpe = df.sort_values("full_sharpe", ascending=False)
    front_idx = pareto_front(df, "full_vol", "full_cagr")
    front = df.loc[front_idx].sort_values("full_vol")

    # ---- Overfitting diagnostics (train -> test) ----
    best_train_cagr = df.loc[df["train_cagr"].idxmax()]
    best_train_sharpe = df.loc[df["train_sharpe"].idxmax()]
    # rank of the train-winner on the test set
    test_cagr_rank = (df["test_cagr"] > best_train_cagr["test_cagr"]).sum() + 1
    test_sharpe_rank = (df["test_sharpe"] > best_train_sharpe["test_sharpe"]).sum() + 1
    corr_cagr = df[["train_cagr", "test_cagr"]].corr().iloc[0, 1]
    corr_sharpe = df[["train_sharpe", "test_sharpe"]].corr().iloc[0, 1]
    rank_corr_cagr = df[["train_cagr", "test_cagr"]].corr(method="spearman").iloc[0, 1]

    # ---- Plots ----
    _plot_pareto(df, front, today)
    _plot_train_test(df, today)

    # ---- Markdown summary ----
    _write_summary(df, by_cagr, by_sharpe, front, sp_stats,
                   best_train_cagr, best_train_sharpe,
                   test_cagr_rank, test_sharpe_rank,
                   corr_cagr, corr_sharpe, rank_corr_cagr, today)
    print(f"Wrote {OUT}/sweep_summary.md, sweep_pareto.png, sweep_train_test.png")
    return 0


def _cols(df, window):
    return df[[f"{window}_cagr", f"{window}_vol", f"{window}_sharpe",
               f"{window}_maxdd", f"{window}_xsp"]]


def _top_table(df, sortcol, window, n=12):
    d = df.sort_values(sortcol, ascending=False).head(n)
    out = pd.DataFrame({
        "config": d["config"],
        "CAGR%": (d[f"{window}_cagr"] * 100).round(1),
        "vol%": (d[f"{window}_vol"] * 100).round(1),
        "Sharpe": d[f"{window}_sharpe"].round(2),
        "maxDD%": (d[f"{window}_maxdd"] * 100).round(1),
        "x_S&P": d[f"{window}_xsp"].round(2),
    })
    return out


def _md(df):
    try:
        return df.to_markdown(index=False)
    except Exception:  # noqa: BLE001
        return "```\n" + df.to_string(index=False) + "\n```"


def _plot_pareto(df, front, today):
    fig, ax = plt.subplots(figsize=(11, 7))
    cmap = {1: "#d62728", 3: "#ff7f0e", 5: "#2ca02c", 10: "#1f77b4"}
    for n in TOP_NS:
        d = df[df["top_n"] == n]
        ax.scatter(d["full_vol"] * 100, d["full_cagr"] * 100, s=28, alpha=0.55,
                   color=cmap[n], label=f"top {n}")
    f = front.sort_values("full_vol")
    ax.plot(f["full_vol"] * 100, f["full_cagr"] * 100, "k--", lw=1.4, alpha=0.8,
            label="Pareto frontier")
    for _, r in f.iterrows():
        ax.annotate(r["config"], (r["full_vol"] * 100, r["full_cagr"] * 100),
                    fontsize=6.5, xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Annualized volatility (%)  -- risk")
    ax.set_ylabel("CAGR (%)  -- return")
    ax.set_title(f"Return vs risk across all configs (full period 2006 -> {today}, "
                 f"5bps cost, no tax)\nColor = universe size; dashed = efficient frontier")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sweep_pareto.png"), dpi=130)
    plt.close(fig)


def _plot_train_test(df, today):
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    sc = ax.scatter(df["train_cagr"] * 100, df["test_cagr"] * 100,
                    c=df["top_n"], cmap="viridis", s=30, alpha=0.7)
    lo = min(df["train_cagr"].min(), df["test_cagr"].min()) * 100 - 2
    hi = max(df["train_cagr"].max(), df["test_cagr"].max()) * 100 + 2
    ax.plot([lo, hi], [lo, hi], "k--", lw=1, alpha=0.6, label="train = test")
    bt = df.loc[df["train_cagr"].idxmax()]
    ax.scatter([bt["train_cagr"] * 100], [bt["test_cagr"] * 100], s=160,
               facecolors="none", edgecolors="red", linewidths=2,
               label="best on train")
    ax.set_xlabel("Train CAGR % (2006-2017)")
    ax.set_ylabel("Test CAGR % (2018-2026, out-of-sample)")
    ax.set_title("Does in-sample skill survive out-of-sample?\n"
                 "Points far below the dashed line = overfit")
    fig.colorbar(sc, label="top_n")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "sweep_train_test.png"), dpi=130)
    plt.close(fig)


def _write_summary(df, by_cagr, by_sharpe, front, sp_stats,
                   best_train_cagr, best_train_sharpe,
                   test_cagr_rank, test_sharpe_rank,
                   corr_cagr, corr_sharpe, rank_corr_cagr, today):
    L = []
    L.append("# Strategy sweep & optimization\n")
    L.append(f"Full period **2006-01-01 -> {today}**, 5 bps cost, **no tax**, "
             f"dividends reinvested. {len(df)} structural configs.\n")
    L.append("Inputs swept: `universe x top_n x weighting x mode x interval`. "
             "Outputs: CAGR (return), vol & maxDD (risk), Sharpe (combined).\n")

    sp = sp_stats["full"]
    L.append(f"**Benchmark (S&P 500 TR, full):** CAGR {sp.cagr*100:.1f}%, "
             f"vol {sp.vol*100:.1f}%, Sharpe {sp.sharpe:.2f}, "
             f"maxDD {sp.max_drawdown*100:.1f}%.\n")

    L.append("\n## A. Highest return (max CAGR, full period)\n")
    L.append(_md(_top_table(df, "full_cagr", "full")))
    L.append("\n## B. Highest risk-adjusted return (max Sharpe, full period)\n")
    L.append(_md(_top_table(df, "full_sharpe", "full")))
    L.append("\n## C. Pareto frontier (efficient return-vs-risk trade-offs)\n")
    L.append("Each config below is non-dominated: nothing in the sweep has both "
             "higher CAGR and lower vol. Pick by risk appetite.\n")
    fr = pd.DataFrame({
        "config": front["config"],
        "CAGR%": (front["full_cagr"] * 100).round(1),
        "vol%": (front["full_vol"] * 100).round(1),
        "Sharpe": front["full_sharpe"].round(2),
        "maxDD%": (front["full_maxdd"] * 100).round(1),
        "x_S&P": front["full_xsp"].round(2),
    })
    L.append(_md(fr))

    L.append("\n## D. Overfitting check (train 2006-2017 -> test 2018-2026)\n")
    L.append(f"- **Best config on TRAIN by CAGR:** `{best_train_cagr['config']}` "
             f"(train {best_train_cagr['train_cagr']*100:.1f}%). Out-of-sample it did "
             f"**{best_train_cagr['test_cagr']*100:.1f}%** on TEST, ranking "
             f"**#{int(test_cagr_rank)} of {len(df)}** there.")
    L.append(f"- **Best config on TRAIN by Sharpe:** `{best_train_sharpe['config']}` "
             f"(train Sharpe {best_train_sharpe['train_sharpe']:.2f}). Out-of-sample "
             f"Sharpe **{best_train_sharpe['test_sharpe']:.2f}**, ranking "
             f"**#{int(test_sharpe_rank)} of {len(df)}** on TEST.")
    L.append(f"- **Train->test correlation across all configs:** CAGR Pearson "
             f"{corr_cagr:.2f}, Spearman {rank_corr_cagr:.2f}; Sharpe Pearson "
             f"{corr_sharpe:.2f}.")
    L.append("- Read: a high correlation means the ranking is stable (structure, "
             "not luck); a low/negative one means the 'winner' is curve-fit and "
             "should not be trusted forward.\n")

    L.append("\n## How to read / caveats\n")
    L.append("- **In-sample optima overfit.** The section-A/B 'winners' are the best "
             "fit to one 20-year path, not a promise. Section D is the reality check.\n")
    L.append("- **No tax here.** More-frequent intervals (monthly) and full-mode "
             "trimming look better pre-tax than they would after capital-gains tax. "
             "Re-run the short list with `--tax-long/--tax-short` before committing.\n")
    L.append("- **Concentration cuts both ways.** top_1/top_3 can post the highest "
             "CAGR and the worst drawdowns; that's why risk is reported alongside.\n")
    L.append("- Membership is curated annual snapshots (see docs/VISION.md); "
             "global10 pre-2015 is the priceable subset only.\n")
    L.append(f"\nArtifacts: `output/sweep_results.csv` (full matrix), "
             f"`sweep_pareto.png`, `sweep_train_test.png`.\n")

    with open(os.path.join(OUT, "sweep_summary.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
