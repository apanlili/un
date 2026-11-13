"""
Country (ISO) profile + country/KPI detail table for an index.

Layout
  1. Config           - column names, thresholds
  2. Small helpers    - validation, Index_ID handling
  3. KPI-level        - majority-years logic
  4. Country-level    - metadata cleaning, detail table, ISO profile
  5. Entry point      - get_profile_data_ispar

Moved here unchanged from the 'Country Profile Input into ISPAR' cell of the
Metadata Automation notebooks so the .py scripts can share it.
"""
from __future__ import annotations

import ast
import re
from typing import NamedTuple

import pandas as pd

# ===========================================================================
# 1. Config
# ===========================================================================
AVAILABLE_COLS = [
    "A_A1_B_match_total",
    "C_data_available_no_match",
    "D_possible_impute",
]
NO_MATCH_IMPUTE_COLS = ["C_data_available_no_match", "D_possible_impute"]
RECENT_COLS = ["A_total", "A1_cap_adjusted_match"]
OLD_COL = "B_total"
NOT_ASSESSED_COLS = ["E_no_historical_data", "F_no_report_data", "G_no_historical_and_report_data"]

MAJORITY_THRESHOLD = 50.0  # % cumulative share a set of years must exceed

METADATA_COLS = (
    ["Country", "ISO", "Series Name", "KPI ID", "year_inferred", OLD_COL]
    + AVAILABLE_COLS + RECENT_COLS + NOT_ASSESSED_COLS
)
KPI_STATS_COLS = ["KPI ID", "most_common_year", "most_common_year_pct", "year_max",
                  "majority_years", "majority_years_pct"]
COUNTRY_TBL_COLS = ["Country", "ISO", "Series Name", "KPI ID", "year_inferred", OLD_COL,
                    "most_common_year", "most_common_year_pct", "majority_years",
                    "majority_years_pct", "year_max", "year_difference",
                    "Conclusion", "Assessed"]

_INDEX_ID_PATTERN = re.compile(r"index_(\d+)", flags=re.IGNORECASE)


class ProfileResult(NamedTuple):
    """Still unpacks like a plain tuple: profile, country_data_tbl = ..."""
    profile: pd.DataFrame
    country_data_tbl: pd.DataFrame


