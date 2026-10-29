#!/usr/bin/env python3
"""Compute yesterday's tension-index score and merge it into data/tension_daily.csv.

    python scripts/daily.py                    # yesterday (UTC)
    python scripts/daily.py --date 2026-10-20
    python scripts/daily.py --no-fulltext      # raw-file series only (no DOC API calls)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.daily import run, yesterday  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=yesterday())
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "normalisation.json"))
    ap.add_argument("--fulltext-days", type=int, default=10,
                    help="trailing window of full-text counts to (re)pull")
    ap.add_argument("--fulltext-budget", type=float, default=30,
                    help="minutes to spend on (rate-limited) full-text API calls")
    ap.add_argument("--no-fulltext", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    out = run(args.date, args.out, args.norm, ft_days=args.fulltext_days,
              with_fulltext=not args.no_fulltext, ft_budget_s=args.fulltext_budget * 60)
    r = out[out["date"] == args.date].iloc[0]
    logging.info("%s  tension_index=%.1f  (sources: %s; headline=%.1f, fulltext=%s, theme=%.1f)",
                 args.date, r["tension_index"], r["tension_sources"], r["idx_headline"],
                 "n/a" if r["idx_fulltext"] != r["idx_fulltext"] else f"{r['idx_fulltext']:.1f}",
                 r["idx_theme"])


if __name__ == "__main__":
    main()
