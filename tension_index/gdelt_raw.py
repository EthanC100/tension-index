"""Download and summarise raw GDELT 2.0 15-minute files (GKG + Events).

The raw GKG files do not contain article text, so they cannot be matched
against the GPR word lists directly.  They do carry GDELT's own theme tags,
and the Events files carry CAMEO event codes.  This module turns a 15-minute
slot into a row of counts that the theme-based proxy series are built from.

Only the main (English) files are used: GDELT publishes machine-translated
coverage in separate ``*.translation.*`` files, which are deliberately skipped
to stay close to GPR's English-language newspaper universe.
"""
from __future__ import annotations

import io
import logging
import time
import zipfile
from datetime import datetime, timedelta

import requests

from .titles import CATEGORY_NAMES, classify, classify_variants, extract_title
from .wordlists import ACT_CATEGORIES, THREAT_CATEGORIES

log = logging.getLogger(__name__)

BASE_URL = "https://data.gdeltproject.org/gdeltv2/"

# GKG themes counted per record.  The first block exists since the start of
# GKG 2.0 (Feb 2015); the WB_* World Bank taxonomy themes were added later and
# are recorded for reference only (they are not used in the composite).
THEMES = [
    "ARMEDCONFLICT",
    "MILITARY",
    "TERROR",
    "WMD",
    "BLOCKADE",
    "SANCTIONS",
    "CEASEFIRE",
    "ACT_FORCEPOSTURE",
    "ACT_HARMTHREATEN",
    "REBELLION",
    "SEIGE",
    "KILL",
    "TAX_WEAPONS",
    "TAX_TERROR_GROUP",
    "WB_2462_POLITICAL_VIOLENCE_AND_WAR",
    "WB_2468_CONVENTIONAL_WAR",
    "WB_2467_TERRORISM",
]

# Composite flags mirroring the GPR search categories as closely as GDELT's
# theme vocabulary allows (see README, "GKG theme proxy").
BUILDUP_THEMES = {"BLOCKADE", "SANCTIONS", "ACT_FORCEPOSTURE", "SEIGE"}


def composite_flags(themes: set[str]) -> dict[str, int]:
    war = "ARMEDCONFLICT" in themes                          # cat 1, 6, 7
    terror = "TERROR" in themes                              # cat 5, 8
    nuclear = "WMD" in themes                                # cat 4
    buildup = "MILITARY" in themes and bool(themes & BUILDUP_THEMES)  # cat 3
    return {
        "gpr_like": int(war or terror or nuclear or buildup),
        "war_like": int(war),
        "terror_like": int(terror),
        "nuclear_like": int(nuclear),
        "buildup_like": int(buildup),
    }


COMPOSITES = ["gpr_like", "war_like", "terror_like", "nuclear_like", "buildup_like"]

EVENT_ROOTS = ["13", "14", "15", "17", "18", "19", "20"]
EVENT_QUADS = ["1", "2", "3", "4"]

TITLE_COLUMNS = (["gkg_title_records"] + [f"gkg_title_{c}" for c in CATEGORY_NAMES]
                 + ["gkg_title_any", "gkg_title_threats", "gkg_title_acts",
                    "gkg_title_and_any", "gkg_title_topic_any"])
GKG_COLUMNS = (["gkg_total"] + [f"gkg_{t}" for t in THEMES] + [f"gkg_{c}" for c in COMPOSITES]
               + TITLE_COLUMNS)
EVT_COLUMNS = (
    ["evt_total", "evt_mentions"]
    + [f"evt_root{r}" for r in EVENT_ROOTS]
    + [f"evt_quad{q}" for q in EVENT_QUADS]
    + [f"evt_m_root{r}" for r in EVENT_ROOTS]
    + [f"evt_m_quad{q}" for q in EVENT_QUADS]
)
ROW_COLUMNS = ["slot", "gkg_status", "evt_status"] + GKG_COLUMNS + EVT_COLUMNS


