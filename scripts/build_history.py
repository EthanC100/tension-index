#!/usr/bin/env python3
"""Pull the full daily history (2017-01-01 onwards) of GPR-dictionary article
counts from the GDELT DOC API, one request per query.

Output is a long CSV (date, variant, category, value, norm) that
``scripts/validate.py`` and ``scripts/daily.py`` build on.  Rows already
present are skipped, so the script can be re-run after a rate-limit failure.

Example:
    python scripts/build_history.py --variants boolean_en --out data/history_counts.csv
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import docapi, queries, wordlists  # noqa: E402

START = "20170101000000"  # the DOC API full-text archive begins 2017-01-01


def query_plan(variant: str) -> list[tuple[str, str]]:
    """(category label, query) pairs for a variant."""
    english = variant.endswith("_en")
    mode = variant.rsplit("_", 1)[0]
    plan = []
    for cat, *_ in wordlists.CATEGORIES:
        if mode == "boolean":
            plan.append((cat, queries.boolean_query(cat, english_only=english)))
        elif mode == "proximity":
            for i, q in enumerate(queries.proximity_queries(cat, english_only=english)):
                plan.append((f"{cat}#{i}", q))
        else:
            raise SystemExit(f"unknown variant {variant}")
    if mode == "boolean":
        plan.append(("union", queries.union_boolean_query(english_only=english)))
    return plan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="boolean_en")
    ap.add_argument("--out", required=True)
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).strftime("%Y%m%d"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    done: set[tuple[str, str]] = set()
    if os.path.exists(args.out):
        prev = pd.read_csv(args.out)
        done = set(zip(prev["variant"], prev["category"]))

    for variant in args.variants.split(","):
        for label, q in query_plan(variant):
            if (variant, label) in done:
                continue
            logging.info("%s / %s (%d chars)", variant, label, len(q))
            df = docapi.timeline(q, START, f"{args.end}235959")
            if df.attrs.get("date_resolution") != "day":
                raise RuntimeError(f"unexpected resolution {df.attrs.get('date_resolution')}")
            out = df.reset_index().rename(columns={"date": "date"})
            out.insert(1, "variant", variant)
            out.insert(2, "category", label)
            out.insert(3, "query", q)
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")
            header = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
            out.to_csv(args.out, mode="a", header=header, index=False)
            logging.info("  %d days, %.0f matching articles total", len(out), out["value"].sum())


if __name__ == "__main__":
    main()
