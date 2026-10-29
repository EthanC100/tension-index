"""Compute one day's tension-index row (word-list shares from the DOC API plus
the raw-GKG theme proxy) and merge it into the daily CSV."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import pandas as pd

from . import docapi, queries, wordlists
from .gdelt_raw import process_slot, slots_for_day
from .score import daily_shares_from_slots

log = logging.getLogger(__name__)

SAMPLE_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)
CATEGORY_NAMES = [c[0] for c in wordlists.CATEGORIES]
COLUMNS = (
    ["date", "articles_total"]
    + [f"share_{c}" for c in CATEGORY_NAMES]
    + ["share_any", "share_threats", "share_acts",
       "tension_index", "tension_threats", "tension_acts",
       "gkg_slots", "gkg_records", "gkg_share_gpr_like", "gkg_theme_index",
       "evt_share_conflict_mentions", "computed_at"]
)


def wordlist_shares(day: str, english_only: bool = True) -> dict:
    """Matching/total article counts for each GPR category and their union."""
    out: dict = {}
    totals = []
    for cat in CATEGORY_NAMES:
        v, n = docapi.day_counts(queries.boolean_query(cat, english_only=english_only), day)
        out[f"share_{cat}"] = v / n if n else float("nan")
        totals.append(n)
    v, n = docapi.day_counts(queries.union_boolean_query(english_only=english_only), day)
    out["share_any"] = v / n if n else float("nan")
    totals.append(n)
    out["articles_total"] = max(totals)
    out["share_threats"] = sum(out[f"share_{c}"] for c in wordlists.THREAT_CATEGORIES)
    out["share_acts"] = sum(out[f"share_{c}"] for c in wordlists.ACT_CATEGORIES)
    return out


def theme_proxy(day: str) -> dict:
    d = datetime.strptime(day, "%Y-%m-%d")
    rows = [process_slot(s) for s in slots_for_day(d, SAMPLE_HOURS)]
    agg = daily_shares_from_slots(pd.DataFrame(rows), min_ok_slots=4)
    if agg.empty:
        return {"gkg_slots": 0, "gkg_records": 0, "gkg_share_gpr_like": float("nan"),
                "evt_share_conflict_mentions": float("nan")}
    r = agg.iloc[0]
    return {
        "gkg_slots": int(r.get("gkg_slots", 0) or 0),
        "gkg_records": int(r.get("gkg_total", 0) or 0),
        "gkg_share_gpr_like": float(r["share_gkg_gpr_like"]),
        "evt_share_conflict_mentions": float(r["share_evt_m_quad4"]),
    }


def apply_normalisation(row: dict, norm: dict) -> dict:
    """Scale shares into GPR-style index values using stored base-period means."""
    row["tension_index"] = row["share_any"] / norm["share_any"] * 100
    row["tension_threats"] = row["share_threats"] / norm["share_threats"] * 100
    row["tension_acts"] = row["share_acts"] / norm["share_acts"] * 100
    g = row.get("gkg_share_gpr_like")
    row["gkg_theme_index"] = (g / norm["gkg_share_gpr_like"] * 100) if g == g else float("nan")
    return row


def compute_row(day: str, norm: dict, english_only: bool = True, with_proxy: bool = True) -> dict:
    row = {"date": day}
    row.update(wordlist_shares(day, english_only))
    if with_proxy:
        row.update(theme_proxy(day))
    row = apply_normalisation(row, norm)
    row["computed_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {c: row.get(c, float("nan")) for c in COLUMNS}


def upsert(path: str, row: dict) -> pd.DataFrame:
    new = pd.DataFrame([row])[COLUMNS]
    if os.path.exists(path) and os.path.getsize(path) > 0:
        old = pd.read_csv(path)
        old = old[old["date"] != row["date"]]
        df = pd.concat([old, new], ignore_index=True)
    else:
        df = new
    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(path, index=False, float_format="%.6g")
    return df


def load_normalisation(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)
