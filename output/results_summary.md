# Top-10 rebalancing backtest -- results

- **Window:** 2006-01-03 -> 2026-06-12 (~20.4 years)
- **Weighting:** capweight
- **Rebalance:** quarterly, mode=`drift_band` (band 5%)
- **Transaction cost:** 5.0 bps of turnover per rebalance
- **Tax:** long 0% / short 0% on realized gains
- **Contribution:** 0.0 per quarter (start = 1.0)
- **Dividends:** reinvested (prices are split & dividend adjusted)

## Headline comparison

| Strategy               | Final $1 ->   | Total Return   | CAGR   | Vol   |   Sharpe | Max DD   | x vs S&P   |
|------------------------|---------------|----------------|--------|-------|----------|----------|------------|
| Top 10 NASDAQ-listed   | $23.61        | 2,261.1%       | 16.7%  | 23.2% |     0.72 | -50.7%   | 2.73x      |
| S&P 500 (Total Return) | $8.66         | 765.7%         | 11.1%  | 19.4% |     0.57 | -55.3%   | 1.00x      |

## How to read this

- **x vs S&P** is the headline number from the podcast thesis: how many
  times more (or less) ending wealth than the S&P 500 total return.
- A point-in-time roster is used: at each rebalance you hold whoever was
  *actually* top-10 then, and you sell names that dropped out. No look-ahead.

## Caveats (read before believing any number)

1. **Curated membership.** The historical top-10 lists are a good-faith
   reconstruction from public year-end rankings, not an audited dataset.
2. **global10 is lowest-confidence**: several past leaders (PetroChina,
   China Mobile, Gazprom) are delisted ADRs Yahoo can't price, so they get
   dropped and weights renormalize -- the pre-2015 global result is an
   approximation of the available subset.
3. **No taxes.** Quarterly rebalancing in a taxable account triggers
   short/long-term capital gains that this backtest ignores. In a taxable
   account the real after-tax return is meaningfully lower.
4. **Costs are simplified** (flat bps on turnover; no bid/ask, no slippage).
5. **Past performance != future results.** This is a curiosity/research
   tool, not financial advice.

- _Dropped in nasdaq10:_ DELL (x8)