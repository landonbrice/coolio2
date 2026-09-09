# Strategy sweep & optimization

Full period **2006-01-01 -> 2026-06-13**, 5 bps cost, **no tax**, dividends reinvested. 264 structural configs.

Inputs swept: `universe x top_n x weighting x mode x interval`. Outputs: CAGR (return), vol & maxDD (risk), Sharpe (combined).

**Benchmark (S&P 500 TR, full):** CAGR 11.1%, vol 19.4%, Sharpe 0.57, maxDD -55.3%.


## A. Highest return (max CAGR, full period)

| config                            |   CAGR% |   vol% |   Sharpe |   maxDD% |   x_S&P |
|:----------------------------------|--------:|-------:|---------:|---------:|--------:|
| nasdaq10/top5/equal/full/SA       |    18.8 |   24   |     0.78 |    -58.1 |    3.9  |
| nasdaq10/top5/equal/full/A        |    18.7 |   24.2 |     0.78 |    -58.1 |    3.87 |
| nasdaq10/top3/equal/drift_band/M  |    18.7 |   23.6 |     0.79 |    -57.3 |    3.82 |
| nasdaq10/top5/equal/full/Q        |    18.7 |   23.9 |     0.78 |    -57.5 |    3.81 |
| nasdaq10/top3/equal/full/SA       |    18.6 |   23.9 |     0.78 |    -59.1 |    3.79 |
| nasdaq10/top3/equal/full/Q        |    18.6 |   23.9 |     0.78 |    -58.4 |    3.78 |
| nasdaq10/top5/equal/full/M        |    18.5 |   24   |     0.77 |    -57.4 |    3.74 |
| nasdaq10/top3/equal/full/M        |    18.5 |   23.9 |     0.78 |    -58.3 |    3.74 |
| nasdaq10/top3/equal/drift_band/SA |    18.4 |   23.7 |     0.78 |    -59.3 |    3.65 |
| nasdaq10/top5/equal/drift_band/SA |    18.3 |   23.5 |     0.78 |    -58.2 |    3.6  |
| nasdaq10/top3/equal/drift_band/Q  |    18.3 |   23.5 |     0.78 |    -57.5 |    3.59 |
| nasdaq10/top3/equal/full/A        |    18.2 |   24   |     0.76 |    -59.5 |    3.55 |

## B. Highest risk-adjusted return (max Sharpe, full period)

| config                            |   CAGR% |   vol% |   Sharpe |   maxDD% |   x_S&P |
|:----------------------------------|--------:|-------:|---------:|---------:|--------:|
| nasdaq10/top10/equal/full/SA      |    18.2 |   22.2 |     0.82 |    -42.5 |    3.52 |
| nasdaq10/top10/equal/full/A       |    18.2 |   22.3 |     0.82 |    -41   |    3.51 |
| nasdaq10/top10/equal/full/Q       |    17.9 |   22.2 |     0.8  |    -42.5 |    3.32 |
| nasdaq10/top10/equal/full/M       |    17.7 |   22.2 |     0.8  |    -42.4 |    3.24 |
| nasdaq10/top10/equal/drift_band/Q |    17.2 |   21.6 |     0.8  |    -42.2 |    2.96 |
| nasdaq10/top10/equal/drift_band/M |    17.1 |   21.6 |     0.79 |    -42.5 |    2.91 |
| nasdaq10/top3/equal/drift_band/M  |    18.7 |   23.6 |     0.79 |    -57.3 |    3.82 |
| nasdaq10/top10/cap_cap20/full/Q   |    17.9 |   22.9 |     0.78 |    -51.1 |    3.37 |
| nasdaq10/top5/equal/drift_band/M  |    18.1 |   23.2 |     0.78 |    -56.8 |    3.48 |
| nasdaq10/top5/equal/full/SA       |    18.8 |   24   |     0.78 |    -58.1 |    3.9  |
| nasdaq10/top5/equal/drift_band/SA |    18.3 |   23.5 |     0.78 |    -58.2 |    3.6  |
| nasdaq10/top10/cap_cap20/full/SA  |    17.9 |   22.9 |     0.78 |    -51.2 |    3.33 |

## C. Pareto frontier (efficient return-vs-risk trade-offs)

Each config below is non-dominated: nothing in the sweep has both higher CAGR and lower vol. Pick by risk appetite.

| config                            |   CAGR% |   vol% |   Sharpe |   maxDD% |   x_S&P |
|:----------------------------------|--------:|-------:|---------:|---------:|--------:|
| global10/top10/cap/drift_band/A   |    12.7 |   18.4 |     0.69 |    -46   |    1.32 |
| global10/top5/equal/drift_band/SA |    14.2 |   20.2 |     0.7  |    -53.6 |    1.75 |
| global10/top5/equal/drift_band/M  |    14.3 |   20.3 |     0.7  |    -54.9 |    1.76 |
| global10/top5/equal/drift_band/Q  |    14.3 |   20.3 |     0.7  |    -53.6 |    1.76 |
| global10/top5/equal/drift_band/A  |    14.5 |   20.7 |     0.7  |    -53.8 |    1.83 |
| global10/top5/equal/full/SA       |    14.6 |   20.7 |     0.7  |    -55.3 |    1.87 |
| nasdaq10/top10/equal/drift_band/M |    17.1 |   21.6 |     0.79 |    -42.5 |    2.91 |
| nasdaq10/top10/equal/drift_band/Q |    17.2 |   21.6 |     0.8  |    -42.2 |    2.96 |
| nasdaq10/top10/equal/full/Q       |    17.9 |   22.2 |     0.8  |    -42.5 |    3.32 |
| nasdaq10/top10/equal/full/SA      |    18.2 |   22.2 |     0.82 |    -42.5 |    3.52 |
| nasdaq10/top5/equal/drift_band/SA |    18.3 |   23.5 |     0.78 |    -58.2 |    3.6  |
| nasdaq10/top3/equal/drift_band/M  |    18.7 |   23.6 |     0.79 |    -57.3 |    3.82 |
| nasdaq10/top5/equal/full/SA       |    18.8 |   24   |     0.78 |    -58.1 |    3.9  |

## D. Overfitting check (train 2006-2017 -> test 2018-2026)

- **Best config on TRAIN by CAGR:** `nasdaq10/top3/equal/full/SA` (train 16.4%). Out-of-sample it did **21.7%** on TEST, ranking **#129 of 264** there.
- **Best config on TRAIN by Sharpe:** `nasdaq10/top10/equal/full/A` (train Sharpe 0.72). Out-of-sample Sharpe **0.95**, ranking **#51 of 264** on TEST.
- **Train->test correlation across all configs:** CAGR Pearson 0.59, Spearman 0.54; Sharpe Pearson 0.37.
- Read: a high correlation means the ranking is stable (structure, not luck); a low/negative one means the 'winner' is curve-fit and should not be trusted forward.


## How to read / caveats

- **In-sample optima overfit.** The section-A/B 'winners' are the best fit to one 20-year path, not a promise. Section D is the reality check.

- **No tax here.** More-frequent intervals (monthly) and full-mode trimming look better pre-tax than they would after capital-gains tax. Re-run the short list with `--tax-long/--tax-short` before committing.

- **Concentration cuts both ways.** top_1/top_3 can post the highest CAGR and the worst drawdowns; that's why risk is reported alongside.

- Membership is curated annual snapshots (see docs/VISION.md); global10 pre-2015 is the priceable subset only.


Artifacts: `output/sweep_results.csv` (full matrix), `sweep_pareto.png`, `sweep_train_test.png`.
