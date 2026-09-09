"""
Price data layer: download split/dividend-adjusted daily closes from Yahoo via
yfinance, convert non-USD names to USD, cache to disk, and degrade gracefully
when a ticker has no usable history.

Design choices (deliberately minimal Yahoo surface area, because this code is
meant to run on YOUR machine where it can reach Yahoo, and we want the most
battle-tested yfinance path):

  * We only ever call `yfinance.download(..., auto_adjust=True)`. Auto-adjusted
    close already folds in dividends *and* splits, which makes it a clean
    total-return proxy (dividends reinvested) -- exactly what the strategy needs.
  * Foreign listings priced in a non-USD currency are converted with a Yahoo FX
    series (e.g. "HKDUSD=X") so the whole portfolio is measured in USD.
  * Any ticker that fails to download (delisted ADRs, bad symbols) is dropped
    with a warning. The backtest renormalizes weights over whatever it can price.
  * Everything is cached to parquet so re-runs are instant and offline.
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Iterable, List

import pandas as pd

from . import constituents

CACHE_DIR = os.environ.get("REBAL_CACHE_DIR", "data_cache")


def _log(msg: str) -> None:
    print(f"[prices] {msg}", file=sys.stderr)


def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = key.replace("/", "_").replace("=", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe}.parquet")


def _download_raw(tickers: List[str], start: str, end: str) -> pd.DataFrame:
    """Adjusted-close panel (columns=tickers) straight from Yahoo, no FX yet."""
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    # With multiple tickers yfinance returns a column MultiIndex; with one ticker
    # it returns flat columns. Normalize to a (date x ticker) close panel.
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = [tickers[0]]
    close.index = pd.to_datetime(close.index)
    return close


def _fx_to_usd(currency: str, start: str, end: str) -> pd.Series:
    """Daily multiplier that converts `currency` into USD (USD per 1 unit)."""
    if currency == "USD":
        raise ValueError("USD needs no conversion")
    # Yahoo quotes e.g. "HKDUSD=X" as USD per 1 HKD -- exactly the multiplier we want.
    pair = f"{currency}USD=X"
    fx = _download_raw([pair], start, end)
    if fx.empty:
        raise RuntimeError(f"no FX data for {pair}")
    series = fx.iloc[:, 0].astype(float)
    return series.ffill()


def get_price_panel(
    tickers: Iterable[str],
    start: str,
    end: str,
    use_cache: bool = True,
) -> pd.DataFrame:
    """USD-denominated, adjusted daily close panel for `tickers`.

    Returns a DataFrame indexed by date with one column per ticker that had
    usable data. Tickers with no data are omitted (and reported).
    """
    tickers = list(dict.fromkeys(tickers))  # de-dupe, keep order
    cache_key = f"panel_{start}_{end}_{'-'.join(sorted(tickers))[:80]}_{len(tickers)}"
    cache_file = _cache_path(cache_key)
    if use_cache and os.path.exists(cache_file):
        _log(f"loading cached price panel ({len(tickers)} tickers requested)")
        return pd.read_parquet(cache_file)

    # Split USD vs non-USD; download USD names in one shot, others individually
    # so a single bad foreign symbol can't poison the batch.
    usd = [t for t in tickers if constituents.currency_of(t) == "USD"]
    foreign = [t for t in tickers if constituents.currency_of(t) != "USD"]

    cols = {}
    if usd:
        _log(f"downloading {len(usd)} USD tickers...")
        panel = _download_raw(usd, start, end)
        for t in usd:
            if t in panel.columns and panel[t].notna().any():
                cols[t] = panel[t].astype(float)
            else:
                _log(f"  WARNING: no data for {t} -- dropping")

    for t in foreign:
        ccy = constituents.currency_of(t)
        _log(f"downloading foreign ticker {t} ({ccy}) + FX...")
        local = _download_raw([t], start, end)
        if local.empty or local.iloc[:, 0].notna().sum() == 0:
            _log(f"  WARNING: no data for {t} -- dropping")
            continue
        local_series = local.iloc[:, 0].astype(float)
        try:
            fx = _fx_to_usd(ccy, start, end)
            usd_series = (local_series * fx.reindex(local_series.index).ffill()).dropna()
            if usd_series.empty:
                raise RuntimeError("empty after FX align")
            cols[t] = usd_series
        except Exception as exc:  # noqa: BLE001 - we want to never crash the run
            _log(f"  WARNING: FX conversion failed for {t} ({exc}) -- dropping")

    if not cols:
        raise RuntimeError(
            "No price data could be downloaded for any ticker. Are you offline, "
            "or is Yahoo blocked by a network policy? (This sandbox blocks Yahoo; "
            "run on your own machine.)"
        )

    result = pd.DataFrame(cols).sort_index()
    result = result.ffill()  # carry last price over non-trading gaps
    if use_cache:
        result.to_parquet(cache_file)
        _log(f"cached price panel to {cache_file}")
    return result


def get_series(ticker: str, start: str, end: str, use_cache: bool = True) -> pd.Series:
    """USD adjusted-close series for a single ticker (used for benchmarks)."""
    panel = get_price_panel([ticker], start, end, use_cache=use_cache)
    if ticker not in panel.columns:
        raise RuntimeError(f"no data for {ticker}")
    return panel[ticker].dropna()
