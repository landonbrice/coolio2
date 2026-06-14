# Ablation findings — which component carries the top-10 return, and is it alpha or beta?

_Synthesis of three independent passes (factor regression, ablation ladder, exhaust-mining),
each reproduced on the existing engine. Window **2006 → 2026-06 (~20.4y)**, nasdaq10,
quarterly, dividends reinvested, all comparisons against **QQQ** (Nasdaq-100 ETF, adjusted
close = total-return proxy). **Research, not financial advice.**_

The whole project asks one thing in its title: does the **rebalancing rule** create the edge?
The answer below is no. The edge is **owning a concentrated NASDAQ mega-cap basket at all**,
and against the right benchmark that edge is **beta, not alpha**.

---

## TL;DR

- **Carrier component: CONCENTRATION** — stepping off QQQ into a cap-weighted NASDAQ
  mega-cap basket. That single step delivers the entire ladder edge (+1.75 CAGR pts over QQQ).
- **The rebalancing RULE (the namesake) is among the SMALLEST levers** — `full` is best,
  and every alternative only subtracts (drift_band −0.90 pts, no_sell −1.69 pts). It is
  downside avoidance, not a source of return.
- **Verdict: mostly BETA, no skill vs QQQ.** Single-factor alpha vs QQQ is **+1.3%/yr,
  t_HAC = 0.80 (statistically zero), R² = 0.92, beta = 1.05.** The strategy *is* QQQ.
- **And the concentration "edge" is itself an AAPL+MSFT artifact** — drop those two names
  and the top-10 edge over QQQ collapses from +1.75 → +0.56 pts. The edge rests on 1–2
  survivors, not on concentration as a mechanism.

---

## 1. Alpha vs beta — the strategy *is* QQQ

Right benchmark is QQQ, not the S&P. Against the broad index the top-10 looks like a "3.2x"
hero (see `docs/RESULTS.md`); against QQQ — which already *is* concentrated NASDAQ mega-cap —
the apparent skill evaporates.

| Model (monthly, HAC Newey-West lag 6) | Alpha (ann.) | t(alpha) | Key loading | R² |
|---|---:|---:|---|---:|
| **Single-factor vs QQQ** | **+1.26%** | **0.80** | QQQ β = **1.05** (t 35) | **0.92** |
| FF4 (Carhart) | +4.79% | 2.33 | Mkt-RF +1.16, HML **−0.56**, Mom −0.02 | 0.81 |
| FF4 + QQQ orthogonalized | +4.79% | 3.57 | QQQ_orth **+1.28** (t 17) | **0.94** |

Read:
- **vs QQQ there is no alpha.** +1.3%/yr with t = 0.80 is indistinguishable from zero, and
  QQQ explains **92%** of the strategy's variance. Functionally the same trade.
- **β = 1.05, not a leveraged dose.** The original hypothesis predicted β > 1 (a leveraged
  QQQ) and a positive momentum tilt. Both are **refuted**: β is basically 1.0 (the *same*
  dose), and the momentum loading is −0.02, t = −0.32 (≈ zero).
- **The FF4 "+4.8% alpha" is not skill — it is the Nasdaq/growth tilt FF4 doesn't span.**
  It shows up as a large negative HML (−0.56) plus Mkt-RF 1.16; add QQQ (orthogonalized to
  FF4) and it loads +1.28 (t 17), R² → 0.94, while alpha is *unchanged*. The leftover "alpha"
  is the tech tilt QQQ already prices in.

**Verdict: mostly beta. The edge is co-membership with QQQ, not skill.**

Detail: `output/factor_regression.json`, `factor_regression.py`.

---

## 2. The ladder — which layer adds the most over QQQ

Each rung is rebased and measured against QQQ (1.00x). Marginal = CAGR pts gained over the
rung beneath it.

