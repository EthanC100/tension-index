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
    n = normalize_like_gpr(s)
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
