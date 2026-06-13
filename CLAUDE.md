# CLAUDE.md — working guide for this repo

Guidance for a Claude Code session working on this project **locally** on the
user's machine. Read this first; it captures the operational reality and the
non-negotiable design principles so you can be productive immediately and not
re-litigate decisions already made.

For the deeper "why," see **`docs/VISION.md`**.

---

## What this project is

A **backtest + reminder bot** for the "own the top-10 biggest companies,
rebalance quarterly, reinvest dividends" strategy (Philippe Laffont / Coatue
thesis). Two deliverables:

- `run_backtest.py` — backtests the strategy across three universes vs the S&P 500.
- `rebalance_now.py` — the live "bot": ranks today's top 10 and prints a
  buy/sell plan vs the user's holdings.

It is a **research/curiosity tool, not financial advice.** Keep that framing in
all output and docs.

## Status / where things stand

- Active branch: **`claude/nasdaq-rebalancer-bot-54vgi3`**. `main` is an empty
  root commit (the repo started empty), so all real work lives on the branch.
- Open draft PR: **#1** (`landonbrice/coolio2`).
- The engine is fully built and **validated offline with synthetic-price tests**.
  As of this handoff it had **not yet been run against live Yahoo data** — that
  is the immediate next step (see below).

## Local workflow (this is now a local project)

```bash
# one-time
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run it (NOTE: real double hyphens --, and no trailing "# comments" in zsh)
python run_backtest.py --report full          # headline + per-year + rolling + risk
python run_backtest.py --grid                 # robustness sweep
python run_backtest.py --tax-long 0.20 --tax-short 0.37   # after-tax
python rebalance_now.py --universe us10 --no-sell         # the bot

# tests (NO network needed — synthetic prices)
python -m tests.test_engine_synthetic
```

Outputs land in `./output/`; price data caches to `./data_cache/` (both gitignored).

### Gotchas learned the hard way
- **Network:** `yfinance` works on the user's machine but is **blocked in the
  Claude-on-the-web cloud sandbox** (`403: Host not in allowlist` — only
  PyPI/GitHub are reachable there). So: do data-dependent runs locally; use the
  synthetic tests to validate engine logic anywhere.
- **zsh paste:** interactive zsh treats `#` literally and globs `?`, so inline
  comments after a command break. The em-dash from copied markdown (`—`) is not
  `--`. When giving the user commands, put comments on their own lines.
- Foreign/delisted tickers (PetroChina, Gazprom, etc.) often have no Yahoo data;
  the engine is designed to **drop and renormalize**, not crash.

## Architecture

```
nasdaq_rebalancer/
  constituents.py  # curated POINT-IN-TIME top-10 tables (the anti-bias core) + ticker metadata
  prices.py        # yfinance download, USD/FX conversion, parquet cache, graceful per-ticker drops
  backtest.py      # ledger-based quarterly engine: cost, tax, drift_band/no_sell modes, contributions
  metrics.py       # CAGR / vol / Sharpe / max drawdown / multiple; align()
  analysis.py      # per-year + rolling CAGR, beta/tracking error, robustness grid
  benchmark.py     # S&P 500 total return (^SP500TR, falls back to SPY) + QQQ
run_backtest.py    # CLI orchestrator -> table, summary.md, equity/rolling PNGs, grid
rebalance_now.py   # live top-10 + buy/sell plan + desktop notify; --no-sell/--whole-shares/--cash-buffer
tests/             # offline synthetic-price engine tests
docs/VISION.md     # rationale & roadmap
```

## Design principles — do not break these

1. **No survivorship / look-ahead bias.** Membership is point-in-time: at each
   rebalance the portfolio holds whoever was *actually* top-10 then. Never let a
   later roster leak into an earlier date. `members_asof()` enforces this; keep
   it that way. This is the single most important property of the whole project.
2. **Minimal, robust yfinance surface.** Prefer the battle-tested
   `yf.download(..., auto_adjust=True)` path (adjusted close = dividends + splits
   reinvested = total-return proxy). Avoid fragile historical-shares APIs.
3. **Never crash on bad data.** A missing/delisted ticker is dropped with a
   warning and weights renormalize. New data sources must preserve this.
4. **Engine stays offline-testable.** All logic must be exercisable with
   synthetic prices (no network). Add a synthetic test for any new engine feature.
5. **Default behavior is stable.** `mode=full, cost=0, tax=0, contribution=0`
   must remain the plain "growth of $1" result. Add features as opt-in params.
6. **Honesty over flattery.** Surface caveats (taxes, data confidence, regime
   dependence) in output. Don't fabricate precision (e.g. we kept annual
   constituent snapshots rather than inventing quarterly rows — see VISION).

## Validating changes
- Run `python -m tests.test_engine_synthetic` (must stay green; add cases for new
  behavior). Then, locally, sanity-check a real `run_backtest.py --report full`.

## Conventions
- Python 3.11+, std tooling. Match the existing terse-but-commented style.
- Money/weights as floats; equity curves are pandas Series indexed by date,
  re-based to 1.0 at inception.
- Commit messages: clear and descriptive. Keep the "not financial advice" framing.

## Immediate next steps (handoff TODO)
1. **Run live** (`python run_backtest.py --report full` and `--grid`) and capture
   real numbers into `docs/VISION.md` or a results note. Confirm the edge after
   tax and across the robustness grid.
2. Optional: add a GitHub Actions workflow running the synthetic tests (gives the
   PR real checks); add an equal- vs cap-weight chart and a "buy-2010-top-10-and-
   never-rebalance" baseline to isolate what rebalancing itself contributes.
3. Optional: wire in a point-in-time constituents data source for true quarterly
   accuracy (would replace the curated annual snapshots in `constituents.py`).
