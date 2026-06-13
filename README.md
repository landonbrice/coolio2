# Top-10 Rebalancer — backtest + reminder bot

Inspired by Philippe Laffont (Coatue)'s "liquidity / durability of cash flows"
argument: own the biggest companies, rebalance into the new leaders each quarter,
reinvest dividends, and you'd have outpaced the S&P 500 over the last ~decade.

This repo does two things:

1. **`run_backtest.py`** — rigorously backtests that strategy over ~20 years
   across three definitions of "the top 10," market-cap weighted, quarterly
   rebalanced, dividends reinvested, and compares it to the **S&P 500 total
   return**. It's built to *not lie to you* (see "Survivorship bias" below).
2. **`rebalance_now.py`** — the actual "bot": run it (manually or on a schedule)
   to get TODAY's target top-10 portfolio and a concrete **buy / sell / hold**
   plan vs your current holdings, with an optional desktop notification.

> ⚠️ **Not financial advice.** This is a curiosity/research tool. Read the
> Caveats before trusting any number, and remember quarterly rebalancing in a
> taxable account has real tax costs this model ignores.

---

## ⚠️ Important: this must run on YOUR computer

The cloud sandbox this was built in **cannot reach Yahoo Finance** (its network
policy allowlists only PyPI/GitHub). The code is therefore designed to run
locally, where `yfinance` can fetch data normally. It's a ~2-minute setup.

```bash
git clone <this repo>
cd coolio2
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_backtest.py
```

Results land in `./output/` (a console table, `results_summary.md`,
`equity_curves.png`, and raw equity CSVs). Price data is cached in `./data_cache/`
so re-runs are instant.

---

## The three universes

| key        | meaning                                              |
|------------|------------------------------------------------------|
| `nasdaq10` | 10 largest **NASDAQ-listed** companies               |
| `us10`     | 10 largest **U.S.** companies (any U.S. exchange)    |
| `global10` | 10 largest companies **worldwide**                   |

All three are backtested by default.

## Examples

```bash
python run_backtest.py                         # 2006 -> today, cap-weighted
python run_backtest.py --start 2013-01-01      # the all-tech-megacap era
python run_backtest.py --weighting capweight_cap20   # no name above 20%
python run_backtest.py --weighting equal       # 10% each
python run_backtest.py --cost-bps 10           # heavier trading costs
python run_backtest.py --universes us10        # just one universe

# Deeper analysis & honesty checks:
python run_backtest.py --report full           # + per-year, rolling 3y CAGR, beta/tracking error
python run_backtest.py --grid                  # robustness sweep: universes x weightings x {2006,2013}
python run_backtest.py --tax-long 0.20 --tax-short 0.37   # model capital-gains tax drag
python run_backtest.py --mode drift_band --drift-band 0.05  # only trade on >5% drift (less tax/turnover)
python run_backtest.py --mode no_sell          # never trim winners; only sell names that drop out
python run_backtest.py --contribution 0.05     # add 5% new cash each quarter
```

### What the flags do

| flag | effect |
|------|--------|
| `--report full` | adds per-calendar-year returns, rolling 3-yr CAGR (`rolling_cagr.png`), and beta / tracking error / information ratio vs the S&P |
| `--grid` | runs every `universe × weighting × {2006, 2013-start}` combo into one table (`grid_results.md`) so the headline can't hide behind one lucky parameter set |
| `--tax-long` / `--tax-short` | capital-gains tax on realized gains at each rebalance (long- vs short-term picked by holding period). The most honest adjustment for a taxable account |
| `--mode drift_band` | only trades a name when its weight drifts past `--drift-band` — fewer taxable events |
| `--mode no_sell` | never trims a winner; only sells names that fall out of the top 10, steering cash into underweights |
| `--contribution` | periodic new cash (then the equity curve includes deposits) |

---

## 🧠 Survivorship bias — why this backtest is honest

The #1 way these backtests lie: backtesting **today's** top 10 over 20 years.
That secretly "buys Nvidia in 2006 because you already know it wins," producing
a fantasy result.