| Rung | Layer | What changed | CAGR | x QQQ | Max DD | Marginal (CAGR pts) |
|---:|---|---|---:|---:|---:|---:|
| 0 | BASELINE | QQQ | 15.91% | 1.00x | −53.4% | — |
| 1 | (off-index step) | Top-1 biggest NASDAQ name | 17.91% | 1.42x | −57.9% | **+2.00** |
| 2 | CONCENTRATION | Top-3 cap | 17.82% | 1.40x | −58.9% | −0.08 |
| 3 | CONCENTRATION | Top-5 cap | 17.98% | 1.44x | −58.5% | +0.16 |
| 4 | CONCENTRATION | Top-10 cap | 17.66% | 1.36x | −51.3% | −0.32 |
| 5 | WEIGHTING | Top-10 equal | 17.89% | 1.41x | −42.4% | +0.23 |
| 6 | **REBALANCING RULE** | Top-10 cap, `full` (best rule) | 17.66% | 1.36x | −51.3% | **+0.00** |
| 7 | FRICTION/cost | + 5 bps | 17.65% | 1.36x | −51.3% | −0.01 |
| 8 | FRICTION/tax | + 20/37 tax | 17.07% | 1.23x | −51.6% | −0.58 |

**Marginal layer contributions (CAGR pts):**

| Layer | Contribution |
|---|---:|
| **CONCENTRATION (QQQ → top-N cap basket)** | **+1.75** |
| WEIGHTING (cap → equal) | +0.23 |
| **REBALANCING RULE (the title)** | **+0.00** |
| FRICTION/cost (5 bps) | −0.01 |
| FRICTION/tax (20/37) | −0.58 |

