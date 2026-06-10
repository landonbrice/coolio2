#!/usr/bin/env python3
"""
Backtest the "buy the top 10 biggest companies, rebalance quarterly, reinvest
dividends" strategy across three universes (nasdaq10, us10, global10) and compare
to the S&P 500 total return.

USAGE (on a machine that can reach Yahoo Finance -- NOT this sandbox):

    pip install -r requirements.txt
    python run_backtest.py                       # default: 2006-01-01 -> today
    python run_backtest.py --start 2013-01-01    # the "all-tech-megacap" era
    python run_backtest.py --weighting equal --cost-bps 10

Outputs (written to ./output/):
    * a comparison table printed to the console
    * results_summary.md   : the table + per-universe stats + caveats
    * equity_curves.png     : growth of $1, log scale, all strategies vs S&P 500
    * <universe>_<weighting>_equity.csv : raw equity curves

Reminder: this is a research/curiosity tool, NOT financial advice. Read the
"Caveats" section it prints before you believe any number.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import pandas as pd

from nasdaq_rebalancer import backtest, benchmark, constituents, metrics

OUTPUT_DIR = os.environ.get("REBAL_OUTPUT_DIR", "output")
UNIVERSE_ORDER = ["nasdaq10", "us10", "global10"]


def parse_args():
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default="2006-01-01", help="start date YYYY-MM-DD (default 2006-01-01, ~20y)")
    p.add_argument("--end", default=today, help="end date YYYY-MM-DD (default today)")
    p.add_argument("--weighting", default="capweight",
                   choices=["capweight", "capweight_cap20", "equal"],
                   help="position sizing (default capweight = market-cap weighted)")
    p.add_argument("--cost-bps", type=float, default=5.0,
                   help="per-rebalance transaction cost in basis points of turnover (default 5)")
    p.add_argument("--universes", nargs="+", default=UNIVERSE_ORDER, choices=UNIVERSE_ORDER)
    p.add_argument("--no-cache", action="store_true", help="ignore the on-disk price cache")
    p.add_argument("--no-plot", action="store_true", help="skip PNG generation")
    return p.parse_args()


def fmt_pct(x: float) -> str:
    return f"{x * 100:,.1f}%"


def build_table(rows: list) -> str:
    try:
        from tabulate import tabulate
        return tabulate(rows, headers="keys", tablefmt="github", floatfmt=".2f")
    except Exception:  # noqa: BLE001 - tabulate optional
        df = pd.DataFrame(rows)
        return df.to_string(index=False)


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    use_cache = not args.no_cache

    print(f"Window: {args.start} -> {args.end} | weighting={args.weighting} | "
          f"cost={args.cost_bps}bps | universes={args.universes}\n")

    # 1) Download every ticker we might need, once.
    needed = set()
    for u in args.universes:
        needed.update(constituents.all_tickers(u))
    from nasdaq_rebalancer import prices as price_mod
    panel = price_mod.get_price_panel(sorted(needed), args.start, args.end, use_cache=use_cache)
    print(f"Priced {panel.shape[1]}/{len(needed)} tickers over {panel.shape[0]} trading days.\n")

    # 2) Benchmark: S&P 500 total return.
    sp = benchmark.load_sp500(args.start, args.end, use_cache=use_cache)

    # 3) Run each universe.
    curves = {}
    results = {}
    for u in args.universes:
        res = backtest.run_backtest(u, panel, args.start, args.end,
                                    weighting=args.weighting, cost_bps=args.cost_bps)
        results[u] = res
        curves[constituents.UNIVERSE_LABELS[u]] = res.equity
        if res.dropped:
            drops = ", ".join(f"{t}x{n}" for t, n in sorted(res.dropped.items()))
            print(f"  note [{u}]: dropped un-priceable names at some rebalances: {drops}")
    curves["S&P 500 (Total Return)"] = sp

    # 4) Align all curves to a common window and compute stats.
    labels = list(curves.keys())
    aligned = metrics.align(*[curves[l] for l in labels])
    aligned = dict(zip(labels, aligned))

    sp_label = "S&P 500 (Total Return)"
    sp_stats = metrics.compute(aligned[sp_label])

    rows = []
    for label in labels:
        st = metrics.compute(aligned[label])
        rows.append({
            "Strategy": label,
            "Final $1 ->": f"${st.multiple:,.2f}",
            "Total Return": fmt_pct(st.total_return),
            "CAGR": fmt_pct(st.cagr),
            "Vol": fmt_pct(st.vol),
            "Sharpe": round(st.sharpe, 2),
            "Max DD": fmt_pct(st.max_drawdown),
            "x vs S&P": f"{st.multiple / sp_stats.multiple:,.2f}x",
        })
    table = build_table(rows)
    span = f"{aligned[sp_label].index[0].date()} -> {aligned[sp_label].index[-1].date()}"
    print(f"\n=== Results ({span}, ~{sp_stats.years:.1f}y, dividends reinvested) ===\n")
    print(table)

    # 5) Write summary markdown.
    summary = _summary_markdown(args, span, sp_stats, table, results)
    summary_path = os.path.join(OUTPUT_DIR, "results_summary.md")
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"\nWrote {summary_path}")

    # 6) Save raw equity CSVs.
    for label, curve in aligned.items():
        safe = label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("&", "and")
        curve.to_csv(os.path.join(OUTPUT_DIR, f"equity_{safe}.csv"))

    # 7) Plot.
    if not args.no_plot:
        _plot(aligned, args, span)


def _summary_markdown(args, span, sp_stats, table, results) -> str:
    lines = [
        "# Top-10 rebalancing backtest -- results",
        "",
        f"- **Window:** {span} (~{sp_stats.years:.1f} years)",
        f"- **Weighting:** {args.weighting}",
        f"- **Rebalance:** quarterly (first trading day of Jan/Apr/Jul/Oct)",
        f"- **Transaction cost:** {args.cost_bps} bps of turnover per rebalance",
        f"- **Dividends:** reinvested (prices are split & dividend adjusted)",
        "",
        "## Headline comparison",
        "",
        table,
        "",
        "## How to read this",
        "",
        "- **x vs S&P** is the headline number from the podcast thesis: how many",
        "  times more (or less) ending wealth than the S&P 500 total return.",
        "- A point-in-time roster is used: at each rebalance you hold whoever was",
        "  *actually* top-10 then, and you sell names that dropped out. No look-ahead.",
        "",
        "## Caveats (read before believing any number)",
        "",
        "1. **Curated membership.** The historical top-10 lists are a good-faith",
        "   reconstruction from public year-end rankings, not an audited dataset.",
        "2. **global10 is lowest-confidence**: several past leaders (PetroChina,",
        "   China Mobile, Gazprom) are delisted ADRs Yahoo can't price, so they get",
        "   dropped and weights renormalize -- the pre-2015 global result is an",
        "   approximation of the available subset.",
        "3. **No taxes.** Quarterly rebalancing in a taxable account triggers",
        "   short/long-term capital gains that this backtest ignores. In a taxable",
        "   account the real after-tax return is meaningfully lower.",
        "4. **Costs are simplified** (flat bps on turnover; no bid/ask, no slippage).",
        "5. **Past performance != future results.** This is a curiosity/research",
        "   tool, not financial advice.",
        "",
    ]
    for u, res in results.items():
        if res.dropped:
            drops = ", ".join(f"{t} (x{n})" for t, n in sorted(res.dropped.items()))
            lines.append(f"- _Dropped in {u}:_ {drops}")
    return "\n".join(lines)


def _plot(aligned: dict, args, span):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        print(f"(skipping plot: matplotlib unavailable: {exc})")
        return

    fig, ax = plt.subplots(figsize=(12, 7))
    for label, curve in aligned.items():
        style = dict(lw=2.5, color="black", ls="--") if label.startswith("S&P") else dict(lw=2)
        ax.plot(curve.index, curve.values, label=label, **style)
    ax.set_yscale("log")
    ax.set_title(f"Growth of $1 -- top-10 quarterly rebalance vs S&P 500\n"
                 f"{span}, {args.weighting}, dividends reinvested", fontsize=12)
    ax.set_ylabel("Value of $1 (log scale)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, "equity_curves.png")
    fig.savefig(out, dpi=130)
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