# ===========================================================================
# 2. Small helpers
# ===========================================================================
def _require_columns(df: pd.DataFrame, cols, name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{name} is missing columns: {missing}")


def _clean_kpi_id(s: pd.Series) -> pd.Series:
    """KPI ID may be int in one table and str in the other -> compare as stripped str."""
    return s.astype(str).str.strip()


def extract_index_id(index_name: str) -> int:
    """'index_7' -> 7, 'index_32_2026' -> 32."""
    match = _INDEX_ID_PATTERN.search(str(index_name))
    if not match:
        raise ValueError(
            f"Could not extract an Index_ID from index_name={index_name!r}; "
            "expected something like 'index_7' or 'index_32_2026'."
        )
    return int(match.group(1))


def _prepend_index_id(df: pd.DataFrame, index_id: int) -> pd.DataFrame:
    """Return a copy of df with Index_ID as the first column."""
    out = df.copy()
    out.insert(0, "Index_ID", index_id)
    return out


# ===========================================================================
# 3. KPI-level: majority years
# ===========================================================================
def expand_year_distribution(dist, threshold: float = MAJORITY_THRESHOLD):
    """
    Expand a KPI's year distribution from the most common year outwards until
    the cumulative share exceeds `threshold` (%).

    Returns (NA, NA) when the single most common year is already above the
    threshold (no expansion needed) or the input can't be read.
    Years are ordered by share, highest first (ties -> more recent year first).
    Example: {2023: 37.4, 2022: 24.5, ...} -> ('2023-2022', '61.9%')
    """
    if isinstance(dist, str):  # dict stored as text (csv / excel)
        try:
            dist = ast.literal_eval(dist)
        except (ValueError, SyntaxError):
            return pd.NA, pd.NA
    if not isinstance(dist, dict) or not dist:
        return pd.NA, pd.NA

    ranked = sorted(dist.items(), key=lambda kv: (-float(kv[1]), -int(kv[0])))
    if float(ranked[0][1]) > threshold:
        return pd.NA, pd.NA

    years, cum = [], 0.0
    for year, pct in ranked:
        years.append(str(int(year)))
        cum += float(pct)
        if round(cum, 1) > threshold:
            break
    return "-".join(years), f"{cum:.1f}%"


def add_majority_years(kpi_data: pd.DataFrame, threshold: float = MAJORITY_THRESHOLD) -> pd.DataFrame:
    """Return a copy of kpi_data with 'majority_years' and 'majority_years_pct' added."""
    _require_columns(kpi_data, ["year_distribution"], "kpi_data")
    out = kpi_data.copy()
    expanded = out["year_distribution"].apply(expand_year_distribution, threshold=threshold)
    out["majority_years"] = expanded.apply(lambda t: t[0])
    out["majority_years_pct"] = expanded.apply(lambda t: t[1])
    return out


# ===========================================================================
# 4. Country-level
# ===========================================================================
def prepare_metadata(metadata_automated: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean metadata once, so the builders below can assume clean input."""
    _require_columns(metadata_automated, METADATA_COLS, "metadata_automated")
    meta = metadata_automated[METADATA_COLS].copy()

    num_cols = AVAILABLE_COLS + RECENT_COLS + NOT_ASSESSED_COLS + [OLD_COL]
    meta[num_cols] = meta[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    meta[OLD_COL] = meta[OLD_COL].astype(int)
    meta["KPI ID"] = _clean_kpi_id(meta["KPI ID"])
    return meta


def build_country_data_tbl(meta: pd.DataFrame, kpi_data: pd.DataFrame,
                           old_only: bool = True) -> pd.DataFrame:
    """
    One row per ISO x KPI with the matched year and how it compares to the
    KPI-level year statistics.

    `meta` is the output of prepare_metadata. kpi_data must contain
    KPI_STATS_COLS (see add_majority_years).

    old_only=True keeps only rows where B_total == 1; False keeps all rows,
    with B_total == 1 sorted first.

    Adds 'Conclusion' (f-string text per row) and 'Assessed' (always 1).
    """
    _require_columns(kpi_data, KPI_STATS_COLS, "kpi_data")

    tbl = meta[["Country", "ISO", "Series Name", "KPI ID", "year_inferred", OLD_COL]]
    if old_only:
        tbl = tbl[tbl[OLD_COL] == 1]

    lookup = kpi_data[KPI_STATS_COLS].copy()
    lookup["KPI ID"] = _clean_kpi_id(lookup["KPI ID"])

    tbl = tbl.merge(lookup.drop_duplicates("KPI ID"), how="left", on="KPI ID", validate="m:1")

    for col in ["year_inferred", "most_common_year", "year_max"]:
        tbl[col] = tbl[col].astype("Int64")
    tbl["year_difference"] = tbl["year_max"] - tbl["year_inferred"]

    # year_inferred is renamed to year_used by the caller, hence the wording
    tbl["Conclusion"] = [
        f"The source has no figure for {country} after {year_used}. "
        "A recent figure needs to be produced or transmitted to the source."
        for country, year_used in zip(tbl["Country"], tbl["year_inferred"])
    ]
    tbl["Assessed"] = 1

    return (
        tbl[COUNTRY_TBL_COLS]
        .sort_values(["ISO", "year_difference"], ascending=[True, True])
        .reset_index(drop=True)
    )


def build_iso_profile(meta: pd.DataFrame, country_data_tbl: pd.DataFrame) -> pd.DataFrame:
    """
    Per ISO (Country = first Country seen for that ISO):
      indicators_available    = sum of A_A1_B_match_total, C and D
      indicators_total        = unique KPI IDs
      indicators_recent       = A_total + A1_cap_adjusted_match
      indicators_old          = B_total
      indicators_no_match_imputation = C_data_available_no_match + D_possible_impute
      median_years_behind     = median year_difference over the ISO's Bucket B rows
      indicators_not_assessed = E_no_historical_data + F_no_report_data
                                + G_no_historical_and_report_data (last column)
    """
    profile = (
        meta.assign(_available=meta[AVAILABLE_COLS].sum(axis=1),
                    _recent=meta[RECENT_COLS].sum(axis=1),
                    _no_match_impute=meta[NO_MATCH_IMPUTE_COLS].sum(axis=1),
                    _not_assessed=meta[NOT_ASSESSED_COLS].sum(axis=1))
        .groupby("ISO")
        .agg(
            Country=("Country", "first"),
            indicators_available=("_available", "sum"),
            indicators_total=("KPI ID", "nunique"),
            indicators_recent=("_recent", "sum"),
            indicators_old=(OLD_COL, "sum"),
            indicators_no_match_imputation=("_no_match_impute", "sum"),
            indicators_not_assessed=("_not_assessed", "sum"),
        )
        .reset_index()
    )
    count_cols = [c for c in profile.columns if c not in ("Country", "ISO")]
    profile[count_cols] = profile[count_cols].astype(int)

    median_behind = (
        country_data_tbl[country_data_tbl[OLD_COL] == 1]
        .groupby("ISO")["year_difference"]
        .median()
        .rename("median_years_behind")
        .reset_index()
    )
    profile = profile.merge(median_behind, how="left", on="ISO")

    # Put indicators_not_assessed last
    # Put Country first (before ISO) and indicators_not_assessed last
    cols = [c for c in profile.columns if c not in ("Country", "ISO", "indicators_not_assessed")]
    return profile[["Country", "ISO"] + cols + ["indicators_not_assessed"]]


# ===========================================================================
# 5. Entry point
# ===========================================================================
def get_profile_data_ispar(metadata_automated: pd.DataFrame, kpi_data: pd.DataFrame,
                           index_name: str, old_only: bool = True,
                           threshold: float = MAJORITY_THRESHOLD) -> ProfileResult:
    """
    Returns (profile, country_data_tbl), both with Index_ID as the first column.

    index_name       : e.g. 'index_7' or 'index_32_2026'; the number right after
                       'index_' (7, 32) becomes Index_ID.
    profile          : per ISO counts + median_years_behind + indicators_not_assessed
    country_data_tbl : per ISO x KPI detail (see build_country_data_tbl)

    kpi_data needs: KPI ID, most_common_year, most_common_year_pct, year_max,
    year_distribution (majority_years are added here if not already present).
    """
    index_id = extract_index_id(index_name)  # fail fast on a bad name

    if "majority_years" not in kpi_data.columns:
        kpi_data = add_majority_years(kpi_data, threshold)

    meta = prepare_metadata(metadata_automated)
    country_data_tbl = build_country_data_tbl(meta, kpi_data, old_only=old_only)
    profile = build_iso_profile(meta, country_data_tbl)

    return ProfileResult(
        profile=_prepend_index_id(profile, index_id),
        country_data_tbl=_prepend_index_id(country_data_tbl, index_id),
    )