def slot_id(ts: datetime) -> str:
    return ts.strftime("%Y%m%d%H%M%S")


def slots_for_day(day: datetime, hours: tuple[int, ...]) -> list[str]:
    return [slot_id(datetime(day.year, day.month, day.day, h, 0, 0)) for h in hours]


def fetch(url: str, session: requests.Session | None = None, tries: int = 5) -> bytes | None:
    """Return the file bytes, or None if GDELT has no file for that slot (404)."""
    s = session or requests.Session()
    last_exc: Exception | None = None
    for i in range(tries):
        try:
            r = s.get(url, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except Exception as exc:  # noqa: BLE001 - retry on any transport error
            last_exc = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_exc}")


def _unzip_single(blob: bytes) -> io.TextIOWrapper:
    zf = zipfile.ZipFile(io.BytesIO(blob))
    name = zf.namelist()[0]
    return io.TextIOWrapper(zf.open(name), encoding="utf-8", errors="replace", newline="")


def parse_gkg(blob: bytes) -> dict[str, int]:
    counts = {c: 0 for c in GKG_COLUMNS}
    for line in _unzip_single(blob):
        f = line.rstrip("\r\n").split("\t")
        if len(f) < 9:
            continue
        if f[2] != "1":  # SourceCollectionIdentifier 1 == web news
            continue
        counts["gkg_total"] += 1
        themes = {t.split(",")[0] for t in f[7].split(";") if t}
        for t in THEMES:
            if t in themes:
                counts[f"gkg_{t}"] += 1
        for k, v in composite_flags(themes).items():
            counts[f"gkg_{k}"] += v
        title = extract_title(f[26]) if len(f) > 26 else None
        if title:
            counts["gkg_title_records"] += 1
            cats = classify(title)
            for c, hit in cats.items():
                counts[f"gkg_title_{c}"] += hit
            counts["gkg_title_any"] += any(cats.values())
            counts["gkg_title_threats"] += any(cats[c] for c in THREAT_CATEGORIES)
            counts["gkg_title_acts"] += any(cats[c] for c in ACT_CATEGORIES)
            var = classify_variants(title)
            counts["gkg_title_and_any"] += var["and"]
            counts["gkg_title_topic_any"] += var["topic"]
    return counts


def parse_events(blob: bytes) -> dict[str, int]:
    counts = {c: 0 for c in EVT_COLUMNS}
    for line in _unzip_single(blob):
        f = line.rstrip("\r\n").split("\t")
        if len(f) < 35:
            continue
        root, quad = f[28], f[29]
        try:
            mentions = int(f[31])
        except ValueError:
            mentions = 0
        counts["evt_total"] += 1
        counts["evt_mentions"] += mentions
        if root in EVENT_ROOTS:
            counts[f"evt_root{root}"] += 1
            counts[f"evt_m_root{root}"] += mentions
        if quad in EVENT_QUADS:
            counts[f"evt_quad{quad}"] += 1
            counts[f"evt_m_quad{quad}"] += mentions
    return counts


def process_slot(slot: str, session: requests.Session | None = None) -> dict:
    """Download and summarise one 15-minute slot (``YYYYMMDDHHMMSS``)."""
    s = session or requests.Session()
    row: dict = {c: 0 for c in ROW_COLUMNS}
    row["slot"] = slot
    gkg = fetch(f"{BASE_URL}{slot}.gkg.csv.zip", s)
    if gkg is None:
        row["gkg_status"] = "missing"
    else:
        try:
            row.update(parse_gkg(gkg))
            row["gkg_status"] = "ok"
        except zipfile.BadZipFile:
            row["gkg_status"] = "badzip"
    evt = fetch(f"{BASE_URL}{slot}.export.CSV.zip", s)
    if evt is None:
        row["evt_status"] = "missing"
    else:
        try:
            row.update(parse_events(evt))
            row["evt_status"] = "ok"
        except zipfile.BadZipFile:
            row["evt_status"] = "badzip"
    return row


def daterange(start: datetime, end: datetime):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
