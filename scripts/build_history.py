#!/usr/bin/env python3
"""Pull the full daily history (2017-01-01 onwards) of GPR-dictionary article
counts from the GDELT DOC 2.0 full-text API.

The DOC API rejects long queries, so each GPR category is split into pieces
(see ``queries.category_pieces``).  The split adapts: when a piece is rejected
as too long the category is re-split with a smaller size budget, and if even
the smallest pieces fail, the exclusion words are dropped for that category.
The plan that finally worked is saved to ``data/fulltext_plan.json``; the
daily job reuses exactly that plan so new days are comparable with history.

Output is a long CSV (date, category, value, norm).  ``value`` is the number
of matching English-language articles; for ``english_total`` it is the number
of English-language articles indexed that day (the denominator).  ``norm``
is GDELT's all-language article total.

Categories already present are skipped, so the script can simply be re-run.

    python scripts/build_history.py --out data/history_fulltext.csv
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import docapi, queries, wordlists  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
START = "20170101000000"  # the DOC API full-text archive begins 2017-01-01
# Size budgets tried in turn.  A query of 318 characters ("war threat" plus
# GPR's 34 exclusion words) is already rejected, so the exclusion words can
# not be used with this API and are off by default (see README).
SIZE_STEPS = [600, 420, 300, 210, 150, 100]


def pull(q: str, end: str) -> pd.DataFrame:
    df = docapi.timeline(q, START, f"{end}235959")
    if df.attrs.get("date_resolution") != "day":
        raise RuntimeError(f"unexpected resolution {df.attrs.get('date_resolution')}")
    return df


def pull_category(cat: str, end: str, try_exclusions: bool = False) -> tuple[dict, list[tuple[str, pd.DataFrame]]]:
    for exclude in ((True, False) if try_exclusions else (False,)):
        for size in SIZE_STEPS:
            try:
                pieces = queries.category_pieces(cat, exclude=exclude, max_chars=size)
            except ValueError:
                continue
            got = []
            try:
                for i, q in enumerate(pieces):
                    logging.info("  %s#%d/%d (%d chars, exclusions=%s)", cat, i, len(pieces), len(q), exclude)
                    got.append((f"{cat}#{i}", pull(q, end)))
            except docapi.QueryTooLong:
                logging.info("  rejected as too long at size %d; re-splitting", size)
                continue
            return {"max_chars": size, "exclude": exclude, "queries": pieces}, got
    raise RuntimeError(f"could not fit category {cat} into the DOC API")


def write(out_path: str, label: str, df: pd.DataFrame) -> None:
    out = df.reset_index()
    out.insert(1, "category", label)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    header = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    out[["date", "category", "value", "norm"]].to_csv(out_path, mode="a", header=header, index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "history_fulltext.csv"))
    ap.add_argument("--plan", default=os.path.join(ROOT, "data", "fulltext_plan.json"))
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).strftime("%Y%m%d"))
    ap.add_argument("--patient", action="store_true", help="wait up to ~10 min per rate-limit back-off")
    ap.add_argument("--try-exclusions", action="store_true", help="first try with GPR's exclusion words")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.patient:
        docapi.RATE_LIMIT_TRIES = 200
        docapi.RATE_LIMIT_MAX_DELAY = 600

    plan = {}
    if os.path.exists(args.plan):
        with open(args.plan) as fh:
            plan = json.load(fh)
    done: set[str] = set()
    if os.path.exists(args.out):
        done = {c.split("#")[0] for c in pd.read_csv(args.out)["category"]}

    if "english_total" not in done:
        logging.info("english_total")
        write(args.out, "english_total", pull(queries.ENGLISH_TOTAL_QUERY, args.end))
    plan["english_total"] = {"queries": [queries.ENGLISH_TOTAL_QUERY]}

    for cat, *_ in wordlists.CATEGORIES:
        if cat in done:
            continue
        logging.info("%s", cat)
        meta, got = pull_category(cat, args.end, args.try_exclusions)
        for label, df in got:
            write(args.out, label, df)
        plan[cat] = meta
        with open(args.plan, "w") as fh:
            json.dump(plan, fh, indent=2)
        logging.info("  %s done: %d piece(s), size %d, exclusions=%s",
                     cat, len(got), meta["max_chars"], meta["exclude"])
    with open(args.plan, "w") as fh:
        json.dump(plan, fh, indent=2)
    logging.info("all categories done")


if __name__ == "__main__":
    main()
