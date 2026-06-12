"""
Deeper analytics on top of equity curves: per-calendar-year returns, rolling
multi-year CAGR, benchmark-relative risk (beta / tracking error / information
ratio), and a robustness grid that sweeps universes x weightings x start dates so
the headline result can't hide behind one lucky parameter set.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from . import backtest, benchmark, constituents, metrics


def calendar_year_returns(equity: pd.Series) -> pd.Series:
    """Return for each calendar year (within-year first->last day)."""
    eq = equity.dropna()
    return eq.groupby(eq.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1.0)


def rolling_cagr(equity: pd.Series, window_years: int = 3) -> pd.Series:
    """Annualized return over a trailing window, sampled daily."""
    eq = equity.dropna()
    win = int(round(window_years * metrics.TRADING_DAYS))
    if len(eq) <= win:
        return pd.Series(dtype=float)
    ratio = eq / eq.shift(win)
    return ratio.dropna() ** (1.0 / window_years) - 1.0


def benchmark_relative(strategy: pd.Series, bench: pd.Series) -> Dict[str, float]:
    """Beta, tracking error (annualized), and information ratio vs a benchmark."""
    s, b = metrics.align(strategy, bench)
    rs, rb = s.pct_change().dropna(), b.pct_change().dropna()
    common = rs.index.intersection(rb.index)
    rs, rb = rs.loc[common], rb.loc[common]
    var_b = float(rb.var())
    beta = float(np.cov(rs, rb)[0, 1] / var_b) if var_b > 0 else float("nan")
    active = rs - rb
    te = float(active.std() * np.sqrt(metrics.TRADING_DAYS))
    st_s, st_b = metrics.compute(s), metrics.compute(b)
    info_ratio = (st_s.cagr - st_b.cagr) / te if te > 0 else float("nan")
    return {"beta": beta, "tracking_error": te, "information_ratio": info_ratio}


def year_table(curves: Dict[str, pd.Series]) -> pd.DataFrame:
    """Per-calendar-year return for each labeled equity curve."""
    cols = {label: calendar_year_returns(eq) for label, eq in curves.items()}
    df = pd.DataFrame(cols)
    df.index.name = "year"
    return df


def robustness_grid(
    panel: pd.DataFrame,
    sp: pd.Series,
    universes: List[str],
    weightings: List[str],
    starts: List[str],
    end: str,
    cost_bps: float = 5.0,
) -> pd.DataFrame:
    """Sweep parameter combinations; one row per (universe, weighting, start)."""
    rows = []
    for start in starts:
        sp_stats = metrics.compute(metrics.align(sp.loc[start:end])[0])
        for u in universes:
            for w in weightings:
                res = backtest.run_backtest(u, panel, start, end,
                                            weighting=w, cost_bps=cost_bps)
                aligned_s, aligned_b = metrics.align(res.equity, sp.loc[start:end])
                st = metrics.compute(aligned_s)
                spb = metrics.compute(aligned_b)
                rows.append({
                    "start": start,
                    "universe": u,
                    "weighting": w,
                    "CAGR%": round(st.cagr * 100, 1),
                    "S&P CAGR%": round(spb.cagr * 100, 1),
                    "Multiple": round(st.multiple, 2),
                    "x vs S&P": round(st.multiple / spb.multiple, 2),
                    "MaxDD%": round(st.max_drawdown * 100, 1),
                    "Sharpe": round(st.sharpe, 2),
                })
    return pd.DataFrame(rows)
