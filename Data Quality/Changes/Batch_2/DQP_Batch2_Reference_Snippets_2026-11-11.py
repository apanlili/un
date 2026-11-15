from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# SNIPPET 1 — COUNTRY-CODE AUDIT AFTER THE UNIVERSAL PRE-CHECK
# -----------------------------------------------------------------------------

def country_presence_audit(
    simulator: pd.DataFrame,
    historical: pd.DataFrame,
    iso_col: str = "ISO",
    canonical_codes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Compare country coverage in both directions after canonical ISO reconciliation.

    The universal pre-check remains responsible for aliases such as PES→PSE or
    TZN→TZA and for rejecting ambiguous/unrecognised codes. Alfonso should not
    duplicate that mapping logic. This audit is the persistent evidence table
    that should be saved with the DQP output.
    """
    sim_codes = set(simulator[iso_col].dropna().astype(str).str.strip().str.upper())
    hist_codes = set(historical[iso_col].dropna().astype(str).str.strip().str.upper())
    all_codes = sorted(sim_codes | hist_codes)
    canonical = None if canonical_codes is None else {str(x).strip().upper() for x in canonical_codes}

    rows = []
    for iso in all_codes:
        in_sim = iso in sim_codes
        in_hist = iso in hist_codes
        if in_sim and in_hist:
            status = "BOTH"
        elif in_sim:
            status = "SIMULATOR_ONLY"
        else:
            status = "HISTORICAL_ONLY"
        rows.append({
            "ISO": iso,
            "in_simulator": in_sim,
            "in_historical": in_hist,
            "presence_status": status,
            "canonical_iso_status": (
                "NOT_CHECKED" if canonical is None else ("VALID" if iso in canonical else "UNKNOWN")
            ),
        })
    return pd.DataFrame(rows)


def country_audit_summary(audit: pd.DataFrame) -> dict[str, int]:
    counts = audit["presence_status"].value_counts().to_dict() if len(audit) else {}
    return {
        "both": int(counts.get("BOTH", 0)),
        "simulator_only": int(counts.get("SIMULATOR_ONLY", 0)),
        "historical_only": int(counts.get("HISTORICAL_ONLY", 0)),
        "unknown_canonical": int((audit.get("canonical_iso_status") == "UNKNOWN").sum()) if len(audit) else 0,
    }


# -----------------------------------------------------------------------------
# SNIPPET 2 — USER-FACING PERCENTAGES ARE ALWAYS 0–100
# -----------------------------------------------------------------------------

def profile_quality_summary_table_pct100(
    metadata: pd.DataFrame,
    quality_cols: list[str],
    groupby: str | list[str],
    pct_only: bool = False,
) -> pd.DataFrame:
    """Grouped DQP summary with percentage columns on a 0–100 scale.

    This is the corrected equivalent of Alfonso's current grouped profile
    function, which labels columns '(%)' but stores fractions such as 0.61.
    """
    groupby_cols = [groupby] if isinstance(groupby, str) else list(groupby)
    out = metadata.groupby(groupby_cols, dropna=False)[quality_cols].sum().reset_index()
    out["Total"] = out[quality_cols].sum(axis=1)
    denom = out["Total"].replace(0, np.nan)
    for col in quality_cols:
        out[col + " (%)"] = (out[col] / denom * 100).fillna(0).round(2)
    if pct_only:
        return out[groupby_cols + [col + " (%)" for col in quality_cols]]
    return out


def summary_by_group_pct100(
    metadata: pd.DataFrame,
    quality_cols: list[str],
    groupby: str,
) -> pd.DataFrame:
    """Correct the current `_pct` grouped summaries to a 0–100 scale."""
    out = metadata.groupby(groupby, dropna=False)[quality_cols].sum().reset_index()
    out["Total"] = out[quality_cols].sum(axis=1)
    denom = out["Total"].replace(0, np.nan)
    for col in quality_cols:
        out[col + "_pct"] = (out[col] / denom * 100).fillna(0).round(2)
    return out


def prepare_metadata_export_percentages(metadata: pd.DataFrame) -> pd.DataFrame:
    """Make the ratio/percentage distinction explicit in the exported workbook.

    Internal matching may keep the historical name
    `value_difference_percentage_inferred` for backward compatibility. The
    user-facing export should not show a ratio under a percentage label.
    """
    out = metadata.copy()
    src = "value_difference_percentage_inferred"
    if src in out.columns:
        ratio = pd.to_numeric(out[src], errors="coerce")
        out = out.rename(columns={src: "value_difference_ratio_inferred"})
        out["value_difference_pct_inferred"] = (ratio * 100).round(2)
    return out


def assert_pct100_columns(df: pd.DataFrame, pct_suffix: str = " (%)", tolerance: float = 0.02) -> None:
    pct_cols = [c for c in df.columns if c.endswith(pct_suffix)]
    if not pct_cols:
        raise AssertionError("No percentage columns found")
    vals = df[pct_cols].apply(pd.to_numeric, errors="coerce")
    if ((vals < -tolerance) | (vals > 100 + tolerance)).any().any():
        raise AssertionError("A user-facing percentage is outside 0–100")
    sums = vals.sum(axis=1)
    # Rows with at least one classified record should sum to ~100.
    active = vals.notna().any(axis=1)
    if active.any() and not np.allclose(sums[active], 100.0, atol=0.15):
        raise AssertionError("Grouped category percentages do not sum to 100")


# -----------------------------------------------------------------------------
# SNIPPET 3 — EXPLICIT COUNTRY COVERAGE (outlier detection unchanged)
# -----------------------------------------------------------------------------

def build_profile_coverage_table(
    metadata: pd.DataFrame,
    requested_isos: Iterable[str],
    iso_col: str = "ISO",
) -> pd.DataFrame:
    """Return one explicit coverage status for every requested country."""
    available = set(metadata[iso_col].dropna().astype(str).str.strip().str.upper())
    rows = []
    for iso in requested_isos:
        code = str(iso).strip().upper()
        rows.append({
            "ISO": code,
            "profile_status": (
                "AVAILABLE" if code in available else "NOT_COVERED_BY_INDEX_EDITION"
            ),
        })
    return pd.DataFrame(rows)


def profile_isos_to_generate(coverage: pd.DataFrame) -> list[str]:
    """Generate country sheets only where the index edition actually has rows."""
    return coverage.loc[coverage["profile_status"].eq("AVAILABLE"), "ISO"].tolist()


def coverage_patch_instructions() -> list[str]:
    """Machine-readable description of the coverage change. Outlier detection is not changed."""
    return [
        "Before writing country profiles, build and save a Coverage table for all requested countries.",
        "Generate a country sheet only for profile_status=AVAILABLE.",
        "If an unavailable country is requested, return NOT_COVERED_BY_INDEX_EDITION rather than an empty/broken profile.",
        "In the existing writer, replace the latent `country` variable in the skip message with `country_iso`.",
    ]
