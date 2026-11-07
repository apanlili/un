from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import json

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# SNIPPET 1 — sign/zero-safe numerical matching
# -----------------------------------------------------------------------------
def compute_match_gap(data_report: pd.Series, data_historical: pd.Series) -> pd.DataFrame:
    """Return exact-match and sign-safe relative-gap evidence.

    Rules:
    - Exact equality is exact, including 0 == 0.
    - Relative gap uses abs(report) as denominator, so negative values are symmetric.
    - A non-exact comparison with report == 0 has no percentage-based approximate gap.
      It therefore cannot become an approximate match until a reviewed absolute
      tolerance is supplied for that KPI.
    """
    report = pd.to_numeric(data_report, errors="coerce")
    hist = pd.to_numeric(data_historical, errors="coerce")
    diff = (report - hist).abs()
    exact = diff.eq(0) & report.notna() & hist.notna()
    denom = report.abs().replace(0, np.nan)
    rel_gap = np.where(exact, 0.0, diff / denom)
    return pd.DataFrame(
        {
            "value_difference": diff,
            "exact_match": exact,
            "value_difference_percentage": rel_gap,
        },
        index=report.index,
    )


def approximate_match_mask(match_evidence: pd.DataFrame, tolerance: float = 0.01) -> pd.Series:
    return (
        ~match_evidence["exact_match"]
        & pd.to_numeric(match_evidence["value_difference_percentage"], errors="coerce").le(tolerance)
    ).fillna(False)


# -----------------------------------------------------------------------------
# SNIPPET 2 — authoritative bound before final classification
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class BoundRule:
    kpi_id: str
    bound_type: str  # UPPER_CAP | LOWER_FLOOR
    bound_value: float
    bound_stage: str  # REPORT_VALUE | CALCULATION
    dqp_a1_eligible: bool = True
    rule_id: str | None = None


def apply_authoritative_bound(raw_values: pd.Series, rule: BoundRule) -> pd.DataFrame:
    """Preserve raw values and create comparison/calculation-space values.

    REPORT_VALUE: the bound changes the value that should be compared with the
    publisher/effective report value, so comparison_value is bounded first.

    CALCULATION: the report/raw observation remains unaltered for reconciliation;
    only calculation_value is bounded. This supports A1 without falsifying the
    raw-data comparison.
    """
    raw = pd.to_numeric(raw_values, errors="coerce")
    comparison = raw.copy()
    calculation = raw.copy()

    if rule.bound_type == "UPPER_CAP":
        beyond = raw.gt(rule.bound_value)
        bounded = raw.clip(upper=rule.bound_value)
    elif rule.bound_type == "LOWER_FLOOR":
        beyond = raw.lt(rule.bound_value)
        bounded = raw.clip(lower=rule.bound_value)
    else:
        raise ValueError(f"Unsupported bound_type: {rule.bound_type}")

    if rule.bound_stage == "REPORT_VALUE":
        comparison = bounded
        calculation = bounded
    elif rule.bound_stage == "CALCULATION":
        calculation = bounded
    else:
        raise ValueError(f"Unsupported bound_stage: {rule.bound_stage}")

    return pd.DataFrame(
        {
            "raw_value": raw,
            "comparison_value": comparison,
            "calculation_value": calculation,
            "beyond_bound": beyond.fillna(False),
        },
        index=raw.index,
    )


def a1_from_report_bound(
    publisher_value: pd.Series,
    historical_raw_value: pd.Series,
    rule: BoundRule,
) -> pd.Series:
    """A1 evidence for a report-value bound, before A/B/C is finalised."""
    if rule.bound_stage != "REPORT_VALUE" or not rule.dqp_a1_eligible:
        return pd.Series(False, index=publisher_value.index)
    bound = apply_authoritative_bound(historical_raw_value, rule)
    pub = pd.to_numeric(publisher_value, errors="coerce")
    return (
        bound["beyond_bound"]
        & pub.eq(bound["comparison_value"])
    ).fillna(False)


