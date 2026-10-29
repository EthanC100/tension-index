"""Shared definitions of the three component series and the composite index.

Component series (each a daily *share* of articles):

* ``fulltext`` – GPR word lists matched against full article text via the
  GDELT DOC 2.0 API (English sources).  Closest to the GPR method; history
  from 2017-01-01.  Depends on GDELT's full-text indexing keeping up.
* ``headline`` – GPR word lists and proximity rules applied literally to the
  page titles in the raw GKG files (English sources).  History from
  2019-09; the raw files are published within the hour, so it is always
  available the next morning.
* ``theme`` – share of GKG records tagged with GDELT's own conflict, terror,
  WMD or military-buildup themes.  A weaker proxy kept because it is the
  only GDELT series that reaches back to February 2015.

Each share is turned into an index the way GPR is (share divided by its
base-period mean), then multiplied by the daily GPR's own mean over the
same base period, so that index values are on the GPR's scale.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import wordlists as W

CATS = [c[0] for c in W.CATEGORIES]
BASE_START = "2020-01-01"
BASE_END = "2024-12-31"

# component -> (share column for the overall index, threats column, acts column)
COMPONENTS = {
    "fulltext": ("ft_share_any", "ft_share_threats", "ft_share_acts"),
    "headline": ("hl_share_any", "hl_share_threats", "hl_share_acts"),
    "headline_and": ("hl_share_and", None, None),
    "headline_topic": ("hl_share_topic", None, None),
    "theme": ("th_share_gpr_like", None, None),
}

# A full-text day is usable when GDELT indexed at least 25% of the normal
# same-weekday English volume and at least 5,000 English articles.  Holidays
# (~35-60% of normal) pass; indexing outages (often <5% of normal) do not.
FT_COVERAGE_MIN = 0.25
FT_MIN_ARTICLES = 5000


def ft_ok(df: pd.DataFrame) -> pd.Series:
    return (df["ft_coverage"] >= FT_COVERAGE_MIN) & (df["ft_english_articles"] >= FT_MIN_ARTICLES)


def fulltext_shares(counts: pd.DataFrame) -> pd.DataFrame:
    """counts: wide frame (index date) with columns english_total, <cats>, union."""
    out = pd.DataFrame(index=counts.index)
    tot = counts["english_total"].where(counts["english_total"] > 0)
    out["ft_english_articles"] = counts["english_total"]
    for c in CATS:
        out[f"ft_share_{c}"] = counts[c] / tot
    out["ft_share_any"] = counts["union"] / tot if "union" in counts else np.nan
    # Threat/act sub-indexes: sum over categories (an article in two
    # categories counts twice; the union is only pulled for all eight).
    out["ft_share_threats"] = sum(out[f"ft_share_{c}"] for c in W.THREAT_CATEGORIES)
    out["ft_share_acts"] = sum(out[f"ft_share_{c}"] for c in W.ACT_CATEGORIES)
    return out


def raw_shares(daily_slots: pd.DataFrame) -> pd.DataFrame:
    """daily_slots: output of score.daily_shares_from_slots."""
    d = daily_slots
    out = pd.DataFrame(index=d.index)
    out["gkg_slots"] = d["gkg_slots"]
    out["gkg_records"] = d["gkg_total"]
    out["hl_headlines"] = d.get("gkg_title_records", np.nan)
    for c in CATS:
        out[f"hl_share_{c}"] = d.get(f"share_gkg_title_{c}", np.nan)
    out["hl_share_any"] = d.get("share_gkg_title_any", np.nan)
    out["hl_share_threats"] = d.get("share_gkg_title_threats", np.nan)
    out["hl_share_acts"] = d.get("share_gkg_title_acts", np.nan)
    out["hl_share_and"] = d.get("share_gkg_title_and_any", np.nan)
    out["hl_share_topic"] = d.get("share_gkg_title_topic_any", np.nan)
    out["th_share_gpr_like"] = d["share_gkg_gpr_like"]
    # Headlines exist only from ~Sept 2019 and need a usable sample per day.
    few = out["hl_headlines"].fillna(0) < 2000
    out.loc[few, [c for c in out.columns if c.startswith("hl_share_")]] = np.nan
    return out


def fit_normalisation(df: pd.DataFrame, gpr: pd.DataFrame) -> dict:
    base = df.loc[BASE_START:BASE_END]
    g = gpr.loc[BASE_START:BASE_END]
    norm = {"base_start": BASE_START, "base_end": BASE_END,
            "gpr_base_mean": {"GPRD": float(g["GPRD"].mean()),
                              "GPRD_THREAT": float(g["GPRD_THREAT"].mean()),
                              "GPRD_ACT": float(g["GPRD_ACT"].mean())},
            "share_base_mean": {}}
    for comp, cols in COMPONENTS.items():
        for col in cols:
            if col is None or col not in base:
                continue
            s = base[col]
            if comp == "fulltext":
                s = s[ft_ok(base)]
            norm["share_base_mean"][col] = float(s.mean())
            # Day-of-week factors (mean share on each weekday / overall mean).
            # Online news shares of conflict coverage rise at weekends while
            # GPR's newspaper shares fall, so both are adjusted explicitly.
            wd = s.groupby(s.index.dayofweek).mean() / s.mean()
            norm.setdefault("share_dow_factor", {})[col] = [float(wd.get(i, 1.0)) for i in range(7)]
    gw = g["GPRD"].groupby(g.index.dayofweek).mean() / g["GPRD"].mean()
    norm["gpr_dow_factor"] = [float(gw.get(i, 1.0)) for i in range(7)]
    return norm


def gpr_dow_adjusted(gpr: pd.Series, norm: dict) -> pd.Series:
    """GPR with its own (newspaper) day-of-week pattern removed."""
    f = np.asarray(norm["gpr_dow_factor"])[gpr.index.dayofweek]
    return gpr / f


def apply_normalisation(df: pd.DataFrame, norm: dict, composite: list[str]) -> pd.DataFrame:
    out = df.copy()
    sb, gb = norm["share_base_mean"], norm["gpr_base_mean"]
    dowf = norm.get("share_dow_factor", {})
    wd = out.index.dayofweek

    def scaled(col: str, gkey: str) -> pd.Series:
        base = sb.get(col)
        if col not in out or not base or base != base:  # missing or NaN base mean
            return pd.Series(np.nan, index=out.index)
        f = np.asarray(dowf.get(col, [1.0] * 7))[wd]
        return out[col] / f / base * gb[gkey]

    for comp, (c_any, c_thr, c_act) in COMPONENTS.items():
        out[f"idx_{comp}"] = scaled(c_any, "GPRD")
        if c_thr:
            out[f"idx_{comp}_threats"] = scaled(c_thr, "GPRD_THREAT")
            out[f"idx_{comp}_acts"] = scaled(c_act, "GPRD_ACT")
    ok_ft = ft_ok(out) if "ft_coverage" in out else pd.Series(False, index=out.index)
    for col in [c for c in out.columns if c.startswith("idx_fulltext")]:
        out.loc[~ok_ft, col] = np.nan
    # Composite: mean of the available primary components; on days with none
    # of them, mean of the available fallback components.
    def combine(names: list[str], suffix: str) -> pd.Series:
        cols = [f"idx_{c}{suffix}" for c in names if f"idx_{c}{suffix}" in out]
        if not cols:
            return pd.Series(np.nan, index=out.index)
        return out[cols].mean(axis=1, skipna=True)

    fallback = norm.get("fallback", [])
    sub = norm.get("subindex_components", ["fulltext", "headline"])
    out["tension_index"] = combine(composite, "").fillna(combine(fallback, ""))
    out["tension_index_threats"] = combine(sub, "_threats")
    out["tension_index_acts"] = combine(sub, "_acts")
    # GPR-scale nowcast: the weekday-neutral index with GPR's own weekday
    # pattern put back, for direct comparison with the published daily GPR.
    out["gpr_nowcast"] = out["tension_index"] * np.asarray(norm.get("gpr_dow_factor", [1.0] * 7))[wd]
    srcs = []
    for _, r in out.iterrows():
        used = [c for c in composite if pd.notna(r.get(f"idx_{c}"))]
        if not used:
            used = [c for c in fallback if pd.notna(r.get(f"idx_{c}"))]
        srcs.append("+".join(used))
    out["tension_sources"] = srcs
    return out


def coverage(english_total: pd.Series, weeks: int = 8) -> pd.Series:
    """Ratio of a day's English article count to the median of the same
    weekday over the preceding ``weeks`` weeks (weekend volume is ~40% lower,
    so weekdays must be compared like for like)."""
    s = english_total.asfreq("D")
    prev = pd.concat([s.shift(7 * k) for k in range(1, weeks + 1)], axis=1)
    med = prev.median(axis=1, skipna=True).where(prev.notna().sum(axis=1) >= 3)
    return (s / med).reindex(english_total.index)


def save_norm(norm: dict, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(norm, fh, indent=2)


def load_norm(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)