This repo instead uses **point-in-time membership** (`nasdaq_rebalancer/constituents.py`):
at each quarterly rebalance you hold whoever was *actually* top-10 **then**, and
you sell the names that fell out — Exxon, GE, Citigroup, Intel, PetroChina, and
so on. The membership tables are a good-faith reconstruction of public year-end
market-cap rankings.

A direct consequence you'll see in the output: the strategy's edge is
**regime-dependent**. Pre-2010 the "top 10" was oil, banks, and industrials
(including Citi/AIG/GE, which got crushed in 2008), so the early years are
unremarkable. The big outperformance is concentrated in the post-2013
mega-cap-tech era — which is exactly the period the original thesis is about.
Run with `--start 2013-01-01` to isolate it.

## Caveats (read before believing any number)

1. **Curated membership** — a reconstruction, not an audited dataset.
2. **`global10` is lowest-confidence** — past leaders like PetroChina, China
   Mobile, and Gazprom are delisted ADRs Yahoo can't price; the engine drops them
   and renormalizes, so pre-2015 global results approximate the available subset.
3. **No taxes** — quarterly rebalancing triggers capital gains in a taxable
   account; real after-tax returns are lower.
4. **Simplified costs** — flat bps on turnover; no bid/ask or slippage.
5. **Past performance ≠ future results.**

---

## The reminder bot (`rebalance_now.py`)

```bash
cp holdings.example.json holdings.json      # then edit with your share counts
python rebalance_now.py --universe us10 --notify
```

It ranks the current top 10 from **live** market caps, computes your target
allocation, and prints exactly what to BUY/SELL to get there, flagging any name
that **dropped out** (sell) or is a **new entrant** (buy).

Useful flags for how *you* actually rebalance:

```bash
python rebalance_now.py --no-sell          # only sell drop-outs; never trim winners (tax-friendly)
python rebalance_now.py --whole-shares     # trades in whole share counts, not dollars
python rebalance_now.py --cash-buffer 0.02 # keep 2% in cash, allocate the rest
```

### Scheduling the quarterly nag

**macOS / Linux (cron)** — run on the 1st of Jan/Apr/Jul/Oct at 9am:

```cron
0 9 1 1,4,7,10 * cd /path/to/coolio2 && ./.venv/bin/python rebalance_now.py --notify >> output/reminder.log 2>&1
```

**macOS (launchd)** — create `~/Library/LaunchAgents/com.user.rebalancer.plist`
running the same command via a `StartCalendarInterval` for those months.

**Windows (Task Scheduler)** — create a quarterly trigger that runs
`.venv\Scripts\python.exe rebalance_now.py --notify`.

> Because a quarter only changes 4×/year, a simple approach is a monthly cron
> that runs the script and only notifies when the top-10 membership actually
> changes vs your holdings.

---

## Development / tests

The backtest engine is validated with **synthetic prices** (no network needed):

```bash
python -m tests.test_engine_synthetic
```

These check weight normalization, the 20%-cap logic (incl. infeasible caps),
point-in-time roster selection (no look-ahead), full-run sanity (≈80 rebalances
over 20y), and that transaction costs and capital-gains tax reduce returns, that
the drift band cuts turnover, and that no-sell / contributions behave.

## Layout

```
nasdaq_rebalancer/
  constituents.py   # curated point-in-time top-10 tables (the anti-bias core)
  prices.py         # yfinance download, USD/FX conversion, caching, graceful drops
  backtest.py       # quarterly rebalancing engine (cost, tax, drift-band, no-sell, contributions)
  metrics.py        # CAGR, vol, Sharpe, max drawdown, multiple-vs-benchmark
  analysis.py       # per-year + rolling CAGR, beta/tracking error, robustness grid
  benchmark.py      # S&P 500 total return (+ QQQ)
run_backtest.py     # CLI: backtest all three universes vs S&P 500
rebalance_now.py    # CLI: live top-10 + buy/sell plan + desktop notification
tests/              # synthetic-price engine tests (offline)
CLAUDE.md           # working guide for local Claude Code sessions
docs/VISION.md      # rationale behind every major build decision + roadmap
```
