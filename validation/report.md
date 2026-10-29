# Validation against the daily GPR index

Generated 2026-10-29 02:41 UTC.  GPR vintage ends 2026-10-26; tension index ends 2026-10-28.


## Summary

Pearson correlations of index levels.  "dow-adj" removes each series' day-of-week means first.  Lead/lag from daily log deviations from a trailing 30-day mean.

| series vs GPR | sample | daily r | daily r (dow-adj) | weekly r | monthly r | best lag (levels) | best lag (detrended) | r at best lag (detrended) | verdict (detrended) |
|---|---|---|---|---|---|---|---|---|---|
| gpr_nowcast vs GPRD (both as published, with weekday pattern) | 2015-02 to 2026-10 | 0.662 | 0.601 | 0.769 | 0.811 | +0 | +0 | 0.518 | matches |
| tension_index vs GPRD_SA | 2015-02 to 2026-10 | 0.587 | 0.590 | 0.770 | 0.815 | +1 | +1 | 0.305 | leads by 1 day(s) |
| tension_index_threats vs GPRD_THREAT_SA | 2019-09 to 2026-10 | 0.398 | 0.399 | 0.695 | 0.776 | +1 | +1 | 0.206 | leads by 1 day(s) |
| tension_index_acts vs GPRD_ACT_SA | 2019-09 to 2026-10 | 0.260 | 0.260 | 0.383 | 0.562 | +1 | +1 | 0.170 | matches |
| idx_headline vs GPRD_SA | 2019-09 to 2026-10 | 0.406 | 0.407 | 0.648 | 0.809 | +1 | +1 | 0.209 | leads by 1 day(s) |
| idx_headline_and vs GPRD_SA | 2019-09 to 2026-10 | 0.497 | 0.497 | 0.744 | 0.858 | +1 | +1 | 0.240 | leads by 1 day(s) |
| idx_headline_topic vs GPRD_SA | 2019-09 to 2026-10 | 0.675 | 0.675 | 0.855 | 0.903 | +1 | +1 | 0.333 | leads by 1 day(s) |
| idx_theme vs GPRD_SA | 2015-02 to 2026-10 | 0.443 | 0.447 | 0.580 | 0.584 | +1 | +1 | 0.326 | leads by 1 day(s) |

## gpr_nowcast vs GPRD (both as published, with weekday pattern)

Sample: 2015-02-19 to 2026-10-26, 4244 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 4244.000 | 0.662 | 0.559 | 0.601 | 0.559 |
| daily_dow_adj | 4244.000 | 0.601 | 0.416 | 0.481 | 0.419 |
| weekly | 609.000 | 0.769 | 0.598 | 0.690 | 0.599 |
| monthly | 141.000 | 0.811 | 0.677 | 0.746 | 0.657 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +0 (r=0.662; r at lag 0 = 0.662) → matches
- **log**: best lag +0 (r=0.601; r at lag 0 = 0.601) → matches
- **detrend**: best lag +0 (r=0.518; r at lag 0 = 0.518) → matches
- **diff**: best lag +0 (r=0.401; r at lag 0 = 0.401) → matches

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0655; the reverse raises R² by 0.0126.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.323 | 0.198 | -0.057 | -0.171 |
| -4 | 0.313 | 0.187 | -0.062 | -0.022 |
| -3 | 0.325 | 0.195 | -0.050 | -0.029 |
| -2 | 0.366 | 0.228 | -0.011 | -0.190 |
| -1 | 0.531 | 0.426 | 0.264 | 0.026 |
| 0 | 0.662 | 0.601 | 0.518 | 0.401 |
| 1 | 0.550 | 0.429 | 0.273 | 0.014 |
| 2 | 0.386 | 0.246 | 0.019 | -0.172 |
| 3 | 0.339 | 0.211 | -0.024 | -0.024 |
| 4 | 0.320 | 0.198 | -0.046 | -0.037 |
| 5 | 0.331 | 0.216 | -0.031 | -0.188 |


