# Historical KPI outlier detection — method reference

How `detect_outliers_by_series` decides what "normal" looks like for each series, and how it decides which points depart from it.

Everything below operates on one group at a time. A group is one `(KPI ID, ISO)` pair — one indicator for one country — sorted by year. `n` throughout means the number of rows in that group where **both** the year and the value are non-null. Rows missing either are carried through to the output untouched, with `NA` in every new column.

---

## Stage 1 — choose a baseline

The detectors need something to measure against. Three baselines are available, chosen by three gates checked in order.

```
                    Series group
                 (n valid year+value rows)
                            |
                            v
                       n >= 8 ?  ----- no ----+
                            | yes             |
                            v                 |
                logistic converged ?  -- no --+
                            | yes             |
                            v                 |
                    r2 >= 0.85 ?  ----- no ---+
                            | yes             |
                            v                 v
                       [ logistic ]     n >= 5 ?
                                         |      |
                                       yes      no
                                         |      |
                                         v      v
                             [ rolling_median ] [ median ]
```

Because the two point thresholds are 8 and 5, `median` is only reachable when `n <= 4`. Every failure on a longer series — no convergence, poor fit, constant values — lands on `rolling_median`.

### logistic

The four-parameter curve `b + L / (1 + exp(-k(t - t0)))`, where `L` is the range covered, `k` the steepness, `t0` the midpoint year, and `b` the floor. Chosen because most development indicators saturate: literacy, electrification, immunisation coverage all rise toward a ceiling rather than trending forever.

Fitted twice. The first pass uses all points. Residuals are scored with a modified z-score, points above `|z| = 3` are dropped, and the curve is refit on what remains (only if at least five points survive and at least one was dropped). This second pass is what makes the curve usable as an outlier baseline — a single bad observation can otherwise drag the fit toward itself and mask its own residual.

Accepted only if `r2 >= r2_threshold` (0.85). The candidate's score is retained in `logistic_r2` even when rejected, so you can see whether a series missed narrowly or failed badly.

### rolling_median

A centred median over a window measured **in years**, not row positions:

```python
mask = np.abs(t - yr) <= window_years / 2
out[i] = np.median(y[mask])
```

Gaps in the year sequence are handled correctly — a series missing 2007 doesn't silently shift its window. But nothing is fitted. This is a smoother that follows whatever the data does.

Two consequences worth holding onto. A single-year spike survives, because one point can't move the median of five. A **sustained** shift over two or three years inside a five-year window becomes the median, so the residual collapses to near zero and the break disappears. And at the series endpoints the window is one-sided, so the first and last observations are smoothed over roughly half as many points — anomalies there are more likely to become their own baseline.

### median

A flat line at `np.median(y)`. On any short series with a real trend, the first and last points show large residuals purely because of the slope, not because anything is wrong with them. Treat flags from `median`-baseline series as unreliable.

### Why the baseline choice matters downstream

`trend_r2` is **not comparable across methods**. For `logistic` it scores a parametric fit. For `rolling_median` and `median` it scores a smoother against the data it just smoothed, so it is high almost by construction. Filtering on `trend_r2 > 0.9` across the whole result set mixes two incompatible quantities.

More importantly, the baseline changes what the detectors can see. A logistic baseline is rigid, so a genuine break produces a large residual. A rolling-median baseline bends to absorb that same break. Same anomaly, opposite outcome, decided by whether the series happened to clear 0.85.

`trend_method_summary(result)` breaks flag rates down by baseline. If the three methods show very different flag rates, that difference is the fitting stage, not the data.

---

## Stage 2 — the four detectors

```
        resid = y - fitted                    raw series
      (per-point deviation)                (values in year order)
        |        |        |                          |
        v        v        v                          v
   [IQR test] [Mod. z] [Iso forest]              [YoY diff]
        |        |        |                          |
        +--------+--------+--------------------------+
                            |
                            v
                      outlier_total
```

Three detectors ask "how far is this point from the baseline?" The fourth ignores the baseline entirely and asks "how does this point relate to its neighbours?"

Each writes a 0/1 column, and `outlier_total` is their sum.

---

### 1. `outlier_iqr` — interquartile range on the residuals

**What it asks.** Is this residual outside the bulk of the other residuals in this series?

**How.** Compute Q1 and Q3 of the residual vector, take `IQR = Q3 - Q1`, and flag anything outside `[Q1 - 3.5·IQR, Q3 + 3.5·IQR]`. The multiplier of 3.5 is much wider than the textbook 1.5 — deliberately, because a well-fitting logistic already leaves small residuals and you only want to catch conspicuous departures.

**Then the noise floor.** A statistical flag is discarded unless the residual also exceeds `0.015 × (series max - min)`. This is the important part. On a series that barely moves — a KPI already at 99%, or one flat for twenty years — the IQR is tiny and ordinary rounding noise sits far outside it. Without the floor, the cleanest series in the dataset generate the most flags.

**Strengths.** No distributional assumption. Robust: the quartiles aren't moved much by the outliers you're looking for.

**Weaknesses.** Needs a reasonable number of points for stable quartiles (gated at `n >= 4`, which is generous). Symmetric bounds, so it treats a large positive and large negative residual identically even when only one direction is plausible for the indicator.

---

### 2. `outlier_zscore` — modified z-score on the residuals

**What it asks.** The same question as the IQR test, with a different spread estimator.

**How.** Take the median of the residuals, then the median absolute deviation from it. The score is `0.6745 × (resid - median) / MAD`, flagged above 3.5. The 0.6745 factor rescales MAD so the result is comparable to a standard z-score on normally distributed data. The same 1.5% noise floor applies.

