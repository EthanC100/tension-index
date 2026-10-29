#!/usr/bin/env python3
"""Compute yesterday's tension-index score and append it to data/tension_daily.csv.

    python scripts/daily.py                # yesterday (UTC)
    python scripts/daily.py --date 2026-10-20
    python scripts/daily.py --no-proxy     # skip the raw-GKG theme proxy
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.daily import compute_row, load_normalisation, upsert  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "normalisation.json"))
    ap.add_argument("--no-proxy", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    norm = load_normalisation(args.norm)
    row = compute_row(args.date, norm, with_proxy=not args.no_proxy)
    upsert(args.out, row)
    logging.info("%s: tension_index=%.1f (threats %.1f, acts %.1f), articles=%d, gkg proxy=%s",
                 args.date, row["tension_index"], row["tension_threats"], row["tension_acts"],
                 row["articles_total"], f"{row['gkg_theme_index']:.1f}")


if __name__ == "__main__":
    main()
