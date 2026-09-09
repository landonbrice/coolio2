# Exhaust-mining findings — what got thrown away, and what that teaches

_Generated 2026-06-14 by the FAILURE / EXHAUST-MINING agent. Research, not financial advice._

Scope: scraped everything discarded — the 264-config sweep (`output/sweep_results.csv`),
the point-in-time graveyard in `nasdaq_rebalancer/constituents.py`, and every drop-note
routed to `output/dropzone/` by the regression agent, the ablation engineer, and the
layer reviewers. The thesis under test is "the biggest companies keep winning, so own
them and rebalance." Below is the pile of things that **died**, grouped by why.

---

## 1. The fallen-leader graveyard (the literal failure cases of "biggest keeps winning")

These are names that were ACTUALLY in a point-in-time top-10 snapshot and later fell out.
A buy-and-never-rebalance investor who anchored on any of these got hurt; the rebalancing
rule's whole job is to bury them on schedule. "Exit era" = last year-end snapshot the name
governs (it controls the following year, then drops). Caps are peak snapshot cap (USD bn).

### us10 — fallen leaders
| Ticker | Name | Entry→Exit era | Yrs in | Peak cap | Note |
|---|---|---|---|---|---|
| INTC | Intel | 2005→2005 | 1 | $150B | gone after one year; never returned to us10 |
| C | Citigroup | 2005→2006 | 2 | $275B | #4 in 2005; GFC erased it |
| PFE | Pfizer | 2005→2006 | 2 | $185B | |
| AIG | AIG | 2005→2006 | 2 | $185B | GFC bailout; never came back |
| T | AT&T | 2007→2008 | 2 | $250B | |
| IBM | IBM | 2009→2012 | 4 | $217B | slow bleed out of the top 10 |
| GE | General Electric | 2005→2016 | 12 | $380B | the textbook fallen leader: #1/#2 for years, gone by 2017 |
| WFC | Wells Fargo | 2008→2015 | 4 | $285B | re-entered then fell |
| PG | Procter & Gamble | 2006→2014 | 7 | $246B | re-entered |
| CVX | Chevron | 2007→2013 | 6 | $240B | commodity-era leader, faded |
| XOM | ExxonMobil | 2005→2022 | 15 | $510B | #1 in 2005-07; out, brief 2022 re-entry, gone |
| JPM | JPMorgan | 2008→2022 | 8 | $467B | re-entered/fell repeatedly |
| JNJ | Johnson & Johnson | 2005→2022 | 15 | $462B | long-tenured defensive, finally dropped |
| WMT | Walmart | 2005→2020 | 12 | $408B | re-entered |
| BAC | Bank of America | 2005→2017 | 3 | $306B | |
| V | Visa | 2018→2023 | 5 | $533B | |
| UNH | UnitedHealth | 2021→2022 | 2 | $496B | |

### nasdaq10 — fallen leaders
| Ticker | Name | Entry→Exit era | Yrs in | Peak cap | Note |
|---|---|---|---|---|---|
| INTC | Intel | 2005→2020 | 16 | $256B | the marquee NASDAQ casualty: top-2 in 2005, finally fell after 2020 |
| CSCO | Cisco | 2005→2019 | 15 | $203B | dot-com royalty, slow exit |
| CMCSA | Comcast | 2005→2020 | 16 | $239B | |
| AMGN | Amgen | 2005→2018 | 14 | $127B | |
| QCOM | Qualcomm | 2005→2016 | 11 | $125B | re-entered |
| ORCL | Oracle | 2005→2012 | 8 | $158B | also a listing-venue casualty (moved NASDAQ→NYSE 2013) |
| GILD | Gilead | 2007→2015 | 5 | $149B | HepC pop then fade |
| DELL | Dell | 2005→2006 | 2 | $72B | went private 2013, relisted 2018; partial price data |
| EBAY | eBay | 2005→2006 | 2 | $58B | |
| PEP | PepsiCo | 2018→2022 | 4 | $249B | re-entered |
| PYPL | PayPal | 2020→2020 | 1 | $275B | one-snapshot wonder (2020 bubble) |
| ADBE | Adobe | 2023→2023 | 1 | $272B | one-snapshot wonder |

