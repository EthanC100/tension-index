#!/usr/bin/env python3
"""Backfill the raw GDELT slot summaries used by the theme-based proxy series.

Example:
    python scripts/backfill_raw.py --start 2015-02-19 --end 2026-10-27 \
        --out data/raw_slots.csv --workers 12

Rows are appended as they complete, so the job can be interrupted and resumed.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.gdelt_raw import ROW_COLUMNS, daterange, process_slot, slots_for_day  # noqa: E402

DEFAULT_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)


def _work(slot: str) -> dict:
    try:
        return process_slot(slot)
    except Exception as exc:  # noqa: BLE001
        row = {c: 0 for c in ROW_COLUMNS}
        row.update(slot=slot, gkg_status=f"error:{exc}"[:80], evt_status="error")
        return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--hours", default=",".join(map(str, DEFAULT_HOURS)))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    hours = tuple(int(h) for h in args.hours.split(","))
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    slots = [s for d in daterange(start, end) for s in slots_for_day(d, hours)]

    done: set[str] = set()
    if os.path.exists(args.out):
        with open(args.out, newline="") as fh:
            for r in csv.DictReader(fh):
                if not r["gkg_status"].startswith("error"):
                    done.add(r["slot"])
    todo = [s for s in slots if s not in done]
    logging.info("%d slots total, %d already done, %d to do", len(slots), len(done), len(todo))

    new_file = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
    with open(args.out, "a", newline="") as fh, Pool(args.workers) as pool:
        w = csv.DictWriter(fh, fieldnames=ROW_COLUMNS)
        if new_file:
            w.writeheader()
        for i, row in enumerate(pool.imap_unordered(_work, todo, chunksize=4), 1):
            w.writerow(row)
            if i % 200 == 0:
                fh.flush()
                logging.info("%d/%d slots done", i, len(todo))
    logging.info("finished")


if __name__ == "__main__":
    main()
