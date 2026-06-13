# Live results & honest interpretation

First live run against Yahoo Finance data. **Run date: 2026-06-13.** Window
**2006-01-03 → 2026-06-12 (~20.4 years)**, cap-weighted, quarterly rebalance,
dividends reinvested, 5 bps cost on turnover. Reproduce with:

```bash
python run_backtest.py --report full --grid
```

This file is the "we actually ran it" record the handoff asked for. Numbers will
drift as the window extends and as `constituents.py` is corrected; re-run before
quoting.

---

## 1. Headline (no tax, growth of $1)

| Strategy                | Final $1 → | CAGR  | Vol   | Sharpe | Max DD | x vs S&P |
|-------------------------|-----------:|------:|------:|-------:|-------:|---------:|
| **Top 10 NASDAQ-listed**| **$27.73** | 17.7% | 23.9% | 0.74   | -51.3% | **3.20x**|
| Top 10 U.S. companies   | $11.45     | 12.7% | 21.3% | 0.60   | -51.4% | 1.32x    |
| Top 10 global companies | $9.96      | 11.9% | 20.4% | 0.58   | -51.3% | 1.15x    |
| S&P 500 (Total Return)  | $8.66      | 11.1% | 19.4% | 0.57   | -55.3% | 1.00x    |

The podcast's "beat the market by a multiple" claim **survives an honest,
point-in-time backtest — but only for the NASDAQ-listed reading.** The broader
US/global definitions barely beat the index (and global10 *underperforms* the
S&P after tax). The "multiple" lives almost entirely in NASDAQ mega-cap tech.

## 2. The edge is real but regime-dependent and lumpy

The equity curve (`output/equity_curves.png`, log scale) is the clearest tell:
NASDAQ top-10 and the S&P are **indistinguishable from 2006 to ~2012**, then the
top-10 pulls away and never looks back. Per-year returns confirm it — the entire
3.2x is built in a handful of explosive years:

- Monster outperformance years: **2009 (+47%), 2017 (+39%), 2020 (+45%), 2023
  (+76%), 2024 (+52%)** — each crushing the S&P by 20–50 points.
- It *underperformed* the S&P in ~6 of 20 years (2006, 2010, 2013, 2016, and
  the partial 2026), so it is not a steady drip of alpha.
- **It is not safer — it is more volatile with a worse single-year crash.** 2022
  was **-39.5% vs the S&P's -18.6%** (roughly double the loss). Vol is 24% vs
  19%; the only reason max drawdown looks similar (-51% vs -55%) is timing of the
  2008 GFC, which it had no tech edge to avoid.

Plain reading: **this is a concentrated momentum/size bet on mega-cap tech**, not
a free lunch. Since ~2013 the "top 10" *has been* big tech, so the strategy is
mechanically long the exact factor that led the last decade.

## 3. Tax drag is smaller than feared (~0.6%/yr)

| | CAGR | x vs S&P |
|---|---:|---:|
| NASDAQ10, no tax        | 17.7% | 3.20x |
| NASDAQ10, 20% LT / 37% ST tax | 17.1% | 2.90x |

After-tax CAGR drops only ~0.6 pts and global10 slips below the S&P (0.98x). Why
so mild? **Cap-weighting is naturally low-turnover** — letting winners grow keeps
weights near the cap targets, so each quarterly rebalance trades little and
realizes few gains. The VISION doc feared quarterly rebalancing would be
"tax-hungry"; the data says it isn't, *for a cap-weighted top-10*. (Equal-weight,
which forces you to trim every winner, would be far more tax-hungry.)

## 4. Rebalancing modes — full rebalancing actually wins here

| NASDAQ10 variant | CAGR | x vs S&P | Read |
|---|---:|---:|---|
| `full` (trim to cap weight each Q) | 17.7% | 3.20x | best |
| `drift_band 0.05` (trade only on >5% drift) | 16.7% | 2.73x | slightly worse, less turnover |
| `no_sell` (never trim, only sell drop-outs) | 15.9% | 2.37x | worst |

Counter-intuitively, **trimming and redeploying beat letting winners run** over
this window. `no_sell` left ~1.8%/yr on the table. Interpretation: systematically
recycling capital into the *current* leaders captured the baton-passing across
tech names (Intel→Apple→Nvidia, etc.) better than buy-and-hold of older leaders.
This is a genuine point in favor of the rebalancing rule itself, not just owning
big-caps — though see the caveats before over-reading one window.

## 5. Robustness grid (full table in `output/grid_results.md`)

The edge holds across weightings and both start dates, and **concentrates further
post-2013** (the mega-cap-tech era):

- 2006-start NASDAQ10: 3.2–3.4x across cap/cap20/equal weightings.
- 2013-start NASDAQ10: ~2.3–2.6x (S&P CAGR itself was higher, 14.9%, so the
  *multiple* compresses even as absolute CAGR rises to ~23%).
