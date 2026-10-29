"""Compute daily tension-index rows and merge them into data/tension_daily.csv.

Each run:

1. pulls the raw GKG + Events files for the target day (24 hourly slots,
   the same sampling as the history) and computes the headline and theme
   shares;
2. pulls the full-text counts from the GDELT DOC API for a trailing window
   (default 10 days ending on the target day), so days that GDELT's
   full-text index had not caught up on yet are revised;
3. normalises with the stored base-period means (data/normalisation.json)
   and upserts the rows.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import docapi, queries, series
from .gdelt_raw import process_slot, slots_for_day
from .score import daily_shares_from_slots

log = logging.getLogger(__name__)

HOURS = tuple(range(24))

COLUMNS = (
    ["date", "tension_index", "gpr_nowcast", "tension_index_threats", "tension_index_acts", "tension_sources",
     "idx_fulltext", "idx_headline", "idx_headline_and", "idx_headline_topic", "idx_theme",
     "idx_fulltext_threats", "idx_fulltext_acts", "idx_headline_threats", "idx_headline_acts",
     "ft_english_articles", "ft_coverage", "ft_share_any", "ft_share_threats", "ft_share_acts"]
    + [f"ft_share_{c}" for c in series.CATS]
    + ["hl_headlines", "hl_share_any", "hl_share_threats", "hl_share_acts", "hl_share_and", "hl_share_topic"]
    + [f"hl_share_{c}" for c in series.CATS]
    + ["gkg_slots", "gkg_records", "th_share_gpr_like", "computed_at"]
)


def raw_day(day: str, workers: int = 8) -> pd.DataFrame:
    d = datetime.strptime(day, "%Y-%m-%d")
    slots = slots_for_day(d, HOURS)
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(process_slot, slots))
    daily = daily_shares_from_slots(pd.DataFrame(rows), min_ok_slots=12)
    return series.raw_shares(daily)


def fulltext_window(end_day: str, days: int, plan_path: str) -> pd.DataFrame:
    end = datetime.strptime(end_day, "%Y-%m-%d")
    start = end - timedelta(days=days - 1)
    frames = {}
    for label, q in queries.plan_from_file(plan_path):
        df = docapi.timeline(q, start.strftime("%Y%m%d000000"), end.strftime("%Y%m%d235959"))
        if df.attrs.get("date_resolution") not in ("day", None):
            df = df.resample("D").sum()
        frames[label] = df["value"]
    counts = queries.combine_pieces(pd.DataFrame(frames).fillna(0))
    counts.index = counts.index.normalize()
    return series.fulltext_shares(counts)


def run(day: str, csv_path: str, norm_path: str, ft_days: int = 10,
        with_fulltext: bool = True, with_raw: bool = True, plan_path: str | None = None) -> pd.DataFrame:
    plan_path = plan_path or os.path.join(os.path.dirname(norm_path), "fulltext_plan.json")
    norm = series.load_norm(norm_path)
    composite = norm.get("composite", ["fulltext", "headline"])
    old = pd.DataFrame(columns=COLUMNS)
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        old = pd.read_csv(csv_path)
    old = old.set_index(pd.to_datetime(old["date"])).drop(columns="date")

    new = pd.DataFrame(index=pd.DatetimeIndex([pd.Timestamp(day)]))
    if with_raw:
        new = raw_day(day)
    df = old.combine_first(new) if not old.empty else new
    df.update(new)  # the freshly computed raw shares win for the target day

    if with_fulltext:
        try:
            ft = fulltext_window(day, ft_days, plan_path)
            df = df.combine_first(ft)
            df.update(ft)
        except Exception as exc:  # noqa: BLE001 - keep the raw-file series even if the API fails
            log.error("full-text pull failed, keeping previous values: %s", exc)

    df = df.sort_index()
    df["ft_coverage"] = series.coverage(df["ft_english_articles"].astype(float))
    df = series.apply_normalisation(df.astype({c: float for c in df.columns
                                               if c not in ("tension_sources", "computed_at")}, errors="ignore"),
                                    norm, composite)
    stamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    touched = df.index >= pd.Timestamp(day) - pd.Timedelta(days=ft_days - 1)
    df.loc[touched, "computed_at"] = stamp
    df.index.name = "date"
    out = df.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    for c in COLUMNS:
        if c not in out:
            out[c] = np.nan
    out = out[COLUMNS]
    out.to_csv(csv_path, index=False, float_format="%.6g")
    return out


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()
