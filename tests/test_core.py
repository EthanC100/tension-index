import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tension_index import queries, wordlists  # noqa: E402
from tension_index.score import normalize_like_gpr  # noqa: E402
from tension_index.validation import (corr_by_frequency, cross_correlation,  # noqa: E402
                                      lead_lag_summary)


def _pair(shift: int):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2018-01-01", periods=1500, freq="D")
    base = pd.Series(np.exp(rng.normal(size=len(idx) + 10)).cumsum()[10:], index=idx)
    noise = pd.Series(np.exp(rng.normal(size=len(idx))), index=idx)
    x = noise
    y = noise.shift(shift) + 0.1  # y follows x by `shift` days
    return x, y.dropna(), base


def test_positive_lag_means_x_leads():
    x, y, _ = _pair(2)
    s = lead_lag_summary(cross_correlation(x, y, max_lag=5))
    assert s["best_lag"] == 2 and s["verdict"].startswith("leads by 2")


def test_negative_lag_means_x_lags():
    x, y, _ = _pair(-3)
    s = lead_lag_summary(cross_correlation(x, y, max_lag=5))
    assert s["best_lag"] == -3 and s["verdict"].startswith("lags by 3")


def test_corr_by_frequency_shapes():
    x, y, _ = _pair(0)
    t = corr_by_frequency(x, y)
    assert list(t.index) == ["daily", "daily_dow_adj", "weekly", "monthly"]
    assert t.loc["daily", "pearson"] > 0.99


def test_normalisation_base_mean_is_100():
    idx = pd.date_range("2016-01-01", "2021-12-31", freq="D")
    s = pd.Series(np.linspace(1, 2, len(idx)), index=idx)
    n = normalize_like_gpr(s, "2017-01-01", "2019-12-31")
    assert abs(n.loc["2017-01-01":"2019-12-31"].mean() - 100) < 1e-9


def test_every_truncated_term_has_inflections():
    for _name, topic, other, _op in wordlists.CATEGORIES:
        for t in topic + other:
            assert all("*" not in f for f in queries.expand(t))
    for t in wordlists.EXCLUSION_WORDS:
        assert all("*" not in f for f in queries.expand(t))


def test_boolean_queries_are_english_and_exclude():
    q = queries.boolean_query("war_threats")
    assert q.endswith("sourcelang:english")
    assert "-movie" in q and "threatened" in q and "*" not in q


def test_fulltext_upsert_and_complete_days(tmp_path):
    from tension_index import fulltext
    path = str(tmp_path / "counts.csv")
    idx = pd.date_range("2024-01-01", periods=70, freq="D")
    labels = ["english_total"] + [f"{c}#0" for c, *_ in wordlists.CATEGORIES]
    for lbl in labels:
        v = 10000.0 if lbl == "english_total" else 100.0
        fulltext.upsert_counts(path, lbl, pd.DataFrame({"value": v, "norm": 30000.0}, index=idx))
    # Re-pull one piece for the last 5 days with new values: rows are replaced, not duplicated.
    fulltext.upsert_counts(path, "war_threats#0",
                           pd.DataFrame({"value": 300.0, "norm": 1.0}, index=idx[-5:]))
    counts = fulltext.load_counts(path)
    assert len(counts) == len(labels) * len(idx)
    sh = fulltext.shares(counts, labels)
    assert abs(sh.loc["2024-01-10", "ft_share_war_threats"] - 0.01) < 1e-12
    assert abs(sh.loc[idx[-1], "ft_share_war_threats"] - 0.03) < 1e-12
    # A day missing one piece gets no full-text share at all.
    counts = counts[~((counts["category"] == "terror_acts#0") & (counts["date"] == "2024-01-20"))]
    sh = fulltext.shares(counts, labels)
    assert np.isnan(sh.loc["2024-01-20", "ft_share_any"])
