#!/usr/bin/env python3
"""Rebuild data/tension_daily.csv and data/normalisation.json from the
historical pulls.

Inputs
  data/history_fulltext.csv     full-text counts from scripts/build_history.py
  data/raw/raw_slots*.csv.gz    raw GKG/Events slot summaries from scripts/backfill_raw.py
  the official daily GPR        (only its base-period mean is used, to put the
                                 index on GPR's scale)

    python scripts/rebuild_daily.py --gpr validation/gpr_daily_vintage.xls \
        --composite fulltext,headline
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import fulltext, queries, series  # noqa: E402
from tension_index.daily import COLUMNS  # noqa: E402
from tension_index.gpr import DAILY_URL, load_daily_gpr  # noqa: E402
from tension_index.score import daily_shares_from_slots  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_slots(pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no slot files match {pattern}")
    frames = [pd.read_csv(f, dtype={"slot": str}) for f in files]
    # Later files (the hourly, headline-aware backfill) win on duplicate slots.
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates("slot", keep="last")


def fulltext_history(counts_path: str, plan_path: str) -> pd.DataFrame:
    labels = [lbl for lbl, _ in queries.plan_from_file(plan_path)]
    return fulltext.shares(fulltext.load_counts(counts_path), labels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fulltext", default=os.path.join(ROOT, "data", "history_fulltext.csv"))
    ap.add_argument("--plan", default=os.path.join(ROOT, "data", "fulltext_plan.json"))
    ap.add_argument("--slots", default=os.path.join(ROOT, "data", "raw", "raw_slots*.csv.gz"))
    ap.add_argument("--gpr", default=DAILY_URL)
    ap.add_argument("--composite", default="fulltext,headline_topic")
    ap.add_argument("--fallback", default="theme")
    ap.add_argument("--subindex", default="fulltext,headline")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--daily-components", default=os.path.join(ROOT, "data", "raw_slots_daily.csv"))
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "normalisation.json"))
    args = ap.parse_args()

    slots = load_slots(args.slots)
    daily_raw = daily_shares_from_slots(slots, min_ok_slots=4)
    daily_raw.index.name = "date"
    daily_raw.to_csv(args.daily_components, float_format="%.6g")
    raw = series.raw_shares(daily_raw)
    # Days added by the daily job after the archived slot files end are kept
    # from the existing output (their raw-file shares are stored there).
    if os.path.exists(args.out):
        prev = pd.read_csv(args.out, parse_dates=["date"]).set_index("date")
        later = prev.loc[prev.index > raw.index.max(), [c for c in raw.columns if c in prev.columns]]
        if not later.empty:
            raw = pd.concat([raw, later])

    have_ft = os.path.exists(args.fulltext) and os.path.exists(args.plan)
    ft = fulltext_history(args.fulltext, args.plan) if have_ft else pd.DataFrame()
    df = raw.join(ft, how="outer") if not ft.empty else raw
    # Keep every calendar day; GDELT outages (e.g. 2025-06-15..07-01, when no
    # raw files were published) become empty rows rather than missing dates.
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="D"))
    for c in ["ft_english_articles", "ft_coverage", "ft_share_any", "ft_share_threats", "ft_share_acts"]:
        if c not in df:
            df[c] = np.nan

    gpr = load_daily_gpr(args.gpr)
    norm = series.fit_normalisation(df, gpr)
    norm["composite"] = args.composite.split(",")
    norm["fallback"] = [c for c in args.fallback.split(",") if c]
    norm["subindex_components"] = args.subindex.split(",")
    norm["built_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    series.save_norm(norm, args.norm)

    out = series.apply_normalisation(df, norm, norm["composite"])
    out["computed_at"] = norm["built_at"]
    out.index.name = "date"
    out = out.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    for c in COLUMNS:
        if c not in out:
            out[c] = np.nan
    out[COLUMNS].to_csv(args.out, index=False, float_format="%.6g")
    print(f"wrote {len(out)} rows to {args.out}")
    print(f"normalisation: {norm}")


if __name__ == "__main__":
    main()
