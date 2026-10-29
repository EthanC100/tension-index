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
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import queries, series  # noqa: E402
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


def fulltext_history(path: str) -> pd.DataFrame:
    h = pd.read_csv(path, parse_dates=["date"])
    wide = h.pivot_table(index="date", columns="category", values="value", aggfunc="sum")
    counts = queries.combine_pieces(wide)
    shares = series.fulltext_shares(counts)
    shares["ft_coverage"] = series.coverage(shares["ft_english_articles"])
    return shares


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fulltext", default=os.path.join(ROOT, "data", "history_fulltext.csv"))
    ap.add_argument("--slots", default=os.path.join(ROOT, "data", "raw", "raw_slots*.csv.gz"))
    ap.add_argument("--gpr", default=DAILY_URL)
    ap.add_argument("--composite", default="fulltext,headline")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--daily-components", default=os.path.join(ROOT, "data", "raw_slots_daily.csv"))
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "normalisation.json"))
    args = ap.parse_args()

    slots = load_slots(args.slots)
    daily_raw = daily_shares_from_slots(slots, min_ok_slots=4)
    daily_raw.index.name = "date"
    daily_raw.to_csv(args.daily_components, float_format="%.6g")
    raw = series.raw_shares(daily_raw)

    ft = fulltext_history(args.fulltext) if os.path.exists(args.fulltext) else pd.DataFrame()
    df = raw.join(ft, how="outer") if not ft.empty else raw
    for c in ["ft_english_articles", "ft_coverage", "ft_share_any", "ft_share_threats", "ft_share_acts"]:
        if c not in df:
            df[c] = np.nan

    gpr = load_daily_gpr(args.gpr)
    norm = series.fit_normalisation(df, gpr)
    norm["composite"] = args.composite.split(",")
    norm["built_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