## tension_index vs GPRD_SA

Sample: 2015-02-19 to 2026-10-26, 4244 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 4244.000 | 0.587 | 0.416 | 0.479 | 0.416 |
| daily_dow_adj | 4244.000 | 0.590 | 0.419 | 0.481 | 0.419 |
| weekly | 609.000 | 0.770 | 0.609 | 0.689 | 0.598 |
| monthly | 141.000 | 0.815 | 0.689 | 0.745 | 0.656 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.603; r at lag 0 = 0.587) → leads by 1 day(s)
- **log**: best lag +1 (r=0.500; r at lag 0 = 0.479) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.305; r at lag 0 = 0.267) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.083; r at lag 0 = 0.010) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0171; the reverse raises R² by 0.0015.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.487 | 0.401 | 0.120 | -0.030 |
| -4 | 0.508 | 0.423 | 0.162 | 0.015 |
| -3 | 0.532 | 0.436 | 0.187 | 0.006 |
| -2 | 0.542 | 0.446 | 0.205 | 0.005 |
| -1 | 0.564 | 0.452 | 0.218 | -0.033 |
| 0 | 0.587 | 0.479 | 0.267 | 0.010 |
| 1 | 0.603 | 0.500 | 0.305 | 0.083 |
| 2 | 0.564 | 0.469 | 0.250 | -0.035 |
| 3 | 0.543 | 0.460 | 0.232 | 0.018 |
| 4 | 0.527 | 0.439 | 0.193 | -0.013 |
| 5 | 0.504 | 0.426 | 0.168 | -0.000 |


## tension_index_threats vs GPRD_THREAT_SA

Sample: 2019-09-22 to 2026-10-26, 2570 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 2570.000 | 0.398 | 0.355 | 0.363 | 0.357 |
| daily_dow_adj | 2570.000 | 0.399 | 0.356 | 0.364 | 0.360 |
| weekly | 370.000 | 0.695 | 0.624 | 0.700 | 0.663 |
| monthly | 86.000 | 0.776 | 0.745 | 0.820 | 0.781 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.448; r at lag 0 = 0.398) → leads by 1 day(s)
- **log**: best lag +1 (r=0.408; r at lag 0 = 0.363) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.206; r at lag 0 = 0.142) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.099; r at lag 0 = -0.040) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0084; the reverse raises R² by 0.0018.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.342 | 0.324 | 0.085 | 0.030 |
| -4 | 0.349 | 0.314 | 0.072 | -0.041 |
| -3 | 0.361 | 0.342 | 0.113 | 0.014 |
| -2 | 0.379 | 0.357 | 0.135 | 0.015 |
| -1 | 0.389 | 0.357 | 0.134 | -0.006 |
| 0 | 0.398 | 0.363 | 0.142 | -0.040 |
| 1 | 0.448 | 0.408 | 0.206 | 0.099 |
| 2 | 0.387 | 0.358 | 0.133 | -0.037 |
| 3 | 0.385 | 0.342 | 0.111 | -0.029 |
| 4 | 0.380 | 0.355 | 0.128 | 0.019 |
| 5 | 0.389 | 0.349 | 0.120 | -0.005 |


## tension_index_acts vs GPRD_ACT_SA

