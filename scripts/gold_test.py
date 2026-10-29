#!/usr/bin/env python3
"""Does the tension index predict gold and silver returns?

Train on 2019-09-01..2023-12-31, evaluate once on 2024-01-01..latest.
Writes reports/gold_test.md plus CSV tables and a figure in reports/.

    python scripts/gold_test.py            # uses cached market data in data/markets
    python scripts/gold_test.py --refresh  # re-download market data
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
from tension_index import markets  # noqa: E402
from tension_index.predict import (dm_test, event_trades, hit_rate, ols_hac,  # noqa: E402
                                   random_entry_pvalue)

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "reports")
TRAIN = ("2019-09-01", "2023-12-31")
TEST_START = "2024-01-01"
HORIZONS = [1, 5, 20]
METALS = ["gold", "silver"]
CONTROLS = ["d_real_yield_bp", "dxy_ret_pct", "d_vix"]
SPECS = {
    "as_specified": 0,   # return from today's close: overlaps the index day (see report)
    "implementable": 1,  # return from tomorrow's close: index published ~05:23 UTC first
}
COST = 0.001
RULE_HOLD = 5


# ----------------------------------------------------------------------------- data

def tension_level(daily_csv: str) -> pd.Series:
    """The series behind tension_index since 2019-09 (topic-word headline
    share), weekday-adjusted with factors fitted on the training period only."""
    d = pd.read_csv(daily_csv, parse_dates=["date"]).set_index("date")
    s = d["hl_share_topic"].loc["2019-08-20":]
    s = s.where(s > 0)
    b = s.loc[TRAIN[0]:TRAIN[1]]
    f = b.groupby(b.index.dayofweek).mean() / b.mean()
    return (s / f.reindex(s.index.dayofweek).to_numpy()).rename("tension")


def change_on_trading_days(level: pd.Series, cal: pd.DatetimeIndex) -> pd.Series:
    """For trading day t with previous trading day t': mean log level over the
    calendar days (t', t] minus log level on t'.  Weekend news therefore
    counts towards Monday."""
    L = np.log(level.asfreq("D"))
    out = {}
    for prev, cur in zip(cal[:-1], cal[1:]):
        if prev not in L.index or pd.isna(L.get(prev)):
            out[cur] = np.nan
            continue
        window = L.loc[prev + pd.Timedelta(days=1):cur]
        out[cur] = window.mean() - L[prev] if window.notna().any() else np.nan
    return pd.Series(out)


def build_frame(daily_csv: str, refresh: bool) -> tuple[pd.DataFrame, pd.Timestamp]:
    mk = markets.load(start="2019-06-01", refresh=refresh)
    # End at the last day every series actually reported (FRED lags a day).
    last = min(markets.fetch(n).index.max() for n in markets.SERIES)
    mk = mk.loc[:last]
    cal = mk.index
    df = pd.DataFrame(index=cal)
    df["d_tension"] = change_on_trading_days(tension_level(daily_csv), cal)
    df["d_real_yield_bp"] = mk["real_yield"].diff() * 100
    df["dxy_ret_pct"] = np.log(mk["dxy"]).diff() * 100
    df["d_vix"] = mk["vix"].diff()
    for m in METALS:
        lp = np.log(mk[m])
        df[f"{m}_ret0"] = lp.diff() * 100  # same-day return (close t' -> close t)
        for spec, delay in SPECS.items():
            for h in HORIZONS:
                df[f"{m}_{spec}_h{h}"] = (lp.shift(-(h + delay)) - lp.shift(-delay)) * 100
        df[f"{m}_price"] = mk[m]
    # Standardise the tension change with training-period moments.
    tr = df.loc[TRAIN[0]:TRAIN[1], "d_tension"]
    df["z_tension"] = (df["d_tension"] - tr.mean()) / tr.std()
    return df, last


def train_mask(df: pd.DataFrame, h: int, delay: int) -> pd.Series:
    """Training rows whose whole return window ends by the training end date."""
    pos = pd.Series(np.arange(len(df)), index=df.index)
    end_pos = pos.loc[:TRAIN[1]].iloc[-1]
    return (df.index >= TRAIN[0]) & (df.index <= TRAIN[1]) & (pos + h + delay <= end_pos)


# ----------------------------------------------------------------------------- tests

MODELS = {"tension": ["z_tension"], "controls": CONTROLS, "tension+controls": ["z_tension"] + CONTROLS}


def regressions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    coef_rows, oos_rows, pred_store = [], [], {}
    for m in METALS:
        for spec, delay in SPECS.items():
            for h in HORIZONS:
                y = df[f"{m}_{spec}_h{h}"]
                tr = train_mask(df, h, delay)
                te = (df.index >= TEST_START) & y.notna()
                cols_all = ["z_tension"] + CONTROLS
                ok = df[cols_all].notna().all(axis=1) & y.notna()
                fits = {}
                for name, cols in MODELS.items():
                    res = ols_hac(y[tr & ok], df.loc[tr & ok, cols], lags=h + delay)
                    fits[name] = res
                    tab = res.table()
                    for var in tab.index:
                        coef_rows.append({"metal": m, "spec": spec, "h": h, "model": name, "var": var,
                                          "coef": tab.loc[var, "coef"], "se_hac": tab.loc[var, "se_hac"],
                                          "t": tab.loc[var, "t"], "p": tab.loc[var, "p"],
                                          "n": res.n, "r2": res.r2})
                # Descriptive only: the same tension-only regression fitted on the test period.
                res_te = ols_hac(y[te & ok], df.loc[te & ok, ["z_tension"]], lags=h + delay)
                coef_rows.append({"metal": m, "spec": spec, "h": h, "model": "tension (test-period refit, descriptive)",
                                  "var": "z_tension", "coef": res_te.beta[1], "se_hac": res_te.se[1],
                                  "t": res_te.t[1], "p": res_te.p[1], "n": res_te.n, "r2": res_te.r2})
                # Out of sample: coefficients from training, evaluated once on the test period.
                yt = y[te & ok].to_numpy()
                X = df.loc[te & ok]
                preds = {"zero": np.zeros(len(yt)), "mean": np.full(len(yt), y[tr & ok].mean())}
                for name, res in fits.items():
                    preds[name] = res.predict(X[res.names[1:]]).to_numpy()
                err = {k: yt - v for k, v in preds.items()}
                rmse = {k: float(np.sqrt(np.mean(e ** 2))) for k, e in err.items()}
                mae = {k: float(np.mean(np.abs(e))) for k, e in err.items()}
                sse = {k: float(np.sum(e ** 2)) for k, e in err.items()}
                dm_tz, p_tz = dm_test(err["zero"], err["tension"], h + delay)
                dm_bc, p_bc = dm_test(err["controls"], err["tension+controls"], h + delay)
                dm_tm, p_tm = dm_test(err["mean"], err["tension"], h + delay)
                oos_rows.append({
                    "metal": m, "spec": spec, "h": h, "n_test": len(yt),
                    "rmse_zero": rmse["zero"], "rmse_mean": rmse["mean"], "rmse_controls": rmse["controls"],
                    "rmse_tension": rmse["tension"], "rmse_both": rmse["tension+controls"],
                    "mae_zero": mae["zero"], "mae_controls": mae["controls"],
                    "mae_tension": mae["tension"], "mae_both": mae["tension+controls"],
                    "r2oos_tension_vs_zero": 1 - sse["tension"] / sse["zero"],
                    "r2oos_mean_vs_zero": 1 - sse["mean"] / sse["zero"],
                    "r2oos_controls_vs_zero": 1 - sse["controls"] / sse["zero"],
                    "r2oos_tension_vs_mean": 1 - sse["tension"] / sse["mean"],
                    "dm_p_tension_vs_mean": p_tm,
                    "r2oos_both_vs_controls": 1 - sse["tension+controls"] / sse["controls"],
                    "dm_p_tension_vs_zero": p_tz, "dm_p_both_vs_controls": p_bc,
                    "hit_tension": hit_rate(preds["tension"], yt),
                    "hit_controls": hit_rate(preds["controls"], yt),
                    "hit_both": hit_rate(preds["tension+controls"], yt),
                    "hit_tension_slope_only": hit_rate(fits["tension"].beta[1] * X["z_tension"].to_numpy(), yt),
                    "share_up": float((yt > 0).mean()),
                })
                pred_store[(m, spec, h)] = (X.index, yt, preds)
    return pd.DataFrame(coef_rows), pd.DataFrame(oos_rows), pred_store


def context(df: pd.DataFrame) -> pd.DataFrame:
    """Same-day reaction: today's metal return on today's tension change."""
    rows = []
    for m in METALS:
        for per, (a, b) in {"train": TRAIN, "test": (TEST_START, None)}.items():
            sub = df.loc[a:b]
            for name, cols in [("tension", ["z_tension"]), ("tension+controls", ["z_tension"] + CONTROLS)]:
                res = ols_hac(sub[f"{m}_ret0"], sub[cols], lags=1)
                rows.append({"metal": m, "period": per, "model": name, "coef_z_tension": res.beta[1],
                             "t": res.t[1], "p": res.p[1], "n": res.n})
    return pd.DataFrame(rows)


def gpr_context(df: pd.DataFrame, gpr_csv: str) -> pd.DataFrame:
    """Gold vs the official daily GPR: does gold move with GPR on the same
    day, and do GPR changes predict gold's next-day return?  (Descriptive;
    the daily GPR is published weekly, so it could not be traded on.)"""
    g = pd.read_csv(gpr_csv, parse_dates=["date"]).set_index("date")["GPRD"]
    b = g.loc[TRAIN[0]:TRAIN[1]]
    f = b.groupby(b.index.dayofweek).mean() / b.mean()
    lvl = (g / f.reindex(g.index.dayofweek).to_numpy()).loc["2019-08-01":]
    d = change_on_trading_days(lvl, df.index)
    z = (d - d.loc[TRAIN[0]:TRAIN[1]].mean()) / d.loc[TRAIN[0]:TRAIN[1]].std()
    rows = []
    for per, (a, bnd) in {"train": TRAIN, "test": (TEST_START, None)}.items():
        for target, col in [("same day", "gold_ret0"), ("next day (from today's close)", "gold_as_specified_h1")]:
            for sig_name, sig in [("z_gpr", z), ("z_tension", df["z_tension"])]:
                X = pd.DataFrame({sig_name: sig}).loc[a:bnd]
                res = ols_hac(df[col].loc[a:bnd], X, lags=1)
                rows.append({"period": per, "gold return": target, "signal": sig_name,
                             "coef_bp_per_sd": 100 * res.beta[1], "t": res.t[1], "n": res.n})
    return pd.DataFrame(rows)


def rule(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    thr = df.loc[TRAIN[0]:TRAIN[1], "d_tension"].quantile(0.9)
    signal = df["d_tension"] >= thr
    px = df["gold_price"]
    summ, yearly, all_trades = [], [], []
    for spec, delay in SPECS.items():
        trades = event_trades(px, signal, hold=RULE_HOLD, delay=delay, cost=COST)
        trades["spec"] = spec
        trades["period"] = np.where(trades["signal_date"] >= pd.Timestamp(TEST_START), "test", "train")
        trades = trades[trades["signal_date"] >= pd.Timestamp(TRAIN[0])]
        all_trades.append(trades)
        for per, (a, b) in {"train": TRAIN, "test": (TEST_START, str(px.index.max().date()))}.items():
            t = trades[trades["period"] == per]
            n_sig = int(signal.loc[a:b].sum())
            net = t["net"].to_numpy()
            ex5 = np.sort(net)[:-5] if len(net) > 5 else np.array([])
            r5 = (px.shift(-RULE_HOLD) / px - 1 - COST).loc[a:b].dropna()
            summ.append({
                "spec": spec, "period": per, "signals": n_sig, "trades": len(t),
                "mean_net_pct": 100 * net.mean() if len(net) else np.nan,
                "median_net_pct": 100 * np.median(net) if len(net) else np.nan,
                "hit_rate": float((net > 0).mean()) if len(net) else np.nan,
                "total_net_pct": 100 * (np.prod(1 + net) - 1) if len(net) else np.nan,
                "mean_net_ex5best_pct": 100 * ex5.mean() if len(ex5) else np.nan,
                "total_net_ex5best_pct": 100 * (np.prod(1 + ex5) - 1) if len(ex5) else np.nan,
                "uncond_5d_mean_net_pct": 100 * r5.mean(),
                "random_entry_p": random_entry_pvalue(px, len(t), RULE_HOLD, net.mean() if len(net) else np.nan,
                                                      (a, b), cost=COST),
                "buy_hold_pct": 100 * (px.loc[a:b].iloc[-1] / px.loc[a:b].iloc[0] - 1),
                "days_invested_share": len(t) * RULE_HOLD / max(1, len(px.loc[a:b])),
            })
        g = trades.groupby(trades["entry"].dt.year)
        for yr, t in g:
            net = t["net"].to_numpy()
            pxy = px.loc[str(yr)]
            r5 = (px.shift(-RULE_HOLD) / px - 1 - COST).loc[str(yr)].dropna()
            yearly.append({"spec": spec, "year": yr, "trades": len(t), "mean_net_pct": 100 * net.mean(),
                           "hit_rate": float((net > 0).mean()), "total_net_pct": 100 * (np.prod(1 + net) - 1),
                           "uncond_5d_mean_net_pct": 100 * r5.mean(),
                           "gold_year_pct": 100 * (pxy.iloc[-1] / pxy.iloc[0] - 1)})
    return pd.DataFrame(summ), pd.DataFrame(yearly), pd.concat(all_trades), float(thr)


# ----------------------------------------------------------------------------- report

def fmt(x, nd=3):
    if isinstance(x, (int, np.integer)):
        return str(x)
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{x:.{nd}f}"


def md(df: pd.DataFrame, nd: int = 3) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt(r[c], nd) if not isinstance(r[c], str) else r[c] for c in cols) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", default=os.path.join(ROOT, "data", "tension_daily.csv"))
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    df, last = build_frame(args.daily, args.refresh)
    coefs, oos, preds = regressions(df)
    ctx = context(df)
    rsum, ryear, trades, thr = rule(df)
    gctx = gpr_context(df, os.path.join(ROOT, "validation", "gpr_daily_vintage.csv"))
    gctx.to_csv(os.path.join(OUT, "gold_test_gpr_context.csv"), index=False, float_format="%.6g")

    coefs.to_csv(os.path.join(OUT, "gold_test_coefficients.csv"), index=False, float_format="%.6g")
    oos.to_csv(os.path.join(OUT, "gold_test_oos.csv"), index=False, float_format="%.6g")
    ctx.to_csv(os.path.join(OUT, "gold_test_same_day.csv"), index=False, float_format="%.6g")
    rsum.to_csv(os.path.join(OUT, "gold_test_rule_summary.csv"), index=False, float_format="%.6g")
    ryear.to_csv(os.path.join(OUT, "gold_test_rule_by_year.csv"), index=False, float_format="%.6g")
    trades.to_csv(os.path.join(OUT, "gold_test_rule_trades.csv"), index=False, float_format="%.6g")

    # Figure: test-period equity of the implementable rule vs buy-and-hold gold.
    px = df["gold_price"].loc[TEST_START:]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(px.index, px / px.iloc[0], color="#888", label="gold, buy and hold")
    for spec, colr in [("implementable", "#c0392b"), ("as_specified", "#2c7fb8")]:
        t = trades[(trades["spec"] == spec) & (trades["period"] == "test")].sort_values("exit")
        eq = pd.Series((1 + t["net"]).cumprod().to_numpy(), index=t["exit"])
        eq = pd.concat([pd.Series([1.0], index=[px.index[0]]), eq])
        ax.step(eq.index, eq.to_numpy(), where="post", color=colr, label=f"rule ({spec.replace('_', ' ')}), after costs")
    ax.set_ylabel("growth of 1")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "gold_test_rule.png"), dpi=130)
    plt.close(fig)

    sel = coefs[(coefs["var"] == "z_tension")].copy()
    sel["coef_bp"] = sel["coef"] * 100
    sel["se_bp"] = sel["se_hac"] * 100

    lines = [
        "# Does the tension index predict gold and silver?",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/gold_test.py`. "
        f"Training sample {TRAIN[0]} to {TRAIN[1]}; test sample {TEST_START} to {last:%Y-%m-%d} (evaluated once).",
        "",
        "Signal: `z_tension`, the change in the (training-period weekday-adjusted) tension index from the previous "
        "trading day to today, in log points, standardised with training-period mean and SD (1 unit = 1 SD, "
        f"{df.loc[TRAIN[0]:TRAIN[1], 'd_tension'].std():.3f} log points).  Controls: today's change in the 10y TIPS "
        "real yield (bp), the dollar index log return (%) and the VIX change (points).  Returns are log returns in %; "
        "coefficients on `z_tension` are shown in basis points of return per 1 SD.",
        "",
        "Two timings.  *as_specified*: return from today's close.  The index day ends at 24:00 UTC, after "
        "the COMEX close, and is published about 05:23 UTC the next day, so this return overlaps a few hours of "
        "the same news and could not have been traded.  *implementable*: return from the next day's close, "
        "after the index is published.",
        "",
        "## Coefficients on z_tension (training sample, Newey-West SE)",
        "",
        md(sel[sel["model"].isin(["tension", "tension+controls"])][
            ["metal", "spec", "h", "model", "coef_bp", "se_bp", "t", "p", "n"]], 2),
        "",
        "Same regression re-fitted on the test sample (descriptive only; not used for forecasting):",
        "",
        md(sel[sel["model"].str.startswith("tension (test")][["metal", "spec", "h", "coef_bp", "se_bp", "t", "p", "n"]], 2),
        "",
        "Control coefficients (training, tension+controls model) are in `gold_test_coefficients.csv`.",
        "",
        "## Out-of-sample (test sample, training coefficients)",
        "",
        "RMSE in % return (lower is better).  R²_oos = 1 − SSE(model)/SSE(benchmark); negative means worse than the benchmark.  "
        "DM p = Diebold-Mariano test of equal squared error (HAC).",
        "",
        md(oos[["metal", "spec", "h", "n_test", "rmse_zero", "rmse_mean", "rmse_controls", "rmse_tension", "rmse_both"]], 4),
        "",
        "Gains in squared error.  `mean` is a model with only an intercept fitted on the training sample "
        "(gold's 2019-2023 drift); it isolates what the tension slope adds beyond that drift.",
        "",
        md(oos[["metal", "spec", "h", "r2oos_tension_vs_zero", "dm_p_tension_vs_zero", "r2oos_mean_vs_zero",
                "r2oos_tension_vs_mean", "dm_p_tension_vs_mean", "r2oos_both_vs_controls",
                "dm_p_both_vs_controls"]], 4),
        "",
        "Direction hit rates on the test sample.  `share_up` is the hit rate of always predicting a rise. "
        "`hit_tension_slope_only` uses only the sign of the slope × signal (ignores the intercept, which "
        "mostly encodes gold's uptrend).",
        "",
        md(oos[["metal", "spec", "h", "hit_tension", "hit_tension_slope_only", "hit_controls", "hit_both", "share_up"]], 3),
        "",
        "## Same-day reaction (descriptive)",
        "",
        "Today's metal return (previous close to today's close) on today's tension change.",
        "",
        md(ctx, 3),
        "",
        "## Gold against the official GPR (descriptive)",
        "",
        "Same weekday adjustment and day-change construction applied to the published daily GPR "
        "(validation vintage).  Coefficients in bp of gold return per 1 SD change.",
        "",
        md(gctx, 2),
        "",
        "## Trading rule: long gold for 5 trading days after a top-decile daily index rise",
        "",
        f"Top decile = training-period 90th percentile of the daily tension change ({thr:.3f} log points, "
        "fixed for the test).  Entry at the close (today for as_specified, next day for implementable); exit "
        f"{RULE_HOLD} trading days later; 0.1% round-trip cost per trade; signals during an open trade are "
        "ignored.  `uncond_5d_mean_net_pct` is the average 5-day gold return (after the same cost) from every "
        "day in the period: the bar the rule has to clear.  `random_entry_p` is the share of 5,000 random "
        "sets of the same number of entry days whose mean is at least the rule's.",
        "",
        md(rsum, 3),
        "",
        "By year of entry:",
        "",
        md(ryear, 3),
        "",
        "![rule](gold_test_rule.png)",
        "",
    ]
    with open(os.path.join(OUT, "gold_test.md"), "w") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
