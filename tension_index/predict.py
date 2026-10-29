"""Small, dependency-free tools for the predictive tests in scripts/gold_test.py:
OLS with Newey-West (HAC) standard errors, out-of-sample loss comparisons,
and an event-driven trading rule."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from math import erf, sqrt


def _norm_sf(z: float) -> float:
    return 0.5 * (1 - erf(z / sqrt(2)))


@dataclass
class OLSResult:
    names: list[str]
    beta: np.ndarray
    se: np.ndarray
    n: int
    r2: float

    @property
    def t(self) -> np.ndarray:
        return self.beta / self.se

    @property
    def p(self) -> np.ndarray:
        return np.array([2 * _norm_sf(abs(t)) for t in self.t])

    def predict(self, X: pd.DataFrame) -> pd.Series:
        M = np.column_stack([np.ones(len(X))] + [X[c].to_numpy() for c in self.names[1:]])
        return pd.Series(M @ self.beta, index=X.index)

    def table(self) -> pd.DataFrame:
        return pd.DataFrame({"coef": self.beta, "se_hac": self.se, "t": self.t, "p": self.p},
                            index=self.names)


def newey_west_cov(X: np.ndarray, u: np.ndarray, lags: int) -> np.ndarray:
    """HAC covariance of OLS coefficients with Bartlett weights."""
    n = len(u)
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = Xu[L:].T @ Xu[:-L]
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    return XtX_inv @ S @ XtX_inv


def ols_hac(y: pd.Series, X: pd.DataFrame, lags: int) -> OLSResult:
    df = pd.concat([y.rename("_y"), X], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    yv = df["_y"].to_numpy()
    M = np.column_stack([np.ones(len(df))] + [df[c].to_numpy() for c in X.columns])
    beta, *_ = np.linalg.lstsq(M, yv, rcond=None)
    u = yv - M @ beta
    cov = newey_west_cov(M, u, lags)
    r2 = 1 - u.var() / yv.var()
    return OLSResult(["const"] + list(X.columns), beta, np.sqrt(np.diag(cov)), len(df), r2)


def dm_test(e_a: np.ndarray, e_b: np.ndarray, lags: int) -> tuple[float, float]:
    """Diebold-Mariano test on squared-error loss, H0: equal accuracy.
    Returns (statistic, two-sided p).  Positive statistic = model b is better."""
    d = e_a ** 2 - e_b ** 2
    n = len(d)
    dc = d - d.mean()
    lrv = dc @ dc / n
    for L in range(1, lags + 1):
        lrv += 2 * (1 - L / (lags + 1)) * (dc[L:] @ dc[:-L]) / n
    if lrv <= 0:
        return float("nan"), float("nan")
    stat = d.mean() / np.sqrt(lrv / n)
    return float(stat), float(2 * _norm_sf(abs(stat)))


def hit_rate(pred: np.ndarray, actual: np.ndarray) -> float:
    m = (pred != 0) & (actual != 0)
    return float((np.sign(pred[m]) == np.sign(actual[m])).mean())


def event_trades(prices: pd.Series, signal: pd.Series, hold: int, delay: int = 0,
                 cost: float = 0.001) -> pd.DataFrame:
    """Long-only trades: on each day with ``signal`` True, buy at the close
    ``delay`` trading days later and sell ``hold`` trading days after entry.
    Signals that arrive while a trade is open are ignored (no stacking).
    ``cost`` is the round-trip cost deducted from each trade's return."""
    px = prices.dropna()
    idx = px.index
    pos = {d: i for i, d in enumerate(idx)}
    trades, busy_until = [], -1
    for d in signal.index[signal.fillna(False).to_numpy(dtype=bool)]:
        if d not in pos:
            continue
        i_entry = pos[d] + delay
        i_exit = i_entry + hold
        if i_entry <= busy_until or i_exit >= len(idx):
            continue
        gross = px.iloc[i_exit] / px.iloc[i_entry] - 1
        trades.append({"signal_date": d, "entry": idx[i_entry], "exit": idx[i_exit],
                       "gross": gross, "net": gross - cost})
        busy_until = i_exit
    return pd.DataFrame(trades)


def random_entry_pvalue(prices: pd.Series, n_trades: int, hold: int, observed_mean: float,
                        period: tuple[str, str], cost: float = 0.001, n_draws: int = 5000,
                        seed: int = 0) -> float:
    """Share of random draws (same number of trades, random entry days inside
    ``period``) whose mean net return is at least the observed mean."""
    px = prices.dropna()
    r = (px.shift(-hold) / px - 1 - cost).loc[period[0]:period[1]].dropna().to_numpy()
    if n_trades == 0 or len(r) == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    draws = rng.choice(r, size=(n_draws, n_trades), replace=True).mean(axis=1)
    return float((draws >= observed_mean).mean())