### global10 — fallen leaders (incl. the delisted ADRs the runs literally cannot price)
| Ticker | Name | Entry→Exit era | Yrs in | Peak cap | Note |
|---|---|---|---|---|---|
| **PTR** | PetroChina (ADR) | 2006→2014 | 9 | **$720B** | was **#1 in the world (2007)**; delisted 2022; dropped **36×** at runtime |
| **CHL** | China Mobile (ADR) | 2007→2012 | 5 | $330B | delisted 2021; dropped **20×** at runtime |
| **OGZPY** | Gazprom (ADR) | 2007→2007 | 1 | $330B | halted 2022; dropped **4×**, no usable history |
| **SNP** | Sinopec (ADR) | 2007→2007 | 1 | $220B | delisted 2021; dropped **4×**, no usable history |
| 1398.HK | ICBC | 2007→2015 | 9 | $290B | priceable but fell out |
| 0700.HK | Tencent | 2016→2021 | 6 | $680B | peaked then fell out of global top-10 |
| BABA | Alibaba (ADR) | 2017→2020 | 4 | $628B | |
| BHP | BHP (ADR) | 2009→2011 | 3 | $240B | commodity super-cycle leader |
| BP / SHEL / TM | BP / Shell / Toyota | 2005→2006-08 | 2-4 | $200-240B | the entire 2005 energy/auto cohort, swept out |
| GE, C, BAC, WMT, JNJ, CVX, IBM, WFC, JPM, PG, UNH | (see us10) | various | — | — | same fallen leaders recur in global10 |

**Pattern.** The 2005-2008 leaderboard (XOM/GE/Citi/AIG/BP/Shell/PetroChina/Gazprom —
energy, banks, China commodities) was almost ENTIRELY destroyed. Of the 2005 us10 roster,
only MSFT survives to 2025. The four delisted Chinese/Russian ADRs are not even survivorship
casualties — they are **data casualties**: PTR (the literal #1 company on earth in 2007) and
CHL/SNP/OGZPY return zero Yahoo history and are silently dropped-and-renormalized at every
pre-2015 rebalance (PTRx36, CHLx20, OGZPYx4, SNPx4; DELLx8 in nasdaq10). So the "global10"
backtest before ~2015 is quietly NOT the strategy on paper — it is the strategy minus its
biggest non-US names, run on the priceable leftovers.

---

## 2. The overfit tail (high in-sample, weak or unstable out-of-sample)

Split: TRAIN = 2006-2017, TEST = 2018-2026. The test era IS the mega-cap-tech boom, so
nearly every config posts a HIGHER test CAGR than train — the tide lifted all boats. The
overfit signal therefore lives in **rank degradation** (train winner ≠ test winner) and in
**negative residuals** off the train→test fit (`test = 15.4 + 0.53·train`, Pearson 0.59,
Spearman 0.54 — only moderate stability).

- **The single sharpest overfit fact:** the best config on TRAIN by CAGR,
  `nasdaq10/top3/equal/full/SA` (16.4% train), lands at **#129 of 264 on TEST** (21.7%).
  Picking the in-sample champion bought you a literally median out-of-sample result.
- **Biggest negative residuals (best train relative to a weak test) — the overfit tail:**
  | Config | Train CAGR | Test CAGR | Residual |
  |---|---|---|---|
  | global10/top1/cap/full/(M,Q,SA,A) | 10.8% | 16.0% | **-5.1pt** |
  | global10/top10/equal/drift_band/Q | 8.0% | 15.0% | -4.7pt |
  | global10/top10/equal/full/M | 8.7% | 15.8% | -4.2pt |
  | global10/top10/equal/full/A | 8.4% | 15.8% | -4.0pt |
- **Worst rank-degradation (train rank → test rank):** the `nasdaq10/top3/equal/*` family
  sat at train ranks #1-#8 and fell to test ranks #119-#139 — top-3 concentration won the
  pre-2017 path and reverted afterward. global10/top1 fell from train rank ~#93 to test
  rank ~#257 (a 164-place drop, but it was never good).
- **Read:** every name in the overfit tail is `global10` or a high-concentration
  `top1`/`top3` config. The discarded tail is dominated by the lowest-data-confidence
  universe and the highest-single-name-risk slices — exactly where curve-fit is easiest.

---

## 3. Dominated configs (the bulk of the sweep is dead weight)

- **214 of 264 (81%) configs are dominated** — some other config has ≥ CAGR, ≥ Sharpe,
  ≤ vol, AND ≤ |maxDD|. Only 50 sit on the 4-D efficient frontier.
- Dominated share by universe: nasdaq10 78, us10 76, global10 60. The non-dominated
  survivors skew to global10 (28) only because global10 occupies the low-vol corner nobody
  else reaches — not because it's good (it's the worst on return).
