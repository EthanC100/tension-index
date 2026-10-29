"""Turn article counts into GPR-style index values."""
from __future__ import annotations

import numpy as np
import pandas as pd

# GPR's recent daily index is scaled so that it averages 100 over 1985–2019.
# GDELT only reaches back to 2015 (and the full-text API to 2017), so the
# tension index is scaled to average 100 over the overlap-friendly base period
# below.  Shares are what matter for correlation; the base only sets the level.
BASE_START = "2017-01-01"
BASE_END = "2019-12-31"


def normalize_like_gpr(share: pd.Series, base_start: str = BASE_START, base_end: str = BASE_END) -> pd.Series:
    """Index = share / mean(share over base period) * 100, like GPR."""
    base = share.loc[base_start:base_end].dropna()
    if base.empty:
        raise ValueError("no observations in the base period; cannot normalise")
    return share / base.mean() * 100.0


def daily_shares_from_slots(slots: pd.DataFrame, min_ok_slots: int = 4) -> pd.DataFrame:
    """Aggregate per-slot raw counts to daily shares.

    ``slots`` is the CSV written by ``scripts/backfill_raw.py``.  Each day's
    share is (sum of matching records over the sampled slots) / (sum of all
    records over those slots).  Days with fewer than ``min_ok_slots`` usable
    GKG slots are left as NaN.
    """
    df = slots.copy()
    df["date"] = pd.to_datetime(df["slot"].astype(str).str[:8], format="%Y%m%d")
    gkg_ok = df[df["gkg_status"] == "ok"]
    evt_ok = df[df["evt_status"] == "ok"]
    gkg_cols = [c for c in df.columns if c.startswith("gkg_") and c != "gkg_status"]
    evt_cols = [c for c in df.columns if c.startswith("evt_") and c != "evt_status"]
    g = gkg_ok.groupby("date")[gkg_cols].sum()
    g["gkg_slots"] = gkg_ok.groupby("date").size()
    e = evt_ok.groupby("date")[evt_cols].sum()
    e["evt_slots"] = evt_ok.groupby("date").size()
    out = pd.DataFrame(index=g.index.union(e.index))
    out["gkg_slots"] = g["gkg_slots"]
    out["evt_slots"] = e["evt_slots"]
    out["gkg_total"] = g["gkg_total"]
    if "gkg_title_records" in g:
        out["gkg_title_records"] = g["gkg_title_records"]
    out["evt_total"] = e["evt_total"]
    for c in gkg_cols:
        if c in ("gkg_total", "gkg_title_records"):
            continue
        # Headline shares are relative to records that carry a headline.
        denom = g["gkg_title_records"] if c.startswith("gkg_title_") else g["gkg_total"]
        out[f"share_{c}"] = g[c] / denom.where(denom > 0)
    for c in evt_cols:
        if c in ("evt_total", "evt_mentions"):
            continue
        denom = e["evt_mentions"] if c.startswith("evt_m_") else e["evt_total"]
        out[f"share_{c}"] = e[c] / denom
    bad_g = out["gkg_slots"].fillna(0) < min_ok_slots
    out.loc[bad_g, [c for c in out.columns if c.startswith("share_gkg_")]] = np.nan
    bad_e = out["evt_slots"].fillna(0) < min_ok_slots
    out.loc[bad_e, [c for c in out.columns if c.startswith("share_evt_")]] = np.nan
    return out.sort_index()
