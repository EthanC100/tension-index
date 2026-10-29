#!/usr/bin/env python3
"""Aggregate the per-slot raw GDELT summaries into daily shares.

    python scripts/aggregate_slots.py --slots raw_slots.csv --out data/raw_slots_daily.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.score import daily_shares_from_slots  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-ok-slots", type=int, default=4)
    args = ap.parse_args()
    raw = pd.read_csv(args.slots, dtype={"slot": str})
    daily = daily_shares_from_slots(raw, min_ok_slots=args.min_ok_slots)
    daily.index.name = "date"
    daily.to_csv(args.out, float_format="%.6g")
    print(f"{len(daily)} days written to {args.out}")


if __name__ == "__main__":
    main()
