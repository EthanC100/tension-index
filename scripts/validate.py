#!/usr/bin/env python3
"""Validate the tension index against the official daily GPR index.

Produces validation/report.md plus CSV tables and figures.

    python scripts/validate.py --daily data/tension_daily.csv --gpr validation/gpr_daily.xls
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.gpr import DAILY_URL, load_daily_gpr  # noqa: E402
from tension_index.validation import (corr_by_frequency, cross_correlation,  # noqa: E402
                                      granger_style_lead, lead_lag_summary)

ROOT = os.path.join(os.path.dirname(__file__), "..")

PAIRS = [
    # (label, our column, GPR column, earliest start)
    ("tension_index vs GPRD", "tension_index", "GPRD", "2015-01-01"),
    ("tension_index_threats vs GPRD_THREAT", "tension_index_threats", "GPRD_THREAT", "2015-01-01"),
    ("tension_index_acts vs GPRD_ACT", "tension_index_acts", "GPRD_ACT", "2015-01-01"),
    ("idx_fulltext vs GPRD", "idx_fulltext", "GPRD", "2017-01-01"),
    ("idx_headline vs GPRD", "idx_headline", "GPRD", "2019-09-01"),
    ("idx_headline_and vs GPRD", "idx_headline_and", "GPRD", "2019-09-01"),
    ("idx_headline_topic vs GPRD", "idx_headline_topic", "GPRD", "2019-09-01"),
    ("idx_theme vs GPRD", "idx_theme", "GPRD", "2015-01-01"),
]


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        vals = [floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in row]
        lines.append("| " + " | ".join([str(idx)] + vals) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--gpr", default=DAILY_URL)
    ap.add_argument("--outdir", default=os.path.join(ROOT, "validation"))
    ap.add_argument("--max-lag", type=int, default=15)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    ours = pd.read_csv(args.daily, parse_dates=["date"]).set_index("date")
    gpr = load_daily_gpr(args.gpr)
    gpr_end = gpr.index.max()
    gpr.to_csv(os.path.join(args.outdir, "gpr_daily_vintage.csv"), float_format="%.6g")

    report = [f"# Validation against the daily GPR index\n",
              f"Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC.  "
              f"GPR vintage ends {gpr_end:%Y-%m-%d}; tension index ends {ours.index.max():%Y-%m-%d}.\n"]
    summary_rows = []
    overview = []
    for label, ocol, gcol, start in PAIRS:
        if ocol not in ours:
            continue
        x = ours[ocol].loc[start:gpr_end]
        y = gpr[gcol].loc[start:gpr_end]
        both = pd.concat([x, y], axis=1).dropna()
        if len(both) < 100:
            continue
        slug = label.split(" vs ")[0]
        report.append(f"\n## {label}\n")
        report.append(f"Sample: {both.index.min():%Y-%m-%d} to {both.index.max():%Y-%m-%d}, "
                      f"{len(both)} overlapping days.\n")
        lev = corr_by_frequency(x, y)
        lg = corr_by_frequency(x, y, log=True)
        tab = lev.join(lg, lsuffix="_level", rsuffix="_log")
        tab.to_csv(os.path.join(args.outdir, f"corr_{slug}.csv"))
        report.append("### Correlation by frequency\n")
        report.append(md_table(tab.rename(columns={"n_level": "n"}).drop(columns=["n_log"])) + "\n")

        report.append("### Lead/lag structure (daily)\n")
        report.append("Positive lag k means the tension index at day t is correlated with GPR at day t+k, "
                      "i.e. the tension index leads.\n")
        xcs = {}
        for tr in ["level", "log", "detrend", "diff"]:
            xc = cross_correlation(x, y, max_lag=args.max_lag, transform=tr)
            xcs[tr] = xc["corr"]
            s = lead_lag_summary(xc)
            summary_rows.append({"pair": label, "transform": tr, **s})
            report.append(f"- **{tr}**: best lag {s['best_lag']:+d} (r={s['corr_at_best']:.3f}; "
                          f"r at lag 0 = {s['corr_at_0']:.3f}) → {s['verdict']}")
        xcdf = pd.DataFrame(xcs)
        det = lead_lag_summary(cross_correlation(x, y, max_lag=args.max_lag, transform="detrend"))
        overview.append({"pair": label, "sample": f"{both.index.min():%Y-%m} to {both.index.max():%Y-%m}",
                         "daily": tab.loc["daily", "pearson_level"],
                         "dow": tab.loc["daily_dow_adj", "pearson_level"], "weekly": tab.loc["weekly", "pearson_level"],
                         "monthly": tab.loc["monthly", "pearson_level"], **det})
        xcdf.to_csv(os.path.join(args.outdir, f"xcorr_{slug}.csv"))
        g = granger_style_lead(x, y)
        report.append(f"\nPredictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR "
                      f"on its own lags raises R² by {g['x_helps_predict_y']:.4f}; the reverse raises R² by "
                      f"{g['y_helps_predict_x']:.4f}.\n")
        report.append("\nCross-correlation table (lags −5…+5, level / log / detrend / diff):\n")
        report.append(md_table(xcdf.loc[-5:5]) + "\n")

        fig, ax = plt.subplots(figsize=(7, 3.2))
        for tr in ["level", "detrend", "diff"]:
            ax.plot(xcdf.index, xcdf[tr], marker="o", ms=3, label=tr)
        ax.axvline(0, color="grey", lw=0.8)
        ax.set_xlabel("lag k (days): corr(tension_t, GPR_{t+k})")
        ax.set_ylabel("correlation")
        ax.set_title(label)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(args.outdir, f"xcorr_{slug}.png"), dpi=130)
        plt.close(fig)

    summ = pd.DataFrame(summary_rows)
    summ.to_csv(os.path.join(args.outdir, "lead_lag_summary.csv"), index=False)
    head = ["\n## Summary\n",
            "Pearson correlations of index levels.  \"dow-adj\" removes each series' day-of-week means first.  "
            "Lead/lag from daily log deviations from a trailing 30-day mean.\n",
            "| series vs GPR | sample | daily r | daily r (dow-adj) | weekly r | monthly r | best lag | r at best lag | verdict |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in overview:
        head.append(f"| {r['pair']} | {r['sample']} | {r['daily']:.3f} | {r['dow']:.3f} | {r['weekly']:.3f} "
                    f"| {r['monthly']:.3f} | {r['best_lag']:+d} | {r['corr_at_best']:.3f} | {r['verdict']} |")
    report[2:2] = head

    # Overview figure: monthly means of the index and GPR.
    if "tension_index" in ours:
        m = pd.concat({"tension_index": ours["tension_index"], "GPRD": gpr["GPRD"]}, axis=1)
        m = m.loc["2017-01-01":gpr_end].resample("MS").mean()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(m.index, m["GPRD"], label="GPR daily (monthly mean)", color="#444")
        ax.plot(m.index, m["tension_index"], label="tension index (monthly mean)", color="#c0392b")
        ax.set_ylabel("index (base period = 100)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(args.outdir, "overview_monthly.png"), dpi=130)
        plt.close(fig)

        w = pd.concat({"tension_index": ours["tension_index"], "GPRD": gpr["GPRD"]}, axis=1)
        w = w.loc["2022-01-01":gpr_end].resample("W-SUN").mean()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(w.index, w["GPRD"], label="GPR daily (weekly mean)", color="#444")
        ax.plot(w.index, w["tension_index"], label="tension index (weekly mean)", color="#c0392b")
        ax.set_ylabel("index")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(args.outdir, "overview_weekly_recent.png"), dpi=130)
        plt.close(fig)

    with open(os.path.join(args.outdir, "report.md"), "w") as fh:
        fh.write("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
