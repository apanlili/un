import pandas as pd
import numpy as np
from pathlib import Path
from scipy.optimize import curve_fit


# ---------------------------------------------------------------------------
# 1. Trend-fitting helpers
# ---------------------------------------------------------------------------
def logistic(t, L, k, t0, b):
    return b + L / (1 + np.exp(-k * (t - t0)))


def modified_zscore(x):
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        mad = np.mean(np.abs(x - med))
    if mad == 0:
        return np.zeros_like(x), 0.0
    z = 0.6745 * (x - med) / mad
    return z, mad


def robust_logistic_fit(t, y):
    """Fit logistic curve; one round of MAD-based downweighting, refit.
    Returns fitted values over t, or None if fit fails."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    L0 = max(y.max() - y.min(), 1e-3)
    b0 = y.min()
    t0_0 = t[np.argmin(np.abs(y - (y.min() + y.max()) / 2))]
    k0 = 4.0 / (t.max() - t.min() + 1e-6)
    p0 = [L0, k0, t0_0, b0]
    bounds = (
        [0, -5, t.min() - 30, -np.inf],
        [L0 * 5 + 1e-6, 5, t.max() + 30, np.inf],
    )
    try:
        popt, _ = curve_fit(logistic, t, y, p0=p0, bounds=bounds, maxfev=20000)
    except Exception:
        return None

    fitted = logistic(t, *popt)
    resid = y - fitted
    z, mad = modified_zscore(resid)
    keep = np.abs(z) <= 3.0
    if keep.sum() >= 5 and keep.sum() < len(t):
        try:
            popt2, _ = curve_fit(logistic, t[keep], y[keep], p0=popt,
                                 bounds=bounds, maxfev=20000)
            fitted = logistic(t, *popt2)
        except Exception:
            pass
    return fitted


def diff_outlier_flags(years, values):
    """Flag abrupt jumps/drops in YoY change, plus a monotonicity check
    when the series is overwhelmingly non-decreasing."""
    n = len(values)
    flags = np.zeros(n, dtype=bool)
    if n < 3:
        return flags
    diffs = np.diff(values)
    year_gaps = np.diff(years)
    rate = diffs / year_gaps

    z, mad = modified_zscore(rate)

    val_range = max(np.nanmax(values) - np.nanmin(values), 1e-9)
    noise_floor = 0.015 * val_range
    material = np.abs(diffs) > noise_floor
    abrupt = (np.abs(z) > 3.5) & material

    frac_nonneg = np.mean(rate >= -1e-9)
    mono_flag = np.zeros(len(rate), dtype=bool)
    if frac_nonneg >= 0.8:
        tol = max(0.02 * val_range, 1e-6)
        mono_flag = rate < -tol

    step_flag = abrupt | mono_flag
    flags[1:] = step_flag
    return flags


# ---------------------------------------------------------------------------
# 2. Detector functions (applied to residuals, per group, below)
# ---------------------------------------------------------------------------
def detect_outliers_iqr_floored(series: pd.Series, multiplier: float = 3.5,
                                value_range: float = None,
                                floor_pct: float = 0.015) -> pd.Series:
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    flagged = (series < lower_bound) | (series > upper_bound)

    if value_range is not None:
        noise_floor = floor_pct * value_range
        material = series.abs() > noise_floor
        flagged = flagged & material

    return flagged


def detect_outliers_modified_zscore_floored(series: pd.Series, threshold: float = 3.5,
                                            value_range: float = None,
                                            floor_pct: float = 0.015) -> pd.Series:
    median = series.median()
    mad = np.median(np.abs(series - median))
    if mad == 0 or np.isnan(mad):
        return pd.Series(False, index=series.index)
    modified_z_scores = 0.6745 * (series - median) / mad
    flagged = np.abs(modified_z_scores) > threshold

    if value_range is not None:
        noise_floor = floor_pct * value_range
        material = series.abs() > noise_floor
        flagged = flagged & material

    return flagged


def detect_outliers_isolation_forest(series: pd.Series,
                                     contamination: float = 0.05) -> pd.Series:
    from sklearn.ensemble import IsolationForest
    s_num = pd.to_numeric(series, errors="coerce")
    notna_pos = np.flatnonzero(~s_num.isna())
    if len(notna_pos) < 30:
        return pd.Series(False, index=series.index)
    X = s_num.iloc[notna_pos].to_numpy().reshape(-1, 1)
    iso = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=200,
        max_samples="auto",
    )
    pred = iso.fit_predict(X)  # 1=inlier, -1=outlier
    mask = pd.Series(False, index=series.index)
    mask.iloc[notna_pos] = (pred == -1)
    return mask


# ---------------------------------------------------------------------------
# 3. Main entry point
# ---------------------------------------------------------------------------
NUMERIC_NEW_COLS = [
    "fitted_trend", "trend_r2", "logistic_r2", "resid",
    "outlier_iqr", "outlier_zscore", "outlier_isoforest",
    "outlier_diff", "outlier_total",
]
STRING_NEW_COLS = ["trend_method", "trend_fallback_reason"]


def detect_outliers_by_series(
    df: pd.DataFrame,
    group_cols: list = ["KPI ID", "ISO"],
    year_col: str = "year_historical_automated",
    value_col: str = "data_historical_automated",
    iqr_multiplier: float = 3.5,
    zscore_threshold: float = 3.5,
    isoforest_contamination: float = 0.05,
    rolling_window_years: int = 5,
    r2_threshold: float = 0.85,
    noise_floor_pct: float = 0.015,
    min_points_logistic: int = 8,
    min_points_rolling: int = 5,
) -> pd.DataFrame:
    """
    Detect outliers per (group_cols) time series, e.g. per (KPI ID, ISO).

    Preserves the original dataframe's shape exactly -- rows with missing
    year/value are kept, they just get NaN/NA in the outlier/trend columns.

    Returns a new dataframe with the same rows as `df` plus:
        fitted_trend, trend_r2, logistic_r2, resid,
        trend_method, trend_fallback_reason,
        outlier_iqr, outlier_zscore, outlier_isoforest, outlier_diff,
        outlier_total

    trend_method values
    -------------------
    'logistic'        robust logistic fit accepted (logistic_r2 >= r2_threshold)
    'rolling_median'  centred rolling median over `rolling_window_years`
    'median'          flat median (fewer than min_points_rolling points)

    trend_fallback_reason values (NA when trend_method == 'logistic')
    -----------------------------------------------------------------
    'too_few_points'   n < min_points_logistic, logistic never attempted
    'fit_failed'       curve_fit raised / did not converge
    'low_r2'           logistic converged but fell below r2_threshold
    'constant_series'  zero total variance, R^2 undefined

    Note: trend_r2 is not comparable across methods. For 'rolling_median' and
    'median' it scores a smoother against the data it smoothed, so it is high
    almost by construction. Filter or compare within trend_method groups.
    """
    df = df.reset_index(drop=True).copy()
    df["_orig_row_"] = df.index

    def rolling_median_by_year(t, y, window_years=rolling_window_years):
        t = np.asarray(t, dtype=float)
        y = np.asarray(y, dtype=float)
        out = np.empty(len(y))
        for i, yr in enumerate(t):
            mask = np.abs(t - yr) <= window_years / 2
            out[i] = np.median(y[mask])
        return out

    out_frames = []
    for _keys, g in df.groupby(group_cols, sort=False, dropna=False):
        g = g.sort_values(year_col).copy()
        for c in NUMERIC_NEW_COLS:
            g[c] = np.nan
        for c in STRING_NEW_COLS:
            g[c] = pd.Series(pd.NA, index=g.index, dtype="object")

        valid = g[[year_col, value_col]].notna().all(axis=1)
        n = int(valid.sum())

        if n == 0:
            out_frames.append(g)
            continue

        v_idx = g.index[valid]
        t = pd.to_numeric(g.loc[v_idx, year_col], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(g.loc[v_idx, value_col], errors="coerce").to_numpy(dtype=float)

        val_range = max(np.nanmax(y) - np.nanmin(y), 1e-9)

        # --- trend fitting, with method provenance --------------------------
        fitted = None
        r2 = np.nan
        logistic_r2 = np.nan
        method = None
        reason = None

        if n < min_points_logistic:
            reason = "too_few_points"
        else:
            candidate = robust_logistic_fit(t, y)
            if candidate is None:
                reason = "fit_failed"
            else:
                ss_res = np.sum((y - candidate) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                if ss_tot <= 0:
                    logistic_r2 = np.nan
                    reason = "constant_series"
                else:
                    logistic_r2 = 1 - ss_res / ss_tot
                    if logistic_r2 >= r2_threshold:
                        fitted = candidate
                        r2 = logistic_r2
                        method = "logistic"
                    else:
                        reason = "low_r2"

        if fitted is None:
            if n >= min_points_rolling:
                fitted = rolling_median_by_year(t, y)
                method = "rolling_median"
            else:
                fitted = np.full(n, np.median(y))
                method = "median"
            ss_res = np.sum((y - fitted) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

        # --- residual-based detectors ---------------------------------------
        resid = pd.Series(y - fitted, index=v_idx, dtype="float64")

        outlier_iqr = (
            detect_outliers_iqr_floored(resid, multiplier=iqr_multiplier,
                                        value_range=val_range,
                                        floor_pct=noise_floor_pct)
            if n >= 4 else pd.Series(False, index=v_idx)
        )
        outlier_zscore = (
            detect_outliers_modified_zscore_floored(resid, threshold=zscore_threshold,
                                                    value_range=val_range,
                                                    floor_pct=noise_floor_pct)
            if n >= 4 else pd.Series(False, index=v_idx)
        )
        outlier_isoforest = detect_outliers_isolation_forest(
            resid, contamination=isoforest_contamination)
        outlier_isoforest = pd.Series(np.asarray(outlier_isoforest).astype(bool),
                                      index=v_idx)
        outlier_diff = pd.Series(np.asarray(diff_outlier_flags(t, y)).astype(bool),
                                 index=v_idx)

        # --- write back -----------------------------------------------------
        g.loc[v_idx, "fitted_trend"] = np.round(fitted, 4)
        g.loc[v_idx, "trend_r2"] = np.round(r2, 4)
        g.loc[v_idx, "logistic_r2"] = np.round(logistic_r2, 4)
        g.loc[v_idx, "resid"] = np.round(resid.values, 4)
        g.loc[v_idx, "trend_method"] = method
        g.loc[v_idx, "trend_fallback_reason"] = reason if reason is not None else pd.NA
        g.loc[v_idx, "outlier_iqr"] = outlier_iqr.astype(int).values
        g.loc[v_idx, "outlier_zscore"] = outlier_zscore.astype(int).values
        g.loc[v_idx, "outlier_isoforest"] = outlier_isoforest.astype(int).values
        g.loc[v_idx, "outlier_diff"] = outlier_diff.astype(int).values
        g.loc[v_idx, "outlier_total"] = (g.loc[v_idx, "outlier_iqr"]
                                         + g.loc[v_idx, "outlier_zscore"]
                                         + g.loc[v_idx, "outlier_isoforest"]
                                         + g.loc[v_idx, "outlier_diff"])
        out_frames.append(g)

    result = pd.concat(out_frames)
    result = (result.sort_values("_orig_row_")
                    .drop(columns="_orig_row_")
                    .reset_index(drop=True))
    result["trend_method"] = result["trend_method"].astype("string")
    result["trend_fallback_reason"] = result["trend_fallback_reason"].astype("string")
    return result


# ---------------------------------------------------------------------------
# 4. Diagnostics
# ---------------------------------------------------------------------------
def trend_method_summary(result: pd.DataFrame,
                         group_cols: list = ["KPI ID", "ISO"]) -> pd.DataFrame:
    """One row per trend_method: how many series used it, and the flag rate
    among the points it produced. Use this to check whether flags are being
    driven by fit method rather than by the data."""
    scored = result[result["trend_method"].notna()]
    per_series = scored.groupby(group_cols, dropna=False).agg(
        trend_method=("trend_method", "first"),
        reason=("trend_fallback_reason", "first"),
        n_points=("resid", "size"),
    )
    counts = per_series.groupby("trend_method", dropna=False).agg(
        n_series=("n_points", "size"),
        median_points=("n_points", "median"),
    )
    rates = scored.groupby("trend_method", dropna=False).agg(
        n_points=("resid", "size"),
        pct_any_flag=("outlier_total", lambda s: 100 * (s > 0).mean()),
        pct_two_plus=("outlier_total", lambda s: 100 * (s >= 2).mean()),
        pct_iqr=("outlier_iqr", lambda s: 100 * s.mean()),
        pct_zscore=("outlier_zscore", lambda s: 100 * s.mean()),
        pct_isoforest=("outlier_isoforest", lambda s: 100 * s.mean()),
        pct_diff=("outlier_diff", lambda s: 100 * s.mean()),
    )
    return counts.join(rates).round(2)


def fallback_reason_summary(result: pd.DataFrame,
                            group_cols: list = ["KPI ID", "ISO"]) -> pd.Series:
    """Count of series by why the logistic fit was not used."""
    scored = result[result["trend_method"].notna()]
    per_series = scored.groupby(group_cols, dropna=False)["trend_fallback_reason"].first()
    return per_series.value_counts(dropna=False)