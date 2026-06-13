# Vision & rationale

The "why" behind this build. `CLAUDE.md` covers how to operate the repo; this doc
explains the decisions, so anyone (human or agent) picking it up understands the
reasoning rather than reverse-engineering it from code.

---

## 1. The thesis we're testing

From a Philippe Laffont (Coatue) talk on liquidity and the *durability of cash
flows*: the biggest companies have become more likely to keep compounding, so a
simple rule — **own the ~10 largest companies, rebalance into the new leaders
periodically, reinvest dividends** — would have beaten the S&P 500 over the last
decade-plus, reportedly by a multiple. A related observation: a $100B company
reaching $1T has been more likely than a startup reaching unicorn status.

The goal of this project is twofold:
1. **Honestly test** whether that rule actually beat the S&P 500 over ~20 years.
2. If it holds up, give the user a **bot** that reminds them quarterly what to
   buy/sell to follow it.

We deliberately separated these: prove the strategy *first*, automate *second*.

## 2. The decision that defines the whole project: no survivorship bias

The naive version of this backtest — take *today's* top 10 (Nvidia, Apple, …)
and run them back 20 years — is worthless. It secretly assumes you knew in 2006
which companies would win, "buying Nvidia early" with hindsight. It produces a
fantasy multiple and is the #1 reason these backtests lie.

**Our answer: point-in-time membership.** At each quarterly rebalance the
portfolio holds whoever was *actually* in the top 10 *at that time*, and sells
the ones that fell out (Exxon, GE, Citigroup, Intel, PetroChina, …). This mirrors
exactly the real-world rule the user described and removes look-ahead bias.

Consequence we expect to see (and consider a feature, not a bug): the strategy's
edge is **regime-dependent**. Pre-2010 the "top 10" was oil, banks, and
industrials — including Citi/AIG/GE, which were crushed in 2008 — so early years
should be unremarkable. The outperformance should concentrate in the post-2013
mega-cap-tech era, which is precisely the period the thesis is about. A backtest
that *hides* this would be the dishonest one.

## 3. Three universes

The user asked to test all three readings of "the top 10":
- `nasdaq10` — 10 largest NASDAQ-listed companies.
- `us10` — 10 largest U.S. companies on any U.S. exchange.
- `global10` — 10 largest companies worldwide.

They diverge meaningfully (global10 includes Saudi Aramco, TSMC, Tencent;
us10 adds NYSE names like Berkshire/JPMorgan that nasdaq10 excludes), so comparing
them is informative about *what* is driving any edge.

## 4. Data decisions and their tradeoffs

- **Prices via `yfinance`, adjusted close.** Auto-adjusted close folds in
  dividends and splits, giving a clean total-return proxy (dividends reinvested,
  as the thesis requires). We intentionally use only the most stable yfinance
  path and cache to parquet.
- **Membership is curated, not fetched.** Yahoo gives prices but not historical
  market-cap *rankings*. So the point-in-time top-10 lists are hand-curated from
  public year-end rankings (FT/Wikipedia, companiesmarketcap, PwC, Visual
  Capitalist) in `constituents.py`. They are approximate and labeled with
  confidence tiers.
- **Annual snapshots, deliberately not quarterly.** The top 10 turns over slowly.
  Fabricating 240 quarterly rows would be *false precision*, not accuracy, so we
  kept honest annual (year-end) snapshots and documented the limitation. A real
  point-in-time data vendor is the right upgrade if quarterly accuracy matters.
- **Cap weights via price-drift scaling.** Cap ≈ shares × price, and shares are
  roughly constant short-term, so at each rebalance we scale a name's year-end
  snapshot cap by its price change since the snapshot to estimate current cap —
  recovering current-cap weighting without needing historical share counts.
- **global10 is lowest-confidence.** Several past leaders (PetroChina, China
  Mobile, Gazprom) are delisted ADRs Yahoo can't price; the engine drops them and
  renormalizes, so pre-2015 global is an approximation of the available subset.
  This is disclosed in output and README.

## 5. Why the engine is ledger-based

We rewrote the engine to track a per-name ledger (shares, average cost basis,
acquisition date). This wasn't gold-plating — it's required to model the things
that decide whether the strategy is *actually* worth following in real life:
- **Capital-gains tax** on realized gains at each rebalance (long vs short rate by
  holding period). For a taxable account this is the single biggest honesty
  adjustment, and quarterly rebalancing is tax-hungry.
- **Rebalancing modes** beyond textbook "full": `drift_band` (only trade past a
  drift threshold) and `no_sell` (only sell names that exit the top 10) — both
  reduce taxable events and reflect how a real person rebalances.
- **Contributions** of new cash, since most people add money over time.

Defaults keep the plain growth-of-$1 result intact; everything else is opt-in.

## 6. Honesty commitments

Surfaced directly in the tool output and README:
1. Curated (approximate) membership, with confidence tiers.
2. global10 data caveats.
3. No taxes unless asked for (`--tax-*`); taxes materially lower real returns.
4. Simplified costs (flat bps, no slippage/bid-ask).
5. Past performance ≠ future results. Not financial advice.

## 7. Roadmap

- **Run live & record results** (the immediate gap): confirm the edge survives
  tax and shows up across the robustness grid; capture numbers here.
- **Baselines that isolate the source of return:** equal- vs cap-weight; and a
  "buy the 2010 top 10 and never rebalance" line to quantify what the
  *rebalancing* itself adds vs just owning big-caps.
- **Better data:** a point-in-time constituents source for true quarterly
  accuracy; optionally reconstruct caps from historical shares.
- **Bot hardening:** brokerage position import so `holdings.json` stays in sync;
  generate the exact cron/launchd/Task Scheduler unit for the user's OS.
- **CI:** GitHub Actions running the offline synthetic tests on every push.

## 8. Explicitly out of scope (for now)

- **Auto-trading.** The bot recommends; a human executes. Keeping a person in the
  loop is intentional, not a missing feature.
- Leverage, options, shorting, intraday — this is a long-only, end-of-day model.
