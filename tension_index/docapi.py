"""Thin client for the GDELT DOC 2.0 full-text API.

The DOC API indexes the full text of the same article stream that feeds the
GKG, so it is the only public GDELT surface on which the GPR word lists can be
applied literally.  ``timelinevolraw`` returns, per time bucket, the number of
matching articles (``value``) and the total number of articles GDELT monitored
in that bucket (``norm``), which is exactly the numerator and denominator of a
GPR-style share.

GDELT asks for at most one request every 5 seconds; the client enforces that
and backs off (up to several minutes) when the API answers with its
rate-limit notice instead of JSON.
"""
from __future__ import annotations

import json
import logging
import time

import pandas as pd
import requests

log = logging.getLogger(__name__)

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
MIN_INTERVAL = 6.0
_last_call = 0.0


class RateLimited(RuntimeError):
    pass


def _get(params: dict, tries: int = 15, timeout: int = 300) -> dict:
    global _last_call
    delay = 10.0
    for attempt in range(tries):
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        r = requests.get(ENDPOINT, params=params, timeout=timeout)
        _last_call = time.monotonic()
        text = r.text
        if text.lstrip().startswith("{"):
            return json.loads(text)
        if "limit requests" in text or r.status_code == 429:
            log.warning("GDELT rate limit hit (attempt %d); sleeping %.0fs", attempt + 1, delay)
            time.sleep(delay)
            delay = min(delay * 1.6, 180)
            continue
        raise RuntimeError(f"GDELT DOC API error ({r.status_code}): {text[:300]}")
    raise RateLimited("GDELT DOC API kept returning its rate-limit notice")


def timeline(query: str, start: str, end: str) -> pd.DataFrame:
    """Daily (or finer, for short spans) matching counts and totals.

    ``start``/``end`` are ``YYYYMMDDHHMMSS`` strings.  Returns a DataFrame
    indexed by bucket timestamp with columns ``value`` and ``norm``.
    """
    d = _get(dict(query=query, mode="timelinevolraw", format="json",
                  startdatetime=start, enddatetime=end))
    series = d.get("timeline", [])
    if not series:
        return pd.DataFrame(columns=["value", "norm"])
    rows = series[0]["data"]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%dT%H%M%SZ")
    df = df.set_index("date")[["value", "norm"]].astype(float)
    df.attrs["date_resolution"] = d.get("query_details", {}).get("date_resolution")
    return df


def day_counts(query: str, day: str) -> tuple[float, float]:
    """(matching, total) article counts for one calendar day (UTC).

    The API picks the bucket resolution itself, so counts are summed over
    whatever buckets it returns for the 24-hour window.
    """
    day = day.replace("-", "")
    df = timeline(query, f"{day}000000", f"{day}235959")
    if df.empty:
        return 0.0, 0.0
    return float(df["value"].sum()), float(df["norm"].sum())
