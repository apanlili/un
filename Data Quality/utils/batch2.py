"""
DQP Batch 2 helpers (pipeline version 1.2).

Kept separate from the shared utils so the v1.0 (original) and v1.1 (Batch 1) outputs do not change.
Reference behaviour: Changes/Batch_2/DQP_Batch2_Reference_Snippets_2026-11-11.py

Snippet 1 (roadmap issue 8) - country-code audit in both directions:
- one row per ISO: in the simulator, in the historical file, or both; saved as 'Country code audit'.
- canonical_iso_status is VALID / UNKNOWN against a canonical country list when one is supplied,
  otherwise NOT_CHECKED. Alias mapping (e.g. PES -> PSE) stays in the upstream pre-check, not here.

Snippet 2 (roadmap issue 10) - percentages mean percentages:
- every user-facing column labelled % (or _pct) is on a 0-100 scale;
- the internal matching ratio keeps its name inside the pipeline; in the exported metadata sheet it is
  value_difference_ratio_inferred, with value_difference_pct_inferred = ratio x 100 next to it.

Snippet 3 (roadmap issue 11) - explicit country coverage:
- one status per requested country, AVAILABLE or NOT_COVERED_BY_INDEX_EDITION, saved as 'Country Profile Coverage';
- country profile sheets are generated only for AVAILABLE countries.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

AUDIT_SHEET = 'Country code audit'
COVERAGE_SHEET = 'Country Profile Coverage'
AVAILABLE = 'AVAILABLE'
NOT_COVERED = 'NOT_COVERED_BY_INDEX_EDITION'


# ---------------------------------------------------------------------------
# Snippet 1 - country-code audit
# ---------------------------------------------------------------------------
def _codes(df: pd.DataFrame, iso_col: str = 'ISO') -> set[str]:
    return set(df[iso_col].dropna().astype(str).str.strip().str.upper()) - {''}


def load_canonical_codes(path: str | Path | None, iso_col: str = 'ISO', sheet_name=0) -> set[str] | None:
    """Canonical ISO list from a file (csv/xlsx with an ISO column), or None when no file is given."""
    if path is None:
        return None
    path = Path(path)
    df = pd.read_csv(path) if path.suffix.lower() == '.csv' else pd.read_excel(path, sheet_name=sheet_name)
    return _codes(df, iso_col)


def country_presence_audit(simulator: pd.DataFrame, historical: pd.DataFrame,
                           canonical_codes: Iterable[str] | None = None,
                           names: dict[str, str] | None = None, iso_col: str = 'ISO') -> pd.DataFrame:
    """Country Profile Coverage in both directions (reference: country_presence_audit), plus the country name."""
    sim_codes, hist_codes = _codes(simulator, iso_col), _codes(historical, iso_col)
    canonical = None if canonical_codes is None else {str(x).strip().upper() for x in canonical_codes}
    rows = []
    for iso in sorted(sim_codes | hist_codes):
        in_sim, in_hist = iso in sim_codes, iso in hist_codes
        rows.append({
            'ISO': iso,
            'Country': (names or {}).get(iso),
            'in_simulator': in_sim,
            'in_historical': in_hist,
            'presence_status': 'BOTH' if in_sim and in_hist else ('SIMULATOR_ONLY' if in_sim else 'HISTORICAL_ONLY'),
            'canonical_iso_status': 'NOT_CHECKED' if canonical is None else ('VALID' if iso in canonical else 'UNKNOWN'),
        })
    cols = ['ISO', 'Country', 'in_simulator', 'in_historical', 'presence_status', 'canonical_iso_status']
    return pd.DataFrame(rows, columns=cols)


def country_audit_summary(audit: pd.DataFrame) -> dict[str, int]:
    counts = audit['presence_status'].value_counts().to_dict() if len(audit) else {}
    return {'both': int(counts.get('BOTH', 0)),
            'simulator_only': int(counts.get('SIMULATOR_ONLY', 0)),
            'historical_only': int(counts.get('HISTORICAL_ONLY', 0)),
            'unknown_canonical': int((audit['canonical_iso_status'] == 'UNKNOWN').sum()) if len(audit) else 0}


def print_country_audit(audit: pd.DataFrame) -> None:
    s = country_audit_summary(audit)
    sim_only = audit.loc[audit['presence_status'] == 'SIMULATOR_ONLY', 'ISO'].tolist()
    hist_only = audit.loc[audit['presence_status'] == 'HISTORICAL_ONLY', 'ISO'].tolist()
    print('=' * 60 + '\nCOUNTRY CODE AUDIT: simulator vs historical\n' + '=' * 60)
    print(f"Both: {s['both']}   Simulator only: {s['simulator_only']}   Historical only: {s['historical_only']}")
    if sim_only:
        print(f"   Simulator only:  {';'.join(sim_only)}")
    if hist_only:
        print(f"   Historical only: {';'.join(hist_only)}")
    if (audit['canonical_iso_status'] == 'NOT_CHECKED').all():
        print('   Canonical check: NOT_CHECKED (no canonical country list supplied)')
    else:
        print(f"   Codes outside the canonical list: {s['unknown_canonical']}")


# ---------------------------------------------------------------------------
# Snippet 3 - explicit country coverage
# ---------------------------------------------------------------------------
def build_profile_coverage_table(metadata: pd.DataFrame, requested_isos: Iterable[str],
                                 names: dict[str, str] | None = None, iso_col: str = 'ISO') -> pd.DataFrame:
    """One status per requested country: AVAILABLE if the index edition has rows for it, else NOT_COVERED."""
    available = _codes(metadata, iso_col)
    rows = []
    for iso in requested_isos:
        code = str(iso).strip().upper()
        rows.append({'ISO': code, 'Country': (names or {}).get(code),
                     'profile_status': AVAILABLE if code in available else NOT_COVERED})
    return pd.DataFrame(rows, columns=['ISO', 'Country', 'profile_status'])


def profile_isos_to_generate(coverage: pd.DataFrame) -> list[str]:
    """Country sheets are generated only for AVAILABLE countries."""
    return coverage.loc[coverage['profile_status'].eq(AVAILABLE), 'ISO'].tolist()


def print_coverage(coverage: pd.DataFrame) -> None:
    not_cov = coverage.loc[coverage['profile_status'] == NOT_COVERED, 'ISO'].tolist()
    print(f"Country Profile Coverage: {len(coverage) - len(not_cov)} of {len(coverage)} requested countries AVAILABLE"
          + (f"; {NOT_COVERED}: {', '.join(not_cov)}" if not_cov else ''))


def append_sheet(xlsx_path: str | Path, sheet_name: str, df: pd.DataFrame) -> None:
    """Add a sheet to an already written workbook (used for workbooks without images)."""
    with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='error') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        for col_letter, width in zip('ABCDEF', (8, 32, 14, 14, 18, 22)):
            ws.column_dimensions[col_letter].width = width

RATIO_COL = 'value_difference_percentage_inferred'          # internal name (unchanged, used by matching)
RATIO_EXPORT_COL = 'value_difference_ratio_inferred'
PCT_EXPORT_COL = 'value_difference_pct_inferred'


# ---------------------------------------------------------------------------
# Snippet 2 - percentages on a 0-100 scale
# ---------------------------------------------------------------------------
def pct100_columns(df: pd.DataFrame, quality_cols: list[str], suffix: str = '_pct') -> pd.DataFrame:
    """Recompute '<col><suffix>' as count / Total x 100 (0-100, 2 decimals).

    Used on the 'Summary Stats by KPI' / 'Summary Stats by Country' tables from get_summary_stats,
    which store fractions (0.96) in their _pct columns. Counts and Total are unchanged.
    """
    out = df.copy()
    denom = out['Total'].replace(0, np.nan)
    for col in quality_cols:
        out[col + suffix] = (out[col] / denom * 100).fillna(0).round(2)
    return out


def profile_quality_summary_table_pct100(metadata: pd.DataFrame, quality_cols: list[str],
                                         groupby: str | list[str], pct_only: bool = False) -> pd.DataFrame:
    """Grouped bucket summary with ' (%)' columns on a 0-100 scale.

    Corrected equivalent of formatting_functions.profile_quality_summary_table(groupby=...),
    which labels its columns '(%)' but stores fractions. Same as the Batch 2 reference function.
    """
    groupby_cols = [groupby] if isinstance(groupby, str) else list(groupby)
    out = metadata.groupby(groupby_cols, dropna=False)[quality_cols].sum().reset_index()
    out['Total'] = out[quality_cols].sum(axis=1)
    denom = out['Total'].replace(0, np.nan)
    for col in quality_cols:
        out[col + ' (%)'] = (out[col] / denom * 100).fillna(0).round(2)
    if pct_only:
        return out[groupby_cols + [col + ' (%)' for col in quality_cols]]
    return out


def prepare_metadata_export_percentages(metadata: pd.DataFrame) -> pd.DataFrame:
    """Exported metadata sheet: the matching ratio is labelled as a ratio, with a 0-100 percentage next to it.

    value_difference_percentage_inferred (a ratio, e.g. 0.0061)
      -> value_difference_ratio_inferred (0.0061) + value_difference_pct_inferred (0.61)
    The matching calculation itself is unchanged.
    """
    if RATIO_COL not in metadata.columns:
        return metadata.copy()
    out = metadata.rename(columns={RATIO_COL: RATIO_EXPORT_COL})
    pct = (pd.to_numeric(out[RATIO_EXPORT_COL], errors='coerce') * 100).round(2)
    out.insert(out.columns.get_loc(RATIO_EXPORT_COL) + 1, PCT_EXPORT_COL, pct)
    return out


def check_pct100(df: pd.DataFrame, pct_cols: list[str], name: str, tolerance: float = 0.15) -> None:
    """Print whether every % value is within 0-100 and each row of bucket %s sums to ~100."""
    vals = df[pct_cols].apply(pd.to_numeric, errors='coerce')
    in_range = bool(((vals >= -0.02) & (vals <= 100.02) | vals.isna()).all().all())
    sums = vals.sum(axis=1)
    active = vals.notna().any(axis=1) & (sums > 0)
    sums_ok = bool(np.allclose(sums[active], 100.0, atol=tolerance)) if active.any() else True
    mark = '✅' if in_range and sums_ok else '⚠️'
    print(f"{mark} {name}: % columns within 0-100: {in_range}; rows sum to ~100: {sums_ok}")
