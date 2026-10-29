"""Download and parse the official daily GPR index (Caldara & Iacoviello)."""
from __future__ import annotations

import io

import pandas as pd
import requests

DAILY_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"


def load_daily_gpr(path_or_url: str = DAILY_URL) -> pd.DataFrame:
    """Return a DataFrame indexed by date with columns GPRD, GPRD_ACT,
    GPRD_THREAT, N10D (number of articles in the 10 newspapers)."""
    if path_or_url.startswith("http"):
        r = requests.get(path_or_url, timeout=120)
        r.raise_for_status()
        src = io.BytesIO(r.content)
    else:
        src = path_or_url
    df = pd.read_excel(src, sheet_name=0)
    df = df[["DAY", "N10D", "GPRD", "GPRD_ACT", "GPRD_THREAT"]].dropna(subset=["DAY"])
    df["date"] = pd.to_datetime(df["DAY"].astype(int).astype(str), format="%Y%m%d")
    return df.drop(columns="DAY").set_index("date").sort_index()
