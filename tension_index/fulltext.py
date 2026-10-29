"""Full-text (GDELT DOC API) counts: storage, incremental pulls and shares.

All counts live in one long CSV, ``data/history_fulltext.csv``, with columns
``date, category, value, norm``.  ``category`` is a query-piece label from
``data/fulltext_plan.json`` (``english_total`` or ``<category>#<piece>``).
The history backfill writes it once; the daily job upserts a trailing window.
A day's shares are computed only when every piece is present for that day.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta

import pandas as pd

from . import docapi, queries, series

log = logging.getLogger(__name__)


def load_counts(path: str) -> pd.DataFrame:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["date", "category", "value", "norm"])
    return pd.read_csv(path)


def upsert_counts(path: str, label: str, df: pd.DataFrame) -> None:
    """Replace the rows of ``label`` for the dates in ``df`` (index: dates)."""
    new = pd.DataFrame({"date": df.index.strftime("%Y-%m-%d"), "category": label,
                        "value": df["value"].to_numpy(), "norm": df["norm"].to_numpy()})
    old = load_counts(path)
    keep = ~((old["category"] == label) & old["date"].isin(new["date"]))
    out = pd.concat([old[keep], new], ignore_index=True).sort_values(["category", "date"])
    out.to_csv(path, index=False)


def shares(counts: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    """Wide daily full-text shares; NaN on days missing any query piece."""
    c = counts[counts["category"].isin(labels)].copy()
    c["date"] = pd.to_datetime(c["date"])
    wide = c.pivot_table(index="date", columns="category", values="value", aggfunc="last")
    wide = wide.reindex(columns=labels)
    complete = wide.notna().all(axis=1)
    out = series.fulltext_shares(queries.combine_pieces(wide.fillna(0)))
    out.loc[~complete, :] = float("nan")
    out["ft_coverage"] = series.coverage(out["ft_english_articles"])
    return out


def pull_window(plan: list[tuple[str, str]], end_day: str, days: int, counts_path: str,
                budget_s: float = 1800) -> int:
    """Pull every plan query for the ``days``-day window ending ``end_day``.

    Stops when ``budget_s`` seconds have elapsed; the starting piece rotates
    with the date so that, under heavy rate limiting, successive runs still
    refresh every piece.  Returns the number of pieces pulled.
    """
    end = datetime.strptime(end_day, "%Y-%m-%d")
    start = end - timedelta(days=days - 1)
    s, e = start.strftime("%Y%m%d000000"), end.strftime("%Y%m%d235959")
    offset = end.toordinal() % len(plan)
    order = plan[offset:] + plan[:offset]
    t0, done = time.monotonic(), 0
    for label, q in order:
        if time.monotonic() - t0 > budget_s:
            log.warning("full-text time budget used up after %d/%d pieces", done, len(plan))
            break
        try:
            df = docapi.timeline(q, s, e)
        except docapi.RateLimited:
            log.warning("full-text: gave up on %s after repeated rate limiting", label)
            break
        if df.attrs.get("date_resolution") not in ("day", None):
            df = df.resample("D").sum()
        df.index = df.index.normalize()
        df = df.reindex(pd.date_range(start, end, freq="D")).fillna(0)
        upsert_counts(counts_path, label, df)
        done += 1
    return done