- us10/global10 cluster at 1.1–1.4x in every cell — the "barely beats" zone.

The headline isn't an artifact of one lucky parameter set. It *is* an artifact of
one lucky **universe** (NASDAQ) and one lucky **decade** (tech leadership).

---

## 6. Honest caveats (what could make 3.2x a mirage)

1. **Curated, approximate membership.** `constituents.py` is a hand-built
   reconstruction of year-end top-10 rankings, not an audited point-in-time
   feed. A few mis-ranked names in the high-turnover early-2010s could move the
   number. This is the single biggest source of error.
2. **Annual snapshots, not quarterly.** We rebalance quarterly but only know the
   roster annually, so intra-year entries/exits are missed. Defensible (the top
   10 turns over slowly) but it smooths over real timing.
3. **global10 is genuinely shaky.** PetroChina, China Mobile, Gazprom, Sinopec
   are dropped at many rebalances (un-priceable delisted ADRs) and weights
   renormalize — pre-2015 global is "the priceable subset," not the true top 10.
4. **No bid/ask, slippage, or borrow.** 5 bps flat is optimistic for the small
   foreign names; immaterial for AAPL/MSFT, but real for the tail.
5. **Survivorship is handled; *selection* is not the point.** Point-in-time
   membership removes look-ahead bias (good), but the result still says nothing
   about whether mega-cap dominance *continues* — only that it paid last decade.
6. **One history, one path.** 20 years is ~one tech super-cycle. The 3.2x is a
   single draw from a distribution we can't see. Treat it as "this rule would
   have worked," not "this rule works."

---

## 7. Extending this into a forward trading strategy

The original goal: turn this from a backtest into something tradeable going
forward. Honest framing first — **what you've actually found is a packaged
mega-cap-momentum factor.** That's a real, well-documented tilt; it is *not*
alpha that's hidden from the market. So the design question is "do I want
leveraged exposure to mega-cap concentration, and how do I size/risk-manage it,"
not "have I found a money machine."

Concrete paths, roughly in order of effort:

**A. Just trade it as-is (lowest effort, honest about what it is).**
- Use `rebalance_now.py --universe nasdaq10` quarterly. It already prints the
  buy/sell plan. The bot is the deliverable; the backtest justifies the rule.
- Expect ~3–5 trades/quarter, low turnover, mild tax. Hold in a tax-advantaged
  account if possible to keep the ~0.6%/yr tax drag at zero.
- **Position-size for a -40% to -55% drawdown.** This is the part people skip.
  2022 already happened in-sample; 2008-style was -51%. If that loss would force
  you to sell, the strategy fails for *you* regardless of the backtest.

**B. Make it a satellite, not the whole portfolio.**
- The cleanest honest use: a 10–30% "concentration sleeve" alongside a broad
  index core. You capture most of the edge with a fraction of the single-factor
  risk. Backtest a blended 70% SPY / 30% nasdaq10 line before committing — it's a
  one-evening addition to `run_backtest.py`.

**C. Add the risk overlay that the backtest is begging for.**
- The strategy's whole weakness is the crash (2x-market drawdowns). A simple
  **trend filter** — e.g. hold the top-10 only while the portfolio (or QQQ) is
  above its 200-day moving average, else go to cash/T-bills — historically cuts
  the worst of 2008/2022 at the cost of some upside. This is the highest-value
  next experiment and is well within the current engine's reach (add a monthly
  regime check to `backtest.py`).
- A volatility-target version (scale exposure inversely to trailing vol) is the
  more sophisticated cousin.

**D. Sharpen the signal before trusting more size.**
- Replace curated annual snapshots with a real point-in-time market-cap feed
  (the #1 data upgrade) so the membership is exact and quarterly.
- Add the **"buy 2013 top-10 and never rebalance"** baseline to *prove* how much
  the rebalancing rule itself adds vs simply owning the 2013 winners. Section 4
  hints rebalancing helps; this isolates it cleanly. (Not yet built — it's the
  most important missing experiment for justifying the *active* rule.)

**E. Things to NOT do (where this quietly becomes gambling).**
- Don't lever it. A 24%-vol, -51%-drawdown line does not want margin.
- Don't switch to equal-weight chasing the +0.2% backtest edge — it triples your
  tax bill and turnover for noise.
- Don't extrapolate the 17.7% CAGR forward. The forward expectation for a
  mega-cap tech tilt is "index + a modest factor premium − your mistakes," not
  17%/yr. The last decade was an outlier you cannot assume repeats.

**Bottom line:** the rule is real and worth running as a small, risk-budgeted,
trend-filtered satellite — owned with eyes open that you're buying concentrated
mega-cap-tech beta, not a market-beating secret.
