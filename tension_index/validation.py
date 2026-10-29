"""Correlation and lead/lag analysis of a daily series against the daily GPR."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _clean_pair(x: pd.Series, y: pd.Series) -> pd.DataFrame:
    df = pd.concat({"x": x, "y": y}, axis=1).dropna()
    return df


def corr_by_frequency(x: pd.Series, y: pd.Series, log: bool = False) -> pd.DataFrame:
    """Pearson and Spearman correlation at daily, weekly and monthly frequency.

    Weekly and monthly values are means of the daily values (GPR's own monthly
    index is likewise an average of daily article shares).
    """
    df = _clean_pair(x, y)
    if log:
        df = np.log(df.where(df > 0)).dropna()
    rows = []
    for freq, rule in [("daily", None), ("weekly", "W-SUN"), ("monthly", "MS")]:
        d = df if rule is None else df.resample(rule).mean().dropna()
        rows.append({
            "frequency": freq,
            "n": len(d),
            "pearson": d["x"].corr(d["y"]),
            "spearman": d["x"].corr(d["y"], method="spearman"),
        })
    return pd.DataFrame(rows).set_index("frequency")


def cross_correlation(x: pd.Series, y: pd.Series, max_lag: int = 15, transform: str = "level") -> pd.DataFrame:
    """corr(x_t, y_{t+k}) for k in [-max_lag, max_lag].

    k > 0: x at t correlates with y k days LATER, i.e. x LEADS y by k days.
    k < 0: x LAGS y.

    ``transform``: "level", "log", "diff" (first difference of logs) or
    "detrend" (log deviation from a trailing 30-day mean).
    """
    df = _clean_pair(x, y)
    if transform in ("log", "diff", "detrend"):
        df = np.log(df.where(df > 0)).dropna()
    if transform == "diff":
        df = df.diff().dropna()
    elif transform == "detrend":
        df = (df - df.rolling(30, min_periods=20).mean()).dropna()
    rows = []
    for k in range(-max_lag, max_lag + 1):
        r = df["x"].corr(df["y"].shift(-k))
        rows.append({"lag": k, "corr": r})
    out = pd.DataFrame(rows).set_index("lag")
    return out


def lead_lag_summary(xc: pd.DataFrame) -> dict:
    best = int(xc["corr"].idxmax())
    r0 = float(xc.loc[0, "corr"])
    rb = float(xc.loc[best, "corr"])
    # Treat a neighbouring lag as "matching" unless it beats lag 0 by a clear margin.
    if best == 0 or (rb - r0) < 0.01:
        verdict = "matches"
    elif best > 0:
        verdict = f"leads by {best} day(s)"
    else:
        verdict = f"lags by {-best} day(s)"
    return {"best_lag": best, "corr_at_best": rb, "corr_at_0": r0, "verdict": verdict}


def granger_style_lead(x: pd.Series, y: pd.Series, lags: int = 5) -> dict:
    """A simple predictive-content check on daily log changes: does adding
    x's lags improve a regression of y on its own lags (and vice versa)?
    Returns the incremental R^2 in each direction."""
    df = _clean_pair(x, y)
    df = np.log(df.where(df > 0)).dropna().diff().dropna()

    def inc_r2(target: str, other: str) -> float:
        cols = {f"{target}_l{i}": df[target].shift(i) for i in range(1, lags + 1)}
        cols.update({f"{other}_l{i}": df[other].shift(i) for i in range(1, lags + 1)})
        X = pd.DataFrame(cols).dropna()
        yv = df[target].loc[X.index].to_numpy()
        own = X[[c for c in X.columns if c.startswith(target)]].to_numpy()
        both = X.to_numpy()

        def r2(M):
            M1 = np.column_stack([np.ones(len(M)), M])
            beta, *_ = np.linalg.lstsq(M1, yv, rcond=None)
            resid = yv - M1 @ beta
            return 1 - resid.var() / yv.var()

        return r2(both) - r2(own)

    return {"x_helps_predict_y": inc_r2("y", "x"), "y_helps_predict_x": inc_r2("x", "y")}