**The single biggest jump on the whole ladder is rung 0 → 1: just stepping off QQQ.** The
trivial top-1 name already gets you +2.0 CAGR pts (1.42x QQQ). Adding more names only shuffles
risk — top-10 cap holds 1.36x at lower vol (23.9% vs top-1's 29.3%) and a shallower drawdown.
The intra-concentration dial (top-1 → top-3 → top-5 → top-10) nets *negative* on return
(−0.25 pts) and only worsens single-name risk. So ~100% of the concentration edge is "be in
a mega-cap NASDAQ basket at all," not "concentrate harder."

### The rebalancing RULE is among the least
`full` is the best rule and nothing beats it. Choosing anything else only costs you:

| Rule | CAGR | x QQQ | Δ vs full |
|---|---:|---:|---:|
| `full` (trade all back to target) | 17.66% | 1.36x | — |
| `drift_band` 5% | 16.76% | 1.16x | **−0.90 pts** |
| `no_sell` (never trim a winner) | 15.97% | 1.01x | **−1.69 pts** |

`no_sell` gives back essentially the entire edge (back to 1.01x QQQ). The rule's whole
contribution is **downside avoidance** — pick `full` and don't sabotage it. The ladder's
headline "REBALANCING RULE = 0.0 pts" is tautological (best rule == full by construction);
the *real* size of the lever is the 1.69-pt spread above, and it is asymmetric: rules can only
take return away, never add it. Robust: `full` wins in all 5 start windows tested, no drift
band 2–20% ever beats it, and the ranking survives 25 bps of cost.

Detail: `output/ablation_ladder.json`, `ablation_ladder.py`.

---

## 3. The graveyard & warnings (from the exhaust)

The thesis is "the biggest companies keep winning, so own them and rebalance." The discarded
pile shows how fragile that is.

**Fallen-leader graveyard — "biggest keeps winning" is survivorship of ~1-in-10.** Of the
2005 us10 roster, **only MSFT survives to 2025.** The 2005–2008 leaderboard
(XOM/GE/Citigroup/AIG/BP/Shell/PetroChina/Gazprom — energy, banks, China commodities) was
almost entirely destroyed.

| Universe | Marquee casualties |
|---|---|
| us10 | GE ($380B, the textbook case), XOM ($510B, #1 in 2005-07), Citigroup, AIG, Pfizer, Intel (1 yr) |
| nasdaq10 | Intel ($256B, top-2 in 2005), Cisco ($203B), Comcast, Amgen, Qualcomm, Oracle; one-snapshot wonders PayPal '20, Adobe '23 |
| global10 | **PetroChina ($720B, #1 on earth in 2007), China Mobile, Sinopec, Gazprom — all delisted ADRs the engine cannot price** |

**Data fragility lives exactly where the data is weakest.** global10 pre-2015 is silently
**not the strategy**: PetroChina (dropped 36×), China Mobile (20×), Sinopec, Gazprom are
unpriceable and dropped-and-renormalized — it is "the strategy minus its biggest foreign
names." And the entire overfit tail / every below-index config is `global10` or a
high-concentration `top1`/`top3` slice.

**Top warnings:**

1. **No alpha vs the right benchmark** — vs QQQ, alpha +1.3%/yr (t 0.80), R² 0.92. The
   strategy IS QQQ.
2. **The concentration edge is an AAPL+MSFT artifact** — drop those two and top-10-vs-QQQ
   collapses +1.75 → +0.56 pts; top-1 is ~68% an Apple bet. The edge rests on 1–2 survivors.
3. **The edge is nasdaq10-only** — nasdaq10 mean 17.5% CAGR; us10/global10 mean ~13% and 3
   configs miss the S&P. Do not generalize "top-10" beyond NASDAQ.
4. **The rebalancing RULE only ever subtracts** (no_sell −1.69 pts, drift −0.90 pts vs full)
   — downside avoidance, not alpha.
5. **WEIGHTING is a CAGR wash but a RISK lever** — +0.23 pts on return is a regime
   cancellation (equal +1.71 pts in 2006-12 flips to −1.59 pts in 2013-19), but equal-weight
   robustly cuts max drawdown ~9 pts (−42% vs −51%) and lifts Sharpe ~0.03-0.05. Judge it on
   risk, not return.
6. **Rebalance INTERVAL is the most-swept, least-mattering knob** — exactly 0.00 pt across
   M/Q/SA/A under no_sell. Cadence tuning is curve-fitting on noise.
7. **The in-sample champion is a trap** — best-train `nasdaq10/top3/equal/full/SA` ranks
   #129/264 out-of-sample.
8. **81% of swept configs (214/264) are dominated** — the grid is mostly dead weight.

**Engine caveats surfaced (flagged, do not block the conclusions):** sell-side cost is
double-counted in `backtest._rebalance` so `total_cost` over-reports ~2× (equity curve is
cash-driven and CORRECT — CAGR/ladder unaffected, just don't quote `total_cost`); after-tax
multiples ignore terminal liquidation tax (optimistic in absolute terms, ~fair on x_vs_QQQ);
`top_n` slices `roster[:n]` without re-sorting by cap (minor bias in intra-concentration rungs
only, top-1 is clean).

Detail: `output/exhaust_findings.md`.

---

## 4. What we believe now

1. **The carrier is CONCENTRATION, not the rebalancing rule.** The edge over QQQ is *owning*
   a concentrated NASDAQ mega-cap basket. The single off-index step delivers it; the rule
   named in the title is among the smallest levers and can only subtract.
2. **It is beta, not alpha.** Against QQQ — the correct benchmark — there is no statistically
   meaningful skill (alpha +1.3%/yr, t 0.80; β 1.05; R² 0.92). The "3.2x vs S&P" headline is
   real but is just the NASDAQ growth tilt that QQQ already packages. The predicted leverage
   (β > 1) and momentum tilt are both refuted.
3. **What edge exists is carried by 1–2 mega-winners and is nasdaq10-only.** Remove AAPL+MSFT
   and most of it disappears; outside NASDAQ it barely clears the index; before ~2015 the
   global universe isn't even the strategy on paper.

**Practical translation:** if you want this exposure, you can largely *buy QQQ.* The top-10
construction adds concentration/single-name risk and a tax drag for return that is, against
the right benchmark, statistically indistinguishable from the ETF. Do not pay for "the
rebalancing rule" — just don't pick a bad one (use `full`).

_Research, not financial advice._
