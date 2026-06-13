# Tax re-run of sweep short-list

Full window **2006-01-01 -> 2026-06-13**, nasdaq10, 5 bps cost, dividends reinvested. Tax = **20% long / 37% short** on realized gains at each rebalance.

S&P 500 TR over the window: CAGR 11.1%, vol 19.4%, maxDD -55.3%.

| config | CAGR no-tax | CAGR taxed | tax drag (pt/yr) | x S&P no-tax | x S&P taxed | vol% | maxDD% | turnover/yr |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| cap baseline (low turnover) | 17.7% | 17.1% | 0.6 | 3.20x | 2.90x | 22.9 | -51.3 | 8% |
| equal full  (pre-tax winner) | 17.9% | 15.8% | 2.0 | 3.32x | 2.32x | 22.2 | -42.5 | 27% |
| equal drift_band | 17.2% | 16.0% | 1.2 | 2.96x | 2.38x | 21.6 | -42.2 | 12% |
| equal no_sell | 16.4% | 15.9% | 0.6 | 2.59x | 2.34x | 22.4 | -46.3 | 7% |
| equal full, ANNUAL | 18.2% | 16.5% | 1.7 | 3.51x | 2.61x | 22.3 | -41.0 | 18% |
| top5  equal full (max CAGR) | 18.8% | 17.2% | 1.6 | 3.90x | 2.95x | 24.0 | -58.1 | 22% |
| top3  equal full | 18.6% | 16.8% | 1.8 | 3.78x | 2.76x | 23.9 | -58.4 | 24% |

**Read:** tax drag scales with turnover. Equal-weight `full` trims every winner each period (high turnover -> biggest drag); cap-weight, drift_band, no_sell, and annual cadence all cut turnover and therefore tax. Compare CAGR-taxed (not no-tax) when choosing a config for a taxable account; in a tax-advantaged account the no-tax column applies.