def a1_from_calculation_bound(
    publisher_raw_value: pd.Series,
    is_timely_accurate_raw_match: pd.Series,
    rule: BoundRule,
) -> pd.Series:
    """A1 evidence for calculation-stage clipping.

    Raw reconciliation remains unchanged. If raw data are timely/accurate and the
    raw value is beyond the authoritative calculation bound, the record may be A1.
    """
    if rule.bound_stage != "CALCULATION" or not rule.dqp_a1_eligible:
        return pd.Series(False, index=publisher_raw_value.index)
    bound = apply_authoritative_bound(publisher_raw_value, rule)
    good = pd.Series(is_timely_accurate_raw_match, index=publisher_raw_value.index).fillna(False).astype(bool)
    return (good & bound["beyond_bound"]).fillna(False)


# -----------------------------------------------------------------------------
# SNIPPET 3 — lightweight MVP1 run provenance/versioned outputs
# -----------------------------------------------------------------------------
def _sha256(path: str | Path) -> str:
    h = sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_run_manifest(
    *,
    index_id: str,
    edition: str,
    code_version: str,
    local_inputs: Iterable[dict[str, Any]] = (),
    drive_inputs: Iterable[dict[str, Any]] = (),
    run_time: datetime | None = None,
) -> dict[str, Any]:
    """Create a simple reproducibility stamp for an MVP1 DQP run.

    local_inputs entries: {role, path}
    drive_inputs entries: {role, file_id, name, modified_time?}

    A deterministic input_fingerprint identifies the exact input/code identity;
    run_id additionally contains the run timestamp so reruns never overwrite one
    another.
    """
    ts = run_time or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    inputs: list[dict[str, Any]] = []
    for item in local_inputs:
        path = Path(item["path"])
        inputs.append(
            {
                "role": item["role"],
                "name": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    for item in drive_inputs:
        inputs.append(
            {
                "role": item["role"],
                "name": item["name"],
                "drive_file_id": item["file_id"],
                "modified_time": item.get("modified_time"),
            }
        )

    inputs = sorted(inputs, key=lambda x: (str(x.get("role")), str(x.get("name"))))
    fingerprint_payload = {
        "index_id": str(index_id),
        "edition": str(edition),
        "code_version": str(code_version),
        "inputs": inputs,
    }
    fingerprint = sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    stamp = ts.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"DQP_{index_id}_{edition}_{stamp}_{fingerprint[:8]}"
    output_filename = f"Metadata_Automation_{index_id}_{edition}_{run_id}.xlsx"

    return {
        "run_id": run_id,
        "run_timestamp_utc": ts.astimezone(timezone.utc).isoformat(),
        "index_id": str(index_id),
        "edition": str(edition),
        "code_version": str(code_version),
        "input_fingerprint": fingerprint,
        "inputs": inputs,
        "output_filename": output_filename,
    }


# -----------------------------------------------------------------------------
# UCE METADATA ADAPTER — one source of truth, no hand-maintained cap list
# -----------------------------------------------------------------------------
def resolve_uce_vintage_folder(uce_root: str | Path, index_code: str, edition: str | int) -> Path:
    """Return the standard UCE vintage folder <INDEX>_<YEAR>.

    This function deliberately accepts the root as a parameter. Downstream code
    should not hard-code a user's local path or a transient package path.
    """
    folder = Path(uce_root) / f"{str(index_code).upper()}_{edition}"
    if not folder.exists():
        raise FileNotFoundError(f"UCE vintage folder not found: {folder}")
    return folder


def uce_bound_semantics(normalization: str) -> str | None:
    """Map UCE normalization vocabulary to its bound semantics.

    The mapping follows the UCE engine contract:
    - zscore / minmax_observed / log_observed_range: goalposts clip raw values
      before the transformation.
    - truncate: the raw value is truncated at goalpost_max.
    - minmax / log: values outside goalposts are equivalent to a calculation
      boundary because the normalized score is clipped to [0,1].
    - distance_to_target: values outside the target range hit the score floor.
    """
    norm = str(normalization or "").strip().lower()
    if norm in {"zscore", "minmax_observed", "log_observed_range"}:
        return "RAW_PRETRANSFORM_CLIP"
    if norm == "truncate":
        return "RAW_TRUNCATE"
    if norm in {"minmax", "log"}:
        return "SCORE_CLIP_AT_GOALPOST_EQUIVALENT"
    if norm == "distance_to_target":
        return "SCORE_FLOOR_OUTSIDE_TARGET_RANGE"
    return None


def extract_uce_bound_rules(
    metadata_path: str | Path,
    raw_path: str | Path | None = None,
) -> pd.DataFrame:
    """Generate a derived bound table from one standardized UCE metadata file.

    This is an adapter/output, NOT a second source of truth. The authoritative
    values remain in UCE metadata. `actual_beyond_count` is computed only when
    the matching UCE raw file is supplied.

    The resulting table can be used by DQP integration tests and human review.
    It must not silently convert every bound into A1: the downstream DQP mapping
    decides which UCE calculation bounds correspond to an A1 interpretation.
    """
    metadata_path = Path(metadata_path)
    ind = pd.read_excel(metadata_path, sheet_name="indicators")
    ind.columns = ind.columns.str.strip()

    raw = None
    if raw_path is not None:
        raw_path = Path(raw_path)
        raw = pd.read_excel(raw_path, header=0, skiprows=[1])
        def _norm_col(c: Any) -> str:
            if isinstance(c, (int, np.integer)):
                return str(int(c))
            if isinstance(c, float) and c.is_integer():
                return str(int(c))
            s = str(c).strip()
            return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s
        raw.columns = [_norm_col(c) for c in raw.columns]

    out: list[dict[str, Any]] = []
    for _, row in ind.dropna(subset=["KeyID"]).iterrows():
        kid = str(row["KeyID"]).strip()
        if kid.endswith(".0") and kid[:-2].isdigit():
            kid = kid[:-2]

        norm = str(row.get("normalization", "") or "").strip().lower()
        semantics = uce_bound_semantics(norm)
        if semantics is None:
            continue

        lo = pd.to_numeric(pd.Series([row.get("goalpost_min")]), errors="coerce").iloc[0]
        hi = pd.to_numeric(pd.Series([row.get("goalpost_max")]), errors="coerce").iloc[0]
        if norm == "truncate":
            lo = np.nan  # UCE truncate vocabulary is an upper cap only.

        series = None
        if raw is not None and kid in raw.columns:
            series = pd.to_numeric(raw[kid], errors="coerce")

        for bound_type, bound_value, source_col in (
            ("LOWER_FLOOR", lo, "goalpost_min_source"),
            ("UPPER_CAP", hi, "goalpost_max_source"),
        ):
            if pd.isna(bound_value):
                continue

            beyond = None
            if series is not None:
                beyond = (
                    series.lt(float(bound_value))
                    if bound_type == "LOWER_FLOOR"
                    else series.gt(float(bound_value))
                )

            out.append(
                {
                    "KeyID": kid,
                    "indicator_label": row.get("indicator_label"),
                    "normalization": norm,
                    "bound_type": bound_type,
                    "bound_value": float(bound_value),
                    "uce_semantics": semantics,
                    "goalpost_source": row.get(source_col),
                    "notes": row.get("notes"),
                    "actual_beyond_count": (
                        int(beyond.fillna(False).sum()) if beyond is not None else None
                    ),
                    "nonmissing_raw_count": (
                        int(series.notna().sum()) if series is not None else None
                    ),
                    "dqp_status": (
                        "UCE calculation-bound evidence; do not auto-A1 until "
                        "the DQP mapping for this bound type is reviewed"
                    ),
                }
            )

    return pd.DataFrame(out)


def load_uce_bound_rules(
    uce_root: str | Path,
    index_code: str,
    edition: str | int,
) -> pd.DataFrame:
    """Convenience wrapper for the standard UCE folder/file naming contract."""
    folder = resolve_uce_vintage_folder(uce_root, index_code, edition)
    vintage = f"{str(index_code).upper()}_{edition}"
    metadata = folder / f"metadata_{vintage}.xlsx"
    raw = folder / f"raw_{vintage}.xlsx"
    if not metadata.exists():
        raise FileNotFoundError(metadata)
    return extract_uce_bound_rules(metadata, raw if raw.exists() else None)