- **3 configs fail to beat the S&P 500 outright (x_S&P ≤ 1.0):**
  `global10/top10/equal/drift_band/Q` (0.96×), `.../M` (0.96×),
  `us10/top10/equal/drift_band/Q` (1.00×). All three are global10/us10 + drift_band — the
  weakest universe paired with the laggiest rebalancing rule.
- Universe means tell the whole story: **nasdaq10 17.5%** mean full CAGR (min 16.0!), vs
  **us10 13.1%** and **global10 13.2%**. The "edge" is a nasdaq10 phenomenon; us10/global10
  barely clear the index. 88/88 nasdaq10 configs beat S&P by ≥1.5×; only 29/88 us10 do.

---

## 4. Dropped-config / dropped-knob PATTERNS (the levers that did nothing)

From the ablation ladder + reviewer drop-notes, the things discarded as non-levers:

- **REBALANCE INTERVAL (M/Q/SA/A) is near-inert, and totally inert under no_sell.**
  31 of 66 (universe,top_n,weighting,mode) groups show <0.05pt CAGR spread across all four
  cadences. Mean interval spread: full 0.14pt, drift_band 0.35pt, **no_sell 0.00pt** (if you
  never trim, how often you "rebalance" is a no-op). The four global10/top1/cap/full rows are
  byte-identical across M/Q/SA/A. Cadence is the most-swept, least-mattering axis.
- **REBALANCING RULE is the smallest return lever — and only ever subtracts.** `full` is
  best in all 5 start windows; no_sell costs **-1.69pt** CAGR and drift_band **-0.90pt** vs
  full on the spine config (ablation). Across the full sweep, no_sell averages -0.36pt
  (worse in 52/84 pairs) and drift_band -0.32pt (worse in 68/84). The thing in the project's
  TITLE ("rebalance") is a downside-avoidance choice, not a source of edge.
- **WEIGHTING (cap vs equal) is a sign-flipping near-wash on RETURN** (+0.226pt full-window
  = a cancellation of +1.71pt in 2006-12 and -1.59pt in 2013-19; equal beat cap in only
  9/20 years). The ablation ladder demotes it to a footnote. BUT the reviewer flagged this as
  UNDERSOLD on RISK: equal-weight top-10 cuts maxDD ~9pt (ladder) / ~1.5pt mean (sweep) and
  lifts Sharpe ~0.03-0.05 for free. The discarded "weighting doesn't matter" verdict is true
  for CAGR, false for drawdown.
- **capweight_cap20 (20% single-name cap) barely registers** — it only exists at top_n=10
  (36 configs) and almost never reaches the frontier (2 of 50 non-dominated). A cap on the
  cap-weight is a knob the sweep added and the frontier ignored.
- **The "CONCENTRATION edge" is a TWO-NAME (AAPL+MSFT) artifact, not a generic effect.**
  Reviewer: dropping AAPL+MSFT from the panel collapses the top-10 edge over QQQ from +1.75
  to +0.56pt; dropping AAPL alone takes top-5 from +2.07 to +0.54. top-1 is ~68% an AAPL bet
  (AAPL 56/82 quarters). The carrier layer is real but carried by one or two survivors.
- **FF4 "alpha" (+4.8%/yr, t=2.33) was dropped as not-real-skill.** Against the correct
  benchmark (QQQ) single-factor alpha is +1.3%/yr, t=0.80 (statistically zero), R²=0.92 — the
  strategy IS QQQ. The FF4 alpha is the Nasdaq/growth tilt FF doesn't span (HML -0.56,
  Mkt-RF 1.16); QQQ orthogonalized to FF4 loads +1.28 (t=17). Predicted momentum tilt and
  beta>1 both refuted (Mom -0.017, QQQ beta 1.05).

---

## 5. Engine bugs surfaced in the exhaust (flagged, not blocking)

