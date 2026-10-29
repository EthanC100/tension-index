#!/usr/bin/env python3
"""Validate the tension index against the official daily GPR index.

Produces validation/report.md plus CSV tables and figures.

    python scripts/validate.py --daily data/tension_daily.csv --gpr validation/gpr_daily.xls
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index.gpr import DAILY_URL, load_daily_gpr  # noqa: E402
from tension_index.series import BASE_END, BASE_START  # noqa: E402
from tension_index.validation import (corr_by_frequency, cross_correlation,  # noqa: E402
                                      granger_style_lead, lead_lag_summary)

ROOT = os.path.join(os.path.dirname(__file__), "..")

PAIRS = [
    # (label, our column, GPR column, earliest start).  "_SA" = GPR with its
    # own day-of-week pattern removed (factors estimated over the base period).
    ("gpr_nowcast vs GPRD (both as published, with weekday pattern)", "gpr_nowcast", "GPRD", "2015-01-01"),
    ("tension_index vs GPRD_SA", "tension_index", "GPRD_SA", "2015-01-01"),
    ("tension_index_threats vs GPRD_THREAT_SA", "tension_index_threats", "GPRD_THREAT_SA", "2015-01-01"),
    ("tension_index_acts vs GPRD_ACT_SA", "tension_index_acts", "GPRD_ACT_SA", "2015-01-01"),
    ("idx_fulltext vs GPRD_SA", "idx_fulltext", "GPRD_SA", "2017-01-01"),
    ("idx_headline vs GPRD_SA", "idx_headline", "GPRD_SA", "2019-09-01"),
    ("idx_headline_and vs GPRD_SA", "idx_headline_and", "GPRD_SA", "2019-09-01"),
    ("idx_headline_topic vs GPRD_SA", "idx_headline_topic", "GPRD_SA", "2019-09-01"),
    ("idx_theme vs GPRD_SA", "idx_theme", "GPRD_SA", "2015-01-01"),
]


def add_seasonally_adjusted(gpr: pd.DataFrame, base_start: str, base_end: str) -> pd.DataFrame:
    out = gpr.copy()
    for col in ["GPRD", "GPRD_THREAT", "GPRD_ACT"]:
        b = gpr[col].loc[base_start:base_end]
        f = b.groupby(b.index.dayofweek).mean() / b.mean()
        out[f"{col}_SA"] = gpr[col] / f.reindex(gpr.index.dayofweek).to_numpy()
    return out


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for idx in df.index:
        vals = []
        for c in cols:
            v = df.at[idx, c]
            if pd.api.types.is_integer_dtype(df[c]):
                vals.append(f"{int(v):+d}" if "lag" in c else str(int(v)))
            elif isinstance(v, (float, np.floating)):
                vals.append("" if v != v else floatfmt.format(v))
            else:
                vals.append(str(v))
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
    if not args.gpr.endswith(".csv"):
        gpr.to_csv(os.path.join(args.outdir, "gpr_daily_vintage.csv"), float_format="%.6g")
    gpr = add_seasonally_adjusted(gpr, BASE_START, BASE_END)

    report = [f"# Validation against the daily GPR index\n",
              f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.  "
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
        gcol_label = gcol
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
        lev_s = lead_lag_summary(cross_correlation(x, y, max_lag=args.max_lag, transform="level"))
        det["level_lag"] = lev_s["best_lag"]
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
            "| series vs GPR | sample | daily r | daily r (dow-adj) | weekly r | monthly r | best lag (levels) | best lag (detrended) | r at best lag (detrended) | verdict (detrended) |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in overview:
        head.append(f"| {r['pair']} | {r['sample']} | {r['daily']:.3f} | {r['dow']:.3f} | {r['weekly']:.3f} "
                    f"| {r['monthly']:.3f} | {r['level_lag']:+d} | {r['best_lag']:+d} | {r['corr_at_best']:.3f} | {r['verdict']} |")
    report[2:2] = head

    # Overview figure: monthly means of the index and GPR.
    if "tension_index" in ours:
        m = pd.concat({"tension_index": ours["tension_index"], "GPRD": gpr["GPRD"]}, axis=1)
        m = m.loc[ours["tension_index"].first_valid_index():]
        m = m.loc[:gpr_end].resample("MS").mean()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(m.index, m["GPRD"], label="GPR daily (monthly mean)", color="#444")
        ax.plot(m.index, m["tension_index"], label="tension index (monthly mean)", color="#c0392b")
        ax.set_ylabel("index (GPR scale)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(args.outdir, "overview_monthly.png"), dpi=130)
        plt.close(fig)

        w = pd.concat({"tension_index": ours["tension_index"], "GPRD": gpr["GPRD"]}, axis=1)
        w = w.loc["2022-01-01":gpr_end].resample("W-SUN").mean()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(w.index, w["GPRD"], label="GPR daily (weekly mean)", color="#444")
        ax.plot(w.index, w["tension_index"], label="tension index (weekly mean)", color="#c0392b")
        ax.set_ylabel("index (GPR scale)")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(args.outdir, "overview_weekly_recent.png"), dpi=130)
        plt.close(fig)

    # Stability: daily / weekly / monthly correlation of the headline index by
    # sub-period and by calendar year.
    if "tension_index" in ours:
        rows = []
        x_all, y_all = ours["tension_index"], gpr["GPRD_SA"]
        periods = [("2015-02 to 2019-08 (theme fallback)", "2015-01-01", "2019-08-31"),
                   (f"2019-09 to {gpr_end:%Y-%m} (headline era)", "2019-09-01", str(gpr_end.date()))]
        periods += [(str(yr), f"{yr}-01-01", f"{yr}-12-31") for yr in range(2015, gpr_end.year + 1)]
        for name, a, b in periods:
            t = corr_by_frequency(x_all.loc[a:b], y_all.loc[a:b])
            if t.loc["daily", "n"] < 60:
                continue
            ll = lead_lag_summary(cross_correlation(x_all.loc[a:b], y_all.loc[a:b], max_lag=7, transform="detrend"))
            rows.append({"period": name, "days": int(t.loc["daily", "n"]),
                         "daily": t.loc["daily", "pearson"], "weekly": t.loc["weekly", "pearson"],
                         "monthly": t.loc["monthly", "pearson"] if t.loc["monthly", "n"] >= 6 else float("nan"),
                         "best_lag": ll["best_lag"]})
        sub = pd.DataFrame(rows).set_index("period")
        sub.to_csv(os.path.join(args.outdir, "corr_by_period.csv"))
        report.append("\n## tension_index vs GPRD_SA by period\n")
        report.append(md_table(sub) + "\n")

    with open(os.path.join(args.outdir, "report.md"), "w") as fh:
        fh.write("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
