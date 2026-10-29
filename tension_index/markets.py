"""Daily market data for the metal-price tests, fetched the way gold-events does
(EthanC100/gold-events, ``gold_events/data.py``): Yahoo Finance for COMEX
front-month gold and silver futures and the ICE dollar index, FRED for the 10y
TIPS real yield and the VIX.  (gold-events tries Stooq spot first; Stooq
refuses this environment, and gold-events' own recorded build also came from
Yahoo.)  Raw downloads are cached as CSV in ``data/markets``.
"""
from __future__ import annotations

import io
import os

import pandas as pd
import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, "data", "markets")

SERIES = {
    # name: (source, symbol, description)
    "gold": ("yahoo", "GC=F", "COMEX gold front-month futures, daily close, USD/oz"),
    "silver": ("yahoo", "SI=F", "COMEX silver front-month futures, daily close, USD/oz"),
    "dxy": ("yahoo", "DX-Y.NYB", "ICE US dollar index, daily close"),
    "real_yield": ("fred", "DFII10", "10y TIPS constant-maturity real yield, %"),
    "vix": ("fred", "VIXCLS", "CBOE VIX, daily close"),
}


def _yahoo(symbol: str) -> pd.Series:
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="max", auto_adjust=False)
    if h.empty:
        raise RuntimeError(f"Yahoo returned no data for {symbol}")
    s = h["Close"].astype(float)
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s


def _fred(symbol: str) -> pd.Series:
    text = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={symbol}", timeout=60).text
    if not text.lstrip().startswith("observation_date"):
        raise RuntimeError(f"FRED did not return CSV for {symbol}: {text[:80]!r}")
    df = pd.read_csv(io.StringIO(text), parse_dates=["observation_date"], na_values=["."])
    return df.set_index("observation_date")[symbol].astype(float)


def fetch(name: str, refresh: bool = False) -> pd.Series:
    path = os.path.join(CACHE, f"{name}.csv")
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, parse_dates=["date"]).set_index("date")["value"]
    source, symbol, _ = SERIES[name]
    s = (_yahoo if source == "yahoo" else _fred)(symbol).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    os.makedirs(CACHE, exist_ok=True)
    s.rename("value").to_csv(path, index_label="date", float_format="%.6g")
    return s


def load(start: str = "2019-01-01", refresh: bool = False) -> pd.DataFrame:
    """Aligned frame on gold's trading days.  Controls are forward-filled at
    most 3 days (FRED and Yahoo holidays differ slightly from COMEX)."""
    raw = {n: fetch(n, refresh) for n in SERIES}
    cal = raw["gold"].index[raw["gold"].index >= start]
    df = pd.DataFrame(index=cal)
    for n, s in raw.items():
        df[n] = s.reindex(s.index.union(cal)).ffill(limit=3).reindex(cal)
    df.index.name = "date"
    return df
