"""
UCE authoritative cap/floor bounds for DQP (Batch 1 - Snippet 2).

Source of truth: the UCE bounds extract generated from UCE standardized
metadata (e.g. Changes/DQP_UCE_Bounds_Extract_v41_2026-11-01.csv). DQP does
not maintain its own cap/floor list.

Minimal integration:
- Bounds are loaded for one index vintage (e.g. 'EGDI_2024').
- A1 is only assigned for bound semantics whose bound is applied to the
  report value itself (RAW_PRETRANSFORM_CLIP, RAW_TRUNCATE), using the same
  test as the legacy A1 logic: data_report sits on the bound and the most
  recent historical value is beyond it.
- Calculation-stage bounds (SCORE_*) are only flagged (uce_beyond_bound),
  never turned into A1.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# UCE semantics whose bound is applied to the report/raw value
# (stage REPORT_VALUE in the Batch 1 regression runner).
A1_ELIGIBLE_SEMANTICS = {"RAW_PRETRANSFORM_CLIP", "RAW_TRUNCATE"}

UCE_BOUND_COLS = ["KPI ID", "uce_floor", "uce_cap", "uce_semantics", "uce_a1_eligible"]


def _norm_keyid(value) -> str:
    """KeyID/KPI ID as text: 271.0 -> '271', 'BTI_Q13F' unchanged."""
    s = str(value).strip()
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def empty_uce_bounds() -> pd.DataFrame:
    return pd.DataFrame(columns=UCE_BOUND_COLS)


def load_uce_bounds(
    csv_path: str | Path,
    vintage: str | None,
    a1_eligible_semantics: set[str] = A1_ELIGIBLE_SEMANTICS,
) -> pd.DataFrame:
    """Load UCE bounds for one vintage as one row per KPI.

    Parameters
    ----------
    csv_path : path to the UCE bounds extract CSV.
    vintage : UCE vintage code, e.g. 'EGDI_2024'. None returns an empty table.
    a1_eligible_semantics : uce_semantics values allowed to produce A1.

    Returns
    -------
    DataFrame with columns: KPI ID, uce_floor, uce_cap, uce_semantics,
    uce_a1_eligible (one row per KPI, so merges do not change row counts).
    """
    if vintage is None:
        return empty_uce_bounds()

    rules = pd.read_csv(csv_path, dtype={"KeyID": str})
    rules = rules[rules["vintage"] == vintage].copy()
    if rules.empty:
        return empty_uce_bounds()

    rules["KPI ID"] = rules["KeyID"].map(_norm_keyid)
    # The extract contains a few exact duplicate rules (e.g. EPI_2024 3214-3218).
    rules = rules.drop_duplicates(["KPI ID", "bound_type"])

    wide = rules.pivot(index="KPI ID", columns="bound_type", values="bound_value")
    wide = wide.rename(columns={"LOWER_FLOOR": "uce_floor", "UPPER_CAP": "uce_cap"})
    for col in ("uce_floor", "uce_cap"):
        if col not in wide.columns:
            wide[col] = np.nan

    semantics = rules.groupby("KPI ID")["uce_semantics"].agg(
        lambda s: "/".join(sorted(s.unique()))
    )
    out = wide[["uce_floor", "uce_cap"]].join(semantics).reset_index()
    out["uce_a1_eligible"] = out["uce_semantics"].isin(a1_eligible_semantics).astype(int)
    out.columns.name = None
    return out[UCE_BOUND_COLS]


def _on_bound(values: pd.Series, bound: pd.Series, tol: float = 1e-9) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce").astype(float)
    b = pd.to_numeric(bound, errors="coerce").astype(float)
    return ((v - b).abs() <= tol * np.maximum(1.0, b.abs())).fillna(False)


def uce_beyond_bound(df: pd.DataFrame, hist_col: str = "most_recent_data") -> pd.Series:
    """1 where the most recent historical value is above the cap or below the floor (any semantics)."""
    hist = pd.to_numeric(df[hist_col], errors="coerce").astype(float)
    cap = pd.to_numeric(df["uce_cap"], errors="coerce").astype(float)
    floor = pd.to_numeric(df["uce_floor"], errors="coerce").astype(float)
    beyond = (hist > cap).fillna(False) | (hist < floor).fillna(False)
    return beyond.astype(int)


def uce_a1_mask(
    df: pd.DataFrame,
    report_col: str = "data_report",
    hist_col: str = "most_recent_data",
) -> pd.Series:
    """A1 evidence from authoritative UCE bounds (report-value bounds only).

    Upper cap : data_report == uce_cap   and most_recent_data > uce_cap
    Lower floor: data_report == uce_floor and most_recent_data < uce_floor

    Evaluated independently of A/B matches so it can take precedence over them.
    """
    eligible = pd.to_numeric(df["uce_a1_eligible"], errors="coerce").fillna(0).eq(1)
    hist = pd.to_numeric(df[hist_col], errors="coerce").astype(float)
    cap = pd.to_numeric(df["uce_cap"], errors="coerce").astype(float)
    floor = pd.to_numeric(df["uce_floor"], errors="coerce").astype(float)

    capped = _on_bound(df[report_col], cap) & (hist > cap).fillna(False)
    floored = _on_bound(df[report_col], floor) & (hist < floor).fillna(False)
    return (eligible & (capped | floored)).fillna(False)