Sample: 2019-09-22 to 2026-10-26, 2570 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 2570.000 | 0.260 | 0.359 | 0.332 | 0.347 |
| daily_dow_adj | 2570.000 | 0.260 | 0.360 | 0.333 | 0.351 |
| weekly | 370.000 | 0.383 | 0.556 | 0.569 | 0.582 |
| monthly | 86.000 | 0.562 | 0.652 | 0.765 | 0.772 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.265; r at lag 0 = 0.260) → matches
- **log**: best lag +1 (r=0.335; r at lag 0 = 0.332) → matches
- **detrend**: best lag +1 (r=0.170; r at lag 0 = 0.166) → matches
- **diff**: best lag -3 (r=0.044; r at lag 0 = 0.031) → lags by 3 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0062; the reverse raises R² by 0.0019.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.147 | 0.245 | 0.035 | -0.007 |
| -4 | 0.156 | 0.250 | 0.041 | -0.026 |
| -3 | 0.173 | 0.280 | 0.085 | 0.044 |
| -2 | 0.163 | 0.269 | 0.071 | -0.046 |
| -1 | 0.200 | 0.301 | 0.120 | 0.000 |
| 0 | 0.260 | 0.332 | 0.166 | 0.031 |
| 1 | 0.265 | 0.335 | 0.170 | 0.012 |
| 2 | 0.236 | 0.326 | 0.157 | 0.030 |
| 3 | 0.200 | 0.290 | 0.106 | -0.043 |
| 4 | 0.204 | 0.294 | 0.112 | 0.010 |
| 5 | 0.178 | 0.288 | 0.100 | -0.006 |


## idx_headline vs GPRD_SA

Sample: 2019-09-22 to 2026-10-26, 2570 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 2570.000 | 0.406 | 0.427 | 0.421 | 0.426 |
| daily_dow_adj | 2570.000 | 0.407 | 0.428 | 0.422 | 0.428 |
| weekly | 370.000 | 0.648 | 0.665 | 0.702 | 0.698 |
| monthly | 86.000 | 0.809 | 0.793 | 0.865 | 0.852 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.433; r at lag 0 = 0.406) → leads by 1 day(s)
- **log**: best lag +1 (r=0.450; r at lag 0 = 0.421) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.209; r at lag 0 = 0.165) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.082; r at lag 0 = 0.006) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0103; the reverse raises R² by 0.0025.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.317 | 0.347 | 0.050 | -0.017 |
| -4 | 0.330 | 0.360 | 0.070 | -0.023 |
| -3 | 0.357 | 0.392 | 0.122 | 0.060 |
| -2 | 0.347 | 0.375 | 0.095 | -0.037 |
| -1 | 0.367 | 0.388 | 0.113 | -0.025 |
| 0 | 0.406 | 0.421 | 0.165 | 0.006 |
| 1 | 0.433 | 0.450 | 0.209 | 0.082 |
| 2 | 0.391 | 0.410 | 0.149 | -0.054 |
| 3 | 0.388 | 0.416 | 0.157 | 0.033 |
| 4 | 0.383 | 0.394 | 0.124 | -0.010 |
| 5 | 0.358 | 0.380 | 0.101 | -0.033 |


## idx_headline_and vs GPRD_SA

Sample: 2019-09-22 to 2026-10-26, 2570 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 2570.000 | 0.497 | 0.491 | 0.486 | 0.491 |
| daily_dow_adj | 2570.000 | 0.497 | 0.493 | 0.486 | 0.492 |
| weekly | 370.000 | 0.744 | 0.726 | 0.766 | 0.754 |
| monthly | 86.000 | 0.858 | 0.840 | 0.894 | 0.894 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.518; r at lag 0 = 0.497) → leads by 1 day(s)
- **log**: best lag +1 (r=0.510; r at lag 0 = 0.486) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.240; r at lag 0 = 0.200) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.094; r at lag 0 = 0.009) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0116; the reverse raises R² by 0.0032.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.393 | 0.405 | 0.069 | -0.028 |
| -4 | 0.405 | 0.423 | 0.097 | -0.013 |
| -3 | 0.434 | 0.451 | 0.145 | 0.060 |
| -2 | 0.425 | 0.433 | 0.117 | -0.052 |
| -1 | 0.464 | 0.455 | 0.151 | -0.012 |
| 0 | 0.497 | 0.486 | 0.200 | 0.009 |
| 1 | 0.518 | 0.510 | 0.240 | 0.094 |
| 2 | 0.469 | 0.462 | 0.163 | -0.070 |
| 3 | 0.466 | 0.468 | 0.172 | 0.016 |
| 4 | 0.470 | 0.460 | 0.159 | 0.010 |
| 5 | 0.445 | 0.446 | 0.136 | -0.027 |