- **Sell-side transaction cost double-counted** in `backtest._rebalance`
  (`cost += proceeds*cost_rate` ~line 223 AND `cost += sell_cost` ~line 228), while `cash`
  is debited once. `BacktestResult.total_cost` over-reports (~2×sell + buy); equity curve is
  driven by `cash` so CAGR/ladder are UNAFFECTED, but any friction figure quoted off
  `total_cost` is ~2× too high. Conservative for "full wins net of cost."
- **`members_asof` / `top_n` slices `roster[:n]` WITHOUT re-sorting by cap.** pos0 happens to
  equal max-cap in every row so top-1 is clean, but 2006/2008-15/2017-22 rows aren't strictly
  cap-descending in lower ranks, so top-3/top-5 can pick by list position, not true cap rank.
  Small, mostly-immaterial bias to the intra-concentration rungs.
- **Terminal-tax omission:** the engine taxes per-rebalance realized gains but never charges
  exit tax on terminal unrealized gains, so after-tax multiples are optimistic in absolute
  terms (~25× would owe a big liquidation bill). Applies to QQQ too, so x_vs_QQQ stays ~fair.
- **Sharpe = CAGR/vol** (not mean-excess/vol) in `metrics.compute` — non-standard but applied
  identically everywhere, so it doesn't bias comparisons.
- **early-window pricing:** only 9 of 10 nasdaq10 names priced pre-2013, so "top-10 equal"
  is ~9-equal early; symmetric across cap/equal so no comparison bias.

---

## 6. WARNING lines (each pattern, one line)

1. The 2005-2008 leaderboard (XOM/GE/Citi/AIG/BP/Shell/PetroChina/Gazprom) was almost
   entirely destroyed; of the 2005 us10 roster only MSFT survives to 2025 — "biggest keeps
   winning" is survivorship of 1-in-10, not a law.
2. global10 pre-2015 is silently NOT the strategy: PetroChina (#1 in 2007), China Mobile,
   Sinopec, and Gazprom are unpriceable and dropped-and-renormalized (PTRx36, CHLx20), so
   early global10 is "the strategy minus its biggest foreign names."
3. The whole edge is a nasdaq10 phenomenon (mean 17.5% CAGR) — us10 and global10 mean ~13%
   and 3 configs fail to beat the S&P at all; do not generalize "top-10" beyond NASDAQ.
4. 81% of swept configs (214/264) are dominated — the parameter grid is mostly dead weight,
   and the survivors only differ on the risk axis.
5. The in-sample champion is a trap: best-train `nasdaq10/top3/equal/full/SA` ranks #129/264
   out-of-sample — never trust the sweep's section-A winner forward.
6. Rebalance INTERVAL is the most-swept, least-mattering knob (no_sell: exactly 0.00pt across
   M/Q/SA/A) — cadence tuning is curve-fitting on noise.
7. The rebalancing RULE (the project's namesake) is the smallest return lever and only ever
   subtracts (no_sell -1.69pt, drift -0.90pt vs full) — "rebalance" is downside avoidance,
   not alpha.
8. WEIGHTING is a sign-flipping wash on RETURN (+0.23pt = +1.71 early cancelling -1.59 in the
   mega-cap era) but quietly worth ~9pt of drawdown and +0.03-0.05 Sharpe on RISK — judging it
   by CAGR alone discards its real contribution.
9. The "concentration edge" is an AAPL+MSFT artifact: drop those two and top-10-vs-QQQ
   collapses from +1.75 to +0.56pt; top-1 is ~68% an Apple bet — the edge rests on 1-2
   survivors, not a robust concentration premium.
10. There is no real alpha vs the right benchmark: vs QQQ, single-factor alpha is +1.3%/yr
    (t=0.80, R²=0.92) — the strategy IS QQQ; the FF4 "+4.8% alpha" is just the growth tilt
    FF doesn't span.
11. Reported friction is ~2× overstated by a double-counted sell-side cost bug in
    `_rebalance`; equity/CAGR are unaffected but don't quote `total_cost`.
12. After-tax multiples ignore terminal liquidation tax (optimistic in absolute terms);
    top_n slicing isn't cap-re-sorted (minor rank-order bias below pos0).
13. The overfit tail and every below-index config concentrate in the lowest-data-confidence
    universe (global10) and the highest-single-name-risk slices (top1/top3) — fragility lives
    exactly where the data is weakest.
