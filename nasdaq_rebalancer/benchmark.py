"""Benchmark equity curves (S&P 500 total return, Nasdaq, etc.)."""

from __future__ import annotations

import pandas as pd

from . import prices

# Yahoo symbols. ^SP500TR is the S&P 500 *Total Return* index (dividends
# reinvested) -- the correct apples-to-apples benchmark for this dividend-
# reinvesting strategy. SPY (also total-return via auto-adjust) is the fallback
# because ^SP500TR occasionally misbehaves in yfinance.
BENCHMARKS = {
    "sp500": ("^SP500TR", "S&P 500 (Total Return)"),
    "sp500_etf": ("SPY", "S&P 500 ETF (SPY, div. reinvested)"),
    "nasdaq100": ("QQQ", "Nasdaq-100 ETF (QQQ)"),
}


def load_benchmark(key: str, start: str, end: str, use_cache: bool = True) -> pd.Series:
    symbol, _label = BENCHMARKS[key]
    return prices.get_series(symbol, start, end, use_cache=use_cache)


def load_sp500(start: str, end: str, use_cache: bool = True) -> pd.Series:
    """S&P 500 total return, falling back to SPY if the TR index is unavailable."""
    try:
        s = prices.get_series("^SP500TR", start, end, use_cache=use_cache)
        if len(s) > 50:
            return s
    except Exception:  # noqa: BLE001
        pass
    return prices.get_series("SPY", start, end, use_cache=use_cache)
