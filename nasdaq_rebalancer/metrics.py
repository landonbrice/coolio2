"""Performance statistics computed from a daily equity curve (value, base 1.0)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class Stats:
    total_return: float      # e.g. 4.2 == +320%
    multiple: float          # ending value / starting value (e.g. 5.2x)
    cagr: float
    vol: float               # annualized
    sharpe: float            # rf assumed 0 unless provided
    max_drawdown: float      # negative number, e.g. -0.55
    years: float


def _years(equity: pd.Series) -> float:
    days = (equity.index[-1] - equity.index[0]).days
    return max(days / 365.25, 1e-9)


def compute(equity: pd.Series, rf: float = 0.0) -> Stats:
    equity = equity.dropna()
    rets = equity.pct_change().dropna()
    yrs = _years(equity)
    multiple = float(equity.iloc[-1] / equity.iloc[0])
    cagr = multiple ** (1.0 / yrs) - 1.0
    vol = float(rets.std() * np.sqrt(TRADING_DAYS))
    sharpe = (cagr - rf) / vol if vol > 0 else float("nan")
    roll_max = equity.cummax()
    dd = (equity / roll_max - 1.0).min()
    return Stats(
        total_return=multiple - 1.0,
        multiple=multiple,
        cagr=cagr,
        vol=vol,
        sharpe=float(sharpe),
        max_drawdown=float(dd),
        years=yrs,
    )


def align(*series: pd.Series) -> list:
    """Trim a set of equity curves to their common date span and re-base to 1.0."""
    common = None
    for s in series:
        idx = s.dropna().index
        common = idx if common is None else common.intersection(idx)
    out = []
    for s in series:
        a = s.reindex(common).ffill().dropna()
        out.append(a / a.iloc[0])
    return out