## idx_headline_topic vs GPRD_SA

Sample: 2019-09-22 to 2026-10-26, 2570 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 2570.000 | 0.675 | 0.589 | 0.597 | 0.590 |
| daily_dow_adj | 2570.000 | 0.675 | 0.590 | 0.597 | 0.590 |
| weekly | 370.000 | 0.855 | 0.820 | 0.823 | 0.826 |
| monthly | 86.000 | 0.903 | 0.908 | 0.884 | 0.912 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.686; r at lag 0 = 0.675) → leads by 1 day(s)
- **log**: best lag +1 (r=0.616; r at lag 0 = 0.597) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.333; r at lag 0 = 0.295) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.093; r at lag 0 = 0.019) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0170; the reverse raises R² by 0.0049.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.577 | 0.520 | 0.137 | -0.052 |
| -4 | 0.603 | 0.551 | 0.200 | 0.031 |
| -3 | 0.629 | 0.564 | 0.224 | 0.008 |
| -2 | 0.636 | 0.573 | 0.246 | 0.027 |
| -1 | 0.652 | 0.567 | 0.235 | -0.063 |
| 0 | 0.675 | 0.597 | 0.295 | 0.019 |
| 1 | 0.686 | 0.616 | 0.333 | 0.093 |
| 2 | 0.647 | 0.583 | 0.268 | -0.056 |
| 3 | 0.630 | 0.581 | 0.266 | 0.030 |
| 4 | 0.618 | 0.563 | 0.230 | -0.018 |
| 5 | 0.598 | 0.555 | 0.214 | 0.014 |


## idx_theme vs GPRD_SA

Sample: 2015-02-19 to 2026-10-26, 4244 overlapping days.

### Correlation by frequency

| frequency | n | pearson_level | spearman_level | pearson_log | spearman_log |
|---|---|---|---|---|---|
| daily | 4244.000 | 0.443 | 0.340 | 0.388 | 0.340 |
| daily_dow_adj | 4244.000 | 0.447 | 0.344 | 0.390 | 0.343 |
| weekly | 609.000 | 0.580 | 0.462 | 0.550 | 0.464 |
| monthly | 141.000 | 0.584 | 0.473 | 0.565 | 0.470 |

### Lead/lag structure (daily)

Positive lag k means the tension index at day t is correlated with GPR at day t+k, i.e. the tension index leads.

- **level**: best lag +1 (r=0.473; r at lag 0 = 0.443) → leads by 1 day(s)
- **log**: best lag +1 (r=0.414; r at lag 0 = 0.388) → leads by 1 day(s)
- **detrend**: best lag +1 (r=0.326; r at lag 0 = 0.281) → leads by 1 day(s)
- **diff**: best lag +1 (r=0.083; r at lag 0 = 0.005) → leads by 1 day(s)

Predictive content on daily log changes (5 lags): adding tension-index lags to a regression of GPR on its own lags raises R² by 0.0216; the reverse raises R² by 0.0007.


Cross-correlation table (lags −5…+5, level / log / detrend / diff):

| lag | level | log | detrend | diff |
|---|---|---|---|---|
| -5 | 0.348 | 0.304 | 0.125 | -0.001 |
| -4 | 0.359 | 0.313 | 0.142 | -0.007 |
| -3 | 0.376 | 0.326 | 0.167 | 0.010 |
| -2 | 0.387 | 0.333 | 0.182 | -0.032 |
| -1 | 0.417 | 0.360 | 0.229 | -0.004 |
| 0 | 0.443 | 0.388 | 0.281 | 0.005 |
| 1 | 0.473 | 0.414 | 0.326 | 0.083 |
| 2 | 0.439 | 0.391 | 0.287 | 0.004 |
| 3 | 0.405 | 0.365 | 0.243 | -0.013 |
| 4 | 0.391 | 0.346 | 0.211 | -0.004 |
| 5 | 0.366 | 0.330 | 0.182 | -0.013 |
