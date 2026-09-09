# Research design — survivorship-free signal study

**Status:** design / not yet built. Prerequisite for the momentum-entry and quality-factor extensions.

**The question:** *If a stock shows trait X today, what is the probability it reaches outcome Y — measured across **every** stock that showed X, winners and losers alike?*

---

## 1. Why this exists

The current backtest answers "what would owning the top-10 have returned." It cannot answer the forward question the thesis actually asks: **can we identify tomorrow's winners early — as they ascend toward the top — using only information available at the time?** Answering that honestly requires defeating survivorship bias at the design level, not patching it afterward.

## 2. The bias trap, and the fix

- **Wrong (survivorship):** take today's winners → look back → catalog their shared traits → conclude "high momentum / high margins predict winning." The failures were never counted, so *every* trait looks predictive.
- **Right (forward conditional):** at each point in time, take **every** stock with trait X — *including the ones that later stalled or died* — and measure the fraction that reached outcome Y.

**Worked example.** ~200 stocks had >40% gross margins in 2013. If 12 reached the top-50 by 2024, that is **6%** versus a ~2% all-stock base rate — a **3× lift**, and still a 94% failure rate. We estimate **P(Y | X)** over the full cohort and compare to the base rate **P(Y)**. The *lift* is the edge; the *absolute probability* is the reality check. A signal can be genuinely real and still mostly fail.

## 3. The study

**Universe.** Point-in-time *monthly* membership of the **top ~500 by market cap**, including delisted / fallen names (non-negotiable — see §4).

**Outcomes Y** (one per run):
- Forward 3y / 5y total return — continuous, *primary*
- Advanced to the next market-cap tier within N years — binary
- Entered top-10 / top-50 within N years — binary
- "Survived" — still in the universe, not down >50%, after N years — binary

**Signals X** (strictly ex-ante; two families that map to the two beliefs):

| Price / technical — *the momentum thesis* | Fundamental / quality — *the durability thesis* |
|---|---|
| 12–1 momentum (trailing 12m, skip last month) | ROIC + ROIC persistence |
| **market-cap rank velocity (Δrank over 12m)** | gross-margin level **and** stability (pricing power) |
| % above the 200-day moving average | capital intensity = capex/sales (low = capital-light) |
| volatility-scaled momentum (trend quality) | revenue growth (3y CAGR); net cash / low leverage |

**Method.** Decile-bucket by each X (and by X-combinations) → mean/median forward Y per bucket; logistic / panel regression for the binary outcomes. Always report **base rate → conditional rate → lift**, validated out-of-sample (train/test, as in the existing sweep).

## 4. Data requirement — the long pole

yfinance is **disqualified**: it silently drops delisted tickers, which re-introduces the exact survivorship bias this study exists to kill. Requires a **survivorship-bias-free, point-in-time** dataset with dead tickers and *as-reported* fundamentals (lagged ~3 months): **Sharadar (SF1/SEP), Norgate, or CRSP/Compustat.** Sourcing this is the real cost of the project — not scraping a top-500 list.

## 5. Landmines

- **Ex-ante features only** — any outcome leaking into a feature is look-ahead and will look brilliant and be fake.
- **Base rate before conditional rate** — or you mistake a common outcome for a signal.
- **Multiple testing is the silent killer** — pre-commit to ~4–5 motivated signals; do not screen 50 and keep the winners.
- **One regime** — ~20 years ≈ one tech supercycle; cross-validate across sub-periods.

## 6. Sequencing

- **v0 — de-risk, price-only.** 12–1 momentum + rank-velocity on a survivorship-aware universe → forward-3y-return buckets. Answers the single question that justifies everything else: *does entering ascenders beat entering at the summit?* — with the smallest possible data lift.
- **v1 — add the fundamental/quality family** and test momentum × quality.
- **Gate:** build v1 only if v0 shows a real, out-of-sample-stable lift over base rate.

## 7. Success criterion

A signal is "real" only if its forward-outcome lift over base rate (a) is economically meaningful, (b) survives out-of-sample, and (c) is stable across sub-periods. Everything else is data-mining.

---
*Research / curiosity tool. Not financial advice.*