**Strengths.** MAD has a 50% breakdown point — half the data would have to be corrupt before the scale estimate is compromised. That's much stronger than a standard deviation, which a single extreme point inflates enough to hide itself.

**Weaknesses.** If MAD is exactly zero the detector returns all-False and contributes nothing. This happens more often than you'd expect: any series where more than half the residuals are identical, which includes short series sitting exactly on a flat baseline.

**Note on independence.** This and the IQR test are near-duplicates — both are robust location-and-scale tests on the same vector, differing only in estimator. A point that trips one usually trips the other. That means `outlier_total >= 2` is much closer in practice to `outlier_total >= 1` than the 0–4 range implies, and the score is not four independent votes.

---

### 3. `outlier_isoforest` — isolation forest on the residuals

**What it asks.** Nominally: how easy is this point to isolate by random splitting? An easily isolated point sits in a sparse region.

**How.** Fits `sklearn.ensemble.IsolationForest` with 200 trees to the residual vector reshaped to a single column, and takes `fit_predict == -1`.

**Two things that limit it in this pipeline.**

`contamination=0.05` is not a threshold, it's a quota. The estimator flags approximately 5% of points in *every* group it runs on, including perfectly clean series. It cannot return zero flags for a well-behaved series the way the other three can.

The `len(notna_pos) < 30` guard means it returns all-False for any group with fewer than 30 valid points. Annual series rarely reach that. **Check `result["outlier_isoforest"].sum()` — if it is zero, this detector is contributing nothing and `outlier_total` is effectively a 0–3 scale.**

It also has no noise floor, unlike the other two residual detectors.

**On one dimension it adds little.** Isolation depth on a single feature reduces to something close to a rank statistic, which the modified z-score already provides more transparently. If you keep it, consider thresholding `iso.score_samples()` at a fixed cutoff rather than using `fit_predict`, so it reports "nothing unusual here" when that's the truth.

---

### 4. `outlier_diff` — year-on-year change

**What it asks.** Not "how far from the trend?" but "how does this point relate to the one before it?" This is the only detector operating on the raw values rather than residuals, and the only one that can catch an anomaly the baseline has already absorbed.

**How.** Compute `rate = diff(values) / diff(years)` — per-year change, so uneven gaps are handled. Then two rules:

*Abrupt change.* A modified z-score on the rate vector, flagged above 3.5, gated by the same 1.5% materiality floor. This catches a value that jumps or drops far more sharply than the series normally moves.

*Monotonicity.* If at least 80% of the rates are non-negative, the series is treated as one that should only rise, and **any** decrease beyond a tolerance of 2% of the series range is flagged. This is the rule that catches a one-year dip in a cumulative or ratchet-like indicator — the kind of thing a smoother baseline would never surface.

**Strengths.** Genuinely different information from the three residual tests. Catches step changes and direction reversals regardless of how well the baseline fits.

**Weaknesses — two that will show up in your results.**

*Attribution is off by one for spikes.* `diffs[i] = values[i+1] - values[i]`, and `flags[1:] = step_flag` assigns every large change to the later index. A single spike produces two large rates of opposite sign, so the point after a spike gets flagged as well as the spike itself. In testing, one injected outlier produced flags on three consecutive rows despite the two neighbours having near-zero residuals against a well-fitting curve. The monotonicity rule is unaffected — there the later index really is the suspect.

*Duplicate years break it silently.* If a group contains two rows for the same year, `year_gaps` contains a zero, `rate` picks up `inf`, and the MAD calculation is poisoned. The detector then returns nothing for that group without raising an error — just a `RuntimeWarning`. Run `df.duplicated(subset=["KPI ID","ISO","year_historical_automated"]).sum()` before trusting these flags.

---

## Reading `outlier_total`

Range 0–4 in principle. In practice:

| Value | What it usually means |
|---|---|
| 0 | Nothing fired. On a `rolling_median` baseline this is weaker evidence than it looks. |
| 1 | Often `outlier_diff` alone — check whether it's the point *after* a spike. |
| 2 | Usually IQR + modified z, which are near-duplicates. Not two independent confirmations. |
| 3 | A residual outlier that is also a sharp local change. The strongest signal available. |
| 4 | Requires the isolation forest, so only possible on series with 30+ points. |

Two adjustments make the score more informative. Treat IQR and modified z as one vote rather than two, since they rarely disagree. And segment the review by `trend_method` before comparing counts, because `logistic`-baseline series are systematically more sensitive than `rolling_median` ones.

---

## Output columns

| Column | Meaning |
|---|---|
| `fitted_trend` | The baseline value at that point |
| `trend_method` | `logistic` / `rolling_median` / `median` |
| `trend_fallback_reason` | `too_few_points` / `fit_failed` / `low_r2` / `constant_series`; `NA` when the logistic was used |
| `trend_r2` | Fit quality — **only comparable within a `trend_method`** |
| `logistic_r2` | The logistic candidate's score, retained even when rejected |
| `resid` | `value - fitted_trend` |
| `outlier_iqr`, `outlier_zscore`, `outlier_isoforest`, `outlier_diff` | Individual 0/1 flags |
| `outlier_total` | Their sum |

Rows with a missing year or value are preserved in place with `NA` throughout — the function returns exactly as many rows as it received.

## Diagnostic helpers

`trend_method_summary(result)` — series counts and flag rates broken out by baseline. The first thing to run: if flag rates differ sharply across methods, the fitting stage is driving your results.

`fallback_reason_summary(result)` — how many series failed the logistic and why. A large `low_r2` bucket means either genuinely non-sigmoid indicators, or series so corrupted that the fit failed *because* of the outliers you're trying to find.
