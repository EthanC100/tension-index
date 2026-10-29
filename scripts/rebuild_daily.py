#!/usr/bin/env python3
"""Rebuild data/tension_daily.csv and data/normalisation.json from the
historical pulls (DOC API counts + raw GDELT slot summaries).

    python scripts/rebuild_daily.py --history data/history_counts.csv \
        --slots data/raw_slots_daily.csv --variant boolean_en
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import wordlists  # noqa: E402
from tension_index.daily import COLUMNS  # noqa: E402
from tension_index.score import BASE_END, BASE_START  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def wordlist_daily(history: pd.DataFrame, variant: str) -> pd.DataFrame:
    h = history[history["variant"] == variant].copy()
    h["date"] = pd.to_datetime(h["date"])
    val = h.pivot_table(index="date", columns="category", values="value")
    norm = h.pivot_table(index="date", columns="category", values="norm")
    out = pd.DataFrame(index=val.index)
    out["articles_total"] = norm.max(axis=1)
    for cat in [c[0] for c in wordlists.CATEGORIES]:
        out[f"share_{cat}"] = val[cat] / norm[cat]
    out["share_any"] = val["union"] / norm["union"]
    out["share_threats"] = sum(out[f"share_{c}"] for c in wordlists.THREAT_CATEGORIES)
    out["share_acts"] = sum(out[f"share_{c}"] for c in wordlists.ACT_CATEGORIES)
    # Days with a tiny article total are indexing gaps, not news; drop them.
    out.loc[out["articles_total"] < 0.1 * out["articles_total"].rolling(30, min_periods=5).median(), :] = np.nan
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default=os.path.join(ROOT, "data", "history_counts.csv"))
    ap.add_argument("--slots", default=os.path.join(ROOT, "data", "raw_slots_daily.csv"))
    ap.add_argument("--variant", default="boolean_en")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "normalisation.json"))
    args = ap.parse_args()

    wl = wordlist_daily(pd.read_csv(args.history), args.variant)
    slots = pd.read_csv(args.slots, parse_dates=["date"]).set_index("date")
    df = pd.DataFrame(index=wl.index.union(slots.index))
    for c in wl.columns:
        df[c] = wl[c]
    df["gkg_slots"] = slots["gkg_slots"]
    df["gkg_records"] = slots["gkg_total"]
    df["gkg_share_gpr_like"] = slots["share_gkg_gpr_like"]
    df["evt_share_conflict_mentions"] = slots["share_evt_m_quad4"]

    base = df.loc[BASE_START:BASE_END]
    norm = {k: float(base[k].mean()) for k in ["share_any", "share_threats", "share_acts", "gkg_share_gpr_like"]}
    norm.update({"base_start": BASE_START, "base_end": BASE_END, "variant": args.variant,
                 "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
    with open(args.norm, "w") as fh:
        json.dump(norm, fh, indent=2)

    df["tension_index"] = df["share_any"] / norm["share_any"] * 100
    df["tension_threats"] = df["share_threats"] / norm["share_threats"] * 100
    df["tension_acts"] = df["share_acts"] / norm["share_acts"] * 100
    df["gkg_theme_index"] = df["gkg_share_gpr_like"] / norm["gkg_share_gpr_like"] * 100
    df["computed_at"] = norm["built_at"]
    df.index.name = "date"
    out = df.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out[COLUMNS]
    out.to_csv(args.out, index=False, float_format="%.6g")
    print(f"wrote {len(out)} rows to {args.out}; normalisation: {norm}")


if __name__ == "__main__":
    main()
