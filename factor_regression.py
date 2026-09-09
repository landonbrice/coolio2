#!/usr/bin/env python3
"""
factor_regression.py -- the DECISIVE alpha-vs-beta cut on the top-10 strategy.

QUESTION UNDER TEST
-------------------
Is the top-10 edge over QQQ real *skill* (alpha) or just a *leveraged dose of the
same factor* (high beta to QQQ / the market + a momentum tilt)?

HYPOTHESIS (the skeptic's prior): the edge is mostly beta, i.e.
    alpha ~ 0,  QQQ beta > 1,  positive momentum loading.
If alpha is large and statistically significant *after* controlling for QQQ (and
for Mkt-RF/SMB/HML/Mom), that would refute the skeptic and point to real edge.

WHAT THIS DOES
--------------
1. Reruns the TUNED BASELINE strategy (nasdaq10 / capweight / top10 / full / Q,
   5 bps cost) via backtest.run_backtest, reusing the existing engine + cached
   price panel. Converts the daily equity curve to MONTHLY returns.
2. SINGLE-FACTOR (numpy only, always runs): regress strategy monthly EXCESS
   returns on QQQ monthly EXCESS returns. Reports alpha (annualized %), beta,
   R^2, and the alpha t-stat with Newey-West (HAC) standard errors (falls back to
   plain OLS SEs, which are also reported).
3. MULTI-FACTOR (best-effort): fetch Ken French Mkt-RF/SMB/HML/RF + Momentum from
   the Dartmouth data library, parse the monthly factors, and regress strategy
   excess returns on Mkt-RF, SMB, HML, Mom (and a variant that adds QQQ
   orthogonalized to the FF factors). If the fetch/parse fails, ff_done=False and
   we drop a dated note to the exhaust zone.

Output: output/factor_regression.json + a clean printed summary.

Research / not financial advice.
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
import datetime as dt
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request

import numpy as np
import pandas as pd

from nasdaq_rebalancer import backtest, constituents, prices as price_mod

# ---- Tuned baseline (the headline strategy; see docs/RESULTS.md & dashboard) ----
UNIVERSE = "nasdaq10"
WEIGHTING = "capweight"
TOP_N = 10
MODE = "full"
INTERVAL = "Q"
COST_BPS = 5.0
START = "2006-01-01"
END = dt.date.today().isoformat()

OUTPUT_DIR = os.environ.get("REBAL_OUTPUT_DIR", "output")
DROPZONE_DIR = os.path.join(OUTPUT_DIR, "dropzone")
DROP_LABEL = "factor_regression"

FF_FACTORS_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_CSV.zip"
)
FF_MOM_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Momentum_Factor_CSV.zip"
)


# --------------------------------------------------------------------------- #
# drop-zone note (feeds the exhaust-mining agent)                             #
# --------------------------------------------------------------------------- #
def drop_note(what: str, why: str) -> None:
    os.makedirs(DROPZONE_DIR, exist_ok=True)
    path = os.path.join(DROPZONE_DIR, f"{DROP_LABEL}.md")
    stamp = dt.date.today().isoformat()
    with open(path, "a") as f:
        f.write(f"\n## {stamp} -- {what}\n\n{why}\n")
    print(f"[dropzone] noted: {what} -> {path}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# OLS with plain + Newey-West (HAC) standard errors -- pure numpy             #
# --------------------------------------------------------------------------- #
def ols_hac(y: np.ndarray, X: np.ndarray, lags: int = 6) -> Dict:
    """OLS of y on X (X must already include an intercept column).

    Returns betas, plain-OLS SEs/t-stats, Newey-West HAC SEs/t-stats, R^2.
    """
    n, k = X.shape
    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof

    # plain OLS covariance
    cov_ols = sigma2 * XtX_inv
    se_ols = np.sqrt(np.diag(cov_ols))

    # Newey-West HAC covariance (Bartlett kernel)
    # S = sum_t u_t u_t' x_t x_t' with lag weights
    Xu = X * resid[:, None]            # (n x k) score contributions
    S = Xu.T @ Xu                      # lag 0
    for L in range(1, lags + 1):
        w = 1.0 - L / (lags + 1.0)
        Gamma = Xu[L:].T @ Xu[:-L]
        S += w * (Gamma + Gamma.T)
    cov_hac = XtX_inv @ S @ XtX_inv
    se_hac = np.sqrt(np.diag(cov_hac))

    # R^2
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    r2_adj = 1.0 - (1.0 - r2) * (n - 1) / dof if ss_tot > 0 else float("nan")

    with np.errstate(divide="ignore", invalid="ignore"):
        t_ols = beta / se_ols
        t_hac = beta / se_hac

    return {
        "beta": beta,
        "se_ols": se_ols,
        "t_ols": t_ols,
        "se_hac": se_hac,
        "t_hac": t_hac,
        "r2": r2,
        "r2_adj": r2_adj,
        "n": n,
        "k": k,
        "lags": lags,
    }


def annualize_monthly_alpha(monthly_alpha: float) -> float:
    """Monthly intercept (decimal) -> annualized % via compounding."""
    return ((1.0 + monthly_alpha) ** 12 - 1.0) * 100.0


# --------------------------------------------------------------------------- #
# strategy + QQQ monthly returns                                             #
# --------------------------------------------------------------------------- #
def to_monthly_returns(equity: pd.Series) -> pd.Series:
    """Daily equity (base 1.0) -> calendar month-end simple returns."""
    monthly_level = equity.resample("ME").last()
    return monthly_level.pct_change().dropna()


def build_strategy_and_qqq() -> Tuple[pd.Series, pd.Series, pd.DataFrame]:
    needed = sorted(set(constituents.all_tickers(UNIVERSE)))
    panel = price_mod.get_price_panel(needed, START, END, use_cache=True)
    res = backtest.run_backtest(
        UNIVERSE, panel, START, END,
        weighting=WEIGHTING, cost_bps=COST_BPS, mode=MODE,
        interval=INTERVAL, top_n=TOP_N,
    )
    strat_m = to_monthly_returns(res.equity)

    qqq = price_mod.get_series("QQQ", START, END, use_cache=True)
    qqq_m = to_monthly_returns(qqq)

    df = pd.DataFrame({"strat": strat_m, "qqq": qqq_m}).dropna()
    return res.equity, qqq, df


# --------------------------------------------------------------------------- #
# Ken French factor fetch + parse                                            #
# --------------------------------------------------------------------------- #
def _fetch_zip_csv(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (factor-regression)"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = zf.namelist()[0]
    return zf.read(name).decode("latin-1")


def _parse_ff_monthly(text: str, value_cols: List[str]) -> pd.DataFrame:
    """Parse a Ken French monthly CSV block (lines like 'YYYYMM, a, b, ...').

    Stops at the first blank line / annual section. Values are in PERCENT in the
    file; we convert to decimals.
    """
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if rows:
                break  # reached end of the monthly block
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) < 2:
            continue
        token = parts[0]
        if len(token) == 6 and token.isdigit():  # YYYYMM monthly row
            try:
                vals = [float(x) for x in parts[1:]]
            except ValueError:
                continue
            rows.append((token, vals))
    if not rows:
        raise ValueError("no monthly rows parsed")
    ncols = min(len(value_cols), min(len(v) for _, v in rows))
    idx = pd.PeriodIndex([r[0] for r in rows], freq="M")
    data = {value_cols[i]: [r[1][i] for r in rows] for i in range(ncols)}
    df = pd.DataFrame(data, index=idx) / 100.0  # percent -> decimal
    return df


def fetch_french_factors() -> pd.DataFrame:
    """Monthly Mkt-RF, SMB, HML, RF, Mom as decimals, indexed by month period."""
    fac_txt = _fetch_zip_csv(FF_FACTORS_URL)
    fac = _parse_ff_monthly(fac_txt, ["Mkt-RF", "SMB", "HML", "RF"])
    mom_txt = _fetch_zip_csv(FF_MOM_URL)
    mom = _parse_ff_monthly(mom_txt, ["Mom"])
    out = fac.join(mom, how="inner")
    out = out.dropna()
    if out.empty:
        raise ValueError("empty factor frame after join")
    return out


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Window: {START} -> {END}")
    print(f"Strategy (tuned baseline): {UNIVERSE}/{WEIGHTING}/top{TOP_N}/"
          f"{MODE}/{INTERVAL}, {COST_BPS}bps cost\n")

    strat_equity, qqq_level, df = build_strategy_and_qqq()
    print(f"Monthly observations (strategy & QQQ overlap): {len(df)}  "
          f"({df.index[0].date()} -> {df.index[-1].date()})\n")

    result: Dict = {
        "meta": {
            "generated": dt.datetime.utcnow().isoformat() + "Z",
            "window": {"start": START, "end": END},
            "strategy_config": {
                "universe": UNIVERSE, "weighting": WEIGHTING, "top_n": TOP_N,
                "mode": MODE, "interval": INTERVAL, "cost_bps": COST_BPS,
            },
            "n_months": int(len(df)),
            "month_range": [str(df.index[0].date()), str(df.index[-1].date())],
            "hypothesis": (
                "Top-10 edge over QQQ is a leveraged dose of the same factor "
                "(alpha~0, QQQ beta>1, +momentum), NOT skill/alpha."
            ),
        }
    }

    # ----- attach risk-free from FF if we can; else 0 ----------------------- #
    ff: Optional[pd.DataFrame] = None
    ff_err = None
    try:
        ff = fetch_french_factors()
        print(f"[ff] fetched Ken French factors: {ff.index[0]} -> {ff.index[-1]} "
              f"({len(ff)} months)\n")
    except Exception as exc:  # noqa: BLE001
        ff_err = f"{type(exc).__name__}: {exc}"
        print(f"[ff] FAILED to fetch/parse Ken French factors: {ff_err}\n",
              file=sys.stderr)

    # monthly rf series aligned to df (period index), default 0
    df_p = df.copy()
    df_p.index = df_p.index.to_period("M")
    rf = pd.Series(0.0, index=df_p.index)
    rf_source = "zero (FF unavailable)"
    if ff is not None:
        rf_aligned = ff["RF"].reindex(df_p.index)
        if rf_aligned.notna().sum() >= 0.8 * len(df_p):
            rf = rf_aligned.fillna(0.0)
            rf_source = "Ken French RF"

    # ----- SINGLE-FACTOR: strat_excess ~ a + b * qqq_excess ----------------- #
    strat_ex = (df_p["strat"] - rf).values
    qqq_ex = (df_p["qqq"] - rf).values
    X1 = np.column_stack([np.ones_like(qqq_ex), qqq_ex])
    sf = ols_hac(strat_ex, X1, lags=6)

    alpha_m = float(sf["beta"][0])
    beta_q = float(sf["beta"][1])
    alpha_ann = annualize_monthly_alpha(alpha_m)
    alpha_t_hac = float(sf["t_hac"][0])
    alpha_t_ols = float(sf["t_ols"][0])

    result["single_factor"] = {
        "model": "strat_excess ~ alpha + beta * QQQ_excess",
        "rf_source": rf_source,
        "alpha_monthly": alpha_m,
        "alpha_annual_pct": alpha_ann,
        "alpha_se_ols_monthly": float(sf["se_ols"][0]),
        "alpha_se_hac_monthly": float(sf["se_hac"][0]),
        "alpha_t_ols": alpha_t_ols,
        "alpha_t_hac": alpha_t_hac,
        "beta_qqq": beta_q,
        "beta_qqq_se_hac": float(sf["se_hac"][1]),
        "beta_qqq_t_hac": float(sf["t_hac"][1]),
        "r2": float(sf["r2"]),
        "r2_adj": float(sf["r2_adj"]),
        "n_months": int(sf["n"]),
        "hac_lags": int(sf["lags"]),
    }

    print("=== SINGLE-FACTOR: strategy excess vs QQQ excess ===")
    print(f"  alpha  = {alpha_m*100:+.3f}%/mo  ->  {alpha_ann:+.2f}%/yr "
          f"(t_HAC={alpha_t_hac:+.2f}, t_OLS={alpha_t_ols:+.2f})")
    print(f"  beta   = {beta_q:.3f}  (t_HAC={float(sf['t_hac'][1]):.2f})")
    print(f"  R^2    = {sf['r2']:.3f}   (n={sf['n']} months, rf={rf_source})\n")

    # ----- MULTI-FACTOR: FF3 + Mom (+ QQQ orthogonalized) ------------------- #
    ff_done = False
    if ff is not None:
        try:
            common = df_p.index.intersection(ff.index)
            if len(common) < 24:
                raise ValueError(f"too few overlapping months ({len(common)})")
            d = df_p.loc[common]
            f = ff.loc[common]
            y = (d["strat"] - f["RF"]).values
            mkt = f["Mkt-RF"].values
            smb = f["SMB"].values
            hml = f["HML"].values
            mom = f["Mom"].values

            # FF4 (Carhart): Mkt-RF, SMB, HML, Mom
            X4 = np.column_stack([np.ones_like(mkt), mkt, smb, hml, mom])
            mf = ols_hac(y, X4, lags=6)
            names4 = ["alpha", "Mkt-RF", "SMB", "HML", "Mom"]

            # FF4 + QQQ orthogonalized to the four factors (extra mkt-tech tilt)
            qqq_ex_c = (d["qqq"] - f["RF"]).values
            # regress qqq_ex on the 4 factors, take residual
            qb = np.linalg.lstsq(X4, qqq_ex_c, rcond=None)[0]
            qqq_orth = qqq_ex_c - X4 @ qb
            X5 = np.column_stack([X4, qqq_orth])
            mf5 = ols_hac(y, X5, lags=6)
            names5 = names4 + ["QQQ_orth"]

            loadings4 = {names4[i]: float(mf["beta"][i]) for i in range(len(names4))}
            t4 = {names4[i]: float(mf["t_hac"][i]) for i in range(len(names4))}
            loadings5 = {names5[i]: float(mf5["beta"][i]) for i in range(len(names5))}
            t5 = {names5[i]: float(mf5["t_hac"][i]) for i in range(len(names5))}

            result["multi_factor"] = {
                "model_ff4": "strat_excess ~ alpha + Mkt-RF + SMB + HML + Mom",
                "n_months": int(mf["n"]),
                "month_range": [str(common[0]), str(common[-1])],
                "hac_lags": int(mf["lags"]),
                "ff4": {
                    "alpha_monthly": float(mf["beta"][0]),
                    "alpha_annual_pct": annualize_monthly_alpha(float(mf["beta"][0])),
                    "alpha_t_hac": float(mf["t_hac"][0]),
                    "loadings": loadings4,
                    "t_hac": t4,
                    "r2": float(mf["r2"]),
                    "r2_adj": float(mf["r2_adj"]),
                },
                "ff4_plus_qqq_orth": {
                    "alpha_monthly": float(mf5["beta"][0]),
                    "alpha_annual_pct": annualize_monthly_alpha(float(mf5["beta"][0])),
                    "alpha_t_hac": float(mf5["t_hac"][0]),
                    "loadings": loadings5,
                    "t_hac": t5,
                    "r2": float(mf5["r2"]),
                    "r2_adj": float(mf5["r2_adj"]),
                },
            }
            ff_done = True

            print("=== MULTI-FACTOR: FF3 + Momentum (Carhart 4) ===")
            a4 = float(mf["beta"][0])
            print(f"  alpha  = {a4*100:+.3f}%/mo  ->  "
                  f"{annualize_monthly_alpha(a4):+.2f}%/yr "
                  f"(t_HAC={float(mf['t_hac'][0]):+.2f})")
            for nm in names4[1:]:
                print(f"  {nm:8s}= {loadings4[nm]:+.3f}  (t_HAC={t4[nm]:+.2f})")
            print(f"  R^2    = {mf['r2']:.3f}   (n={mf['n']} months)\n")

            print("=== MULTI-FACTOR + QQQ(orthogonalized) ===")
            a5 = float(mf5["beta"][0])
            print(f"  alpha  = {a5*100:+.3f}%/mo  ->  "
                  f"{annualize_monthly_alpha(a5):+.2f}%/yr "
                  f"(t_HAC={float(mf5['t_hac'][0]):+.2f})")
            for nm in names5[1:]:
                print(f"  {nm:8s}= {loadings5[nm]:+.3f}  (t_HAC={t5[nm]:+.2f})")
            print(f"  R^2    = {mf5['r2']:.3f}\n")

        except Exception as exc:  # noqa: BLE001
            ff_err = f"multi-factor regression failed: {type(exc).__name__}: {exc}"
            print(f"[ff] {ff_err}", file=sys.stderr)
            ff_done = False

    result["ff_done"] = ff_done
    if not ff_done:
        result["ff_error"] = ff_err
        drop_note(
            what="Ken French multi-factor regression skipped",
            why=(f"ff_done=false. Reason: {ff_err}. Single-factor QQQ regression "
                 f"still ran (numpy-only) and is the primary alpha-vs-beta cut. "
                 f"Multi-factor (Mkt-RF/SMB/HML/Mom) needs the Dartmouth download "
                 f"to succeed; retry on a network that can reach "
                 f"mba.tuck.dartmouth.edu."),
        )

    # ----- VERDICT --------------------------------------------------------- #
    # Decision rule: "real alpha" if single-factor alpha is positive AND
    # statistically significant (|t_HAC|>=2) AND (if FF available) FF4 alpha also
    # holds up. "mostly beta" if alpha small/insignificant and beta>1. else mixed.
    sig = abs(alpha_t_hac) >= 2.0
    beta_gt1 = beta_q > 1.0
    ff4_sig = None
    if ff_done:
        ff4_t = result["multi_factor"]["ff4"]["alpha_t_hac"]
        ff4_a = result["multi_factor"]["ff4"]["alpha_annual_pct"]
        ff4_sig = (abs(ff4_t) >= 2.0) and (ff4_a > 0)

    if sig and alpha_ann > 0 and (ff4_sig is None or ff4_sig):
        verdict = "real alpha"
    elif (not sig or alpha_ann <= 0) and beta_gt1:
        verdict = "mostly beta"
    else:
        verdict = "mixed"

    hypo_confirmed = (verdict == "mostly beta")
    result["verdict"] = {
        "verdict": verdict,
        "hypothesis_confirmed": hypo_confirmed,
        "alpha_significant_hac": bool(sig),
        "beta_gt_1": bool(beta_gt1),
        "ff4_alpha_significant": ff4_sig,
    }

    out_path = os.path.join(OUTPUT_DIR, "factor_regression.json")
    with open(out_path, "w") as fp:
        json.dump(result, fp, indent=2)

    print("=== VERDICT ===")
    print(f"  {verdict.upper()}  (hypothesis 'mostly beta' "
          f"{'CONFIRMED' if hypo_confirmed else 'REFUTED'})")
    print(f"  single-factor: alpha {alpha_ann:+.2f}%/yr, "
          f"beta {beta_q:.2f}, R^2 {sf['r2']:.2f}, "
          f"alpha t_HAC {alpha_t_hac:+.2f}")
    if ff_done:
        print(f"  FF4: alpha {result['multi_factor']['ff4']['alpha_annual_pct']:+.2f}%/yr "
              f"(t_HAC {result['multi_factor']['ff4']['alpha_t_hac']:+.2f}), "
              f"Mom loading {result['multi_factor']['ff4']['loadings']['Mom']:+.3f}")
    else:
        print("  FF4: not available (ff_done=false)")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
