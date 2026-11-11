#!/usr/bin/env python3
"""
DQP Batch 1 — full UCE / Simulator Generator acceptance runner
Date: 2026-11-01

Purpose
-------
Regression-test the three Batch-1 DQP reference changes on:
  1) all 29 Generator-produced index/vintage candidates in the 8-Oct manufacturing register; and
  2) every additional older UCE structured vintage in those same index families.

Snippet 1: sign/zero-safe relative matching.
Snippet 2: authoritative cap/floor mechanics without altering raw evidence.
Snippet 3: deterministic input fingerprint + non-overwriting run IDs.

Important
---------
- This runner tests generic mechanics. It does NOT automatically declare every UCE
  goalpost/cap/floor an A1 DQP rule.
- BREADY_2025 is tested from the Generator workbook because UCE v41 has a BREADY
  build/fiche but does not expose the standard metadata_<V>.xlsx + raw_<V>.xlsx
  vintage folder in the main reproduction package.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

MANDATORY_GENERATOR_CANDIDATES = [
    "GGI_2026", "SDI_2026", "EPI_2026",
    "FII_2025", "SDI_2025", "EPI_2024", "WPS_2025", "GDI_2025",
    "GII_2025", "WJP_2025",
    "HDI_2025", "GHI_2025", "GGI_2025", "NRI_2025",
    "WPF_2024", "WPF_2025", "WPF_2026", "WBL_2026", "AIR_2025",
    "EPART_2024", "EGDI_2024", "WBL2_2026", "BTI_2026", "PHDI_2025",
    "BREADY_2025", "LNOB_2025", "LNOB_2026", "GKI_2024", "GCI_2024",
]

MANDATORY_FAMILIES = {v.rsplit("_", 1)[0] for v in MANDATORY_GENERATOR_CANDIDATES}


def load_reference_module(path: Path):
    import sys
    spec = importlib.util.spec_from_file_location("batch1_reference", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses resolve forward/type annotations through sys.modules while
    # the module is being executed, so register it before exec_module().
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def norm_keyid(value) -> str:
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value).strip()
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def read_uce_raw(raw_path: Path) -> pd.DataFrame:
    # UCE raw files use row 1 as headers and row 2 as unit/label metadata.
    df = pd.read_excel(raw_path, header=0, skiprows=[1])
    df.columns = [norm_keyid(c) for c in df.columns]
    return df


def numeric_payload(df: pd.DataFrame) -> np.ndarray:
    vals = []
    for col in df.columns:
        x = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        x = x[np.isfinite(x)]
        if len(x):
            vals.append(x)
    if not vals:
        return np.array([], dtype=float)
    return np.concatenate(vals)


def assert_snippet1(ref, values: np.ndarray) -> dict:
    s = pd.Series(values, dtype=float)
    neg = s[s < 0]
    zero = s[s == 0]
    pos = s[s > 0]

    failures = []

    # Every real value must remain an exact match to itself.
    ev = ref.compute_match_gap(s, s)
    if not bool(ev["exact_match"].all()):
        failures.append("exact self-match failed")

    # A +/-0.5% perturbation is inside the CURRENT 1% numerical rule.
    nz = s[s != 0]
    if len(nz):
        near = nz * 1.005
        near_ev = ref.compute_match_gap(nz.reset_index(drop=True), near.reset_index(drop=True))
        if not bool(ref.approximate_match_mask(near_ev, 0.01).all()):
            failures.append("0.5% nonzero perturbation did not pass")

        far = nz * 1.02
        far_ev = ref.compute_match_gap(nz.reset_index(drop=True), far.reset_index(drop=True))
        if bool(ref.approximate_match_mask(far_ev, 0.01).any()):
            failures.append("2% nonzero perturbation incorrectly passed")

    # A non-exact zero has no relative denominator and cannot approximate-match.
    if len(zero):
        z = pd.Series(np.zeros(len(zero)))
        z_hist = pd.Series(np.full(len(zero), 1e-6))
        z_ev = ref.compute_match_gap(z, z_hist)
        if bool(ref.approximate_match_mask(z_ev, 0.01).any()):
            failures.append("non-exact zero incorrectly approximate-matched")
        if z_ev["value_difference_percentage"].notna().any():
            failures.append("non-exact zero unexpectedly received a relative gap")

    return {
        "numeric_cells_tested": int(len(s)),
        "negative_values": int(len(neg)),
        "zero_values": int(len(zero)),
        "positive_values": int(len(pos)),
        "snippet1": "PASS" if not failures else "FAIL",
        "snippet1_failures": failures,
    }


def bound_semantics(norm: str) -> str | None:
    norm = str(norm or "").strip().lower()
    if norm in {"zscore", "minmax_observed", "log_observed_range"}:
        return "RAW_PRETRANSFORM_CLIP"
    if norm == "truncate":
        return "RAW_TRUNCATE"
    if norm in {"minmax", "log"}:
        return "SCORE_CLIP_AT_GOALPOST_EQUIVALENT"
    if norm == "distance_to_target":
        return "SCORE_FLOOR_OUTSIDE_TARGET_RANGE"
    return None


def assert_bound_rule(ref, *, bound_type: str, bound_value: float, stage: str) -> list[str]:
    """Synthetic invariants for one metadata-defined bound."""
    errors = []
    b = float(bound_value)
    span = max(abs(b), 1.0)
    if bound_type == "UPPER_CAP":
        inside = b - 0.1 * span
        outside = b + 0.1 * span
    else:
        inside = b + 0.1 * span
        outside = b - 0.1 * span

    rule = ref.BoundRule(
        kpi_id="TEST",
        bound_type=bound_type,
        bound_value=b,
        bound_stage=stage,
        dqp_a1_eligible=False,  # mechanics only; A1 mapping is separately reviewed
        rule_id="PORTFOLIO_TEST",
    )
    raw = pd.Series([inside, b, outside], dtype=float)
    out = ref.apply_authoritative_bound(raw, rule)

    if not np.allclose(out["raw_value"].to_numpy(), raw.to_numpy(), equal_nan=True):
        errors.append("raw evidence changed")

    if stage == "REPORT_VALUE":
        expected = raw.clip(upper=b) if bound_type == "UPPER_CAP" else raw.clip(lower=b)
        if not np.allclose(out["comparison_value"], expected, equal_nan=True):
            errors.append("report-stage comparison value not bounded")
        if not np.allclose(out["calculation_value"], expected, equal_nan=True):
            errors.append("report-stage calculation value not bounded")
    else:
        if not np.allclose(out["comparison_value"], raw, equal_nan=True):
            errors.append("calculation-stage comparison value changed")
        expected = raw.clip(upper=b) if bound_type == "UPPER_CAP" else raw.clip(lower=b)
        if not np.allclose(out["calculation_value"], expected, equal_nan=True):
            errors.append("calculation-stage calculation value not bounded")

    expected_beyond = np.array([False, False, True])
    if not np.array_equal(out["beyond_bound"].to_numpy(dtype=bool), expected_beyond):
        errors.append("beyond-bound flag incorrect")

    return errors


def test_uce_bounds(ref, metadata_path: Path, raw_df: pd.DataFrame) -> dict:
    ind = pd.read_excel(metadata_path, sheet_name="indicators")
    ind.columns = ind.columns.str.strip()

    rule_count = 0
    actual_beyond = 0
    semantics_counter = Counter()
    failures = []

    for _, row in ind.dropna(subset=["KeyID"]).iterrows():
        kid = norm_keyid(row["KeyID"])
        norm = str(row.get("normalization", "") or "").strip().lower()
        sem = bound_semantics(norm)
        if sem is None:
            continue

        lo = pd.to_numeric(pd.Series([row.get("goalpost_min")]), errors="coerce").iloc[0]
        hi = pd.to_numeric(pd.Series([row.get("goalpost_max")]), errors="coerce").iloc[0]
        if norm == "truncate":
            lo = np.nan

        stage = "REPORT_VALUE" if sem in {"RAW_PRETRANSFORM_CLIP", "RAW_TRUNCATE"} else "CALCULATION"
        series = pd.to_numeric(raw_df[kid], errors="coerce") if kid in raw_df.columns else None

        for bound_type, bound in (("LOWER_FLOOR", lo), ("UPPER_CAP", hi)):
            if pd.isna(bound):
                continue
            rule_count += 1
            semantics_counter[sem] += 1
            errs = assert_bound_rule(
                ref,
                bound_type=bound_type,
                bound_value=float(bound),
                stage=stage,
            )
            if errs:
                failures.extend([f"{kid}/{bound_type}: {e}" for e in errs])

            if series is not None:
                if bound_type == "LOWER_FLOOR":
                    actual_beyond += int(series.lt(float(bound)).fillna(False).sum())
                else:
                    actual_beyond += int(series.gt(float(bound)).fillna(False).sum())

    return {
        "bound_rules_tested": int(rule_count),
        "actual_beyond_bound_values": int(actual_beyond),
        "bound_semantics": "; ".join(f"{k}:{v}" for k, v in sorted(semantics_counter.items())),
        "snippet2": "PASS" if not failures else "FAIL",
        "snippet2_failures": failures,
    }


def test_provenance(ref, *, vintage: str, code_path: Path, inputs: list[dict]) -> dict:
    family, year = vintage.rsplit("_", 1)
    t0 = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
    a = ref.make_run_manifest(
        index_id=family,
        edition=year,
        code_version="DQP_BATCH1_REFERENCE_v2_2026-11-01",
        local_inputs=inputs + [{"role": "reference_code", "path": code_path}],
        run_time=t0,
    )
    b = ref.make_run_manifest(
        index_id=family,
        edition=year,
        code_version="DQP_BATCH1_REFERENCE_v2_2026-11-01",
        local_inputs=inputs + [{"role": "reference_code", "path": code_path}],
        run_time=t0 + timedelta(minutes=1),
    )
    ok = (
        a["input_fingerprint"] == b["input_fingerprint"]
        and a["run_id"] != b["run_id"]
        and a["output_filename"] != b["output_filename"]
    )
    return {
        "snippet3": "PASS" if ok else "FAIL",
        "input_fingerprint_12": a["input_fingerprint"][:12],
        "snippet3_failures": [] if ok else ["fingerprint/run-id non-overwrite invariant failed"],
    }


def scan_bready_workbook(path: Path) -> np.ndarray:
    wb = load_workbook(path, read_only=True, data_only=True)
    vals = []
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, (int, float, np.integer, np.floating)) and np.isfinite(float(v)):
                        vals.append(float(v))
    finally:
        wb.close()
    return np.array(vals, dtype=float)


def gii_regression(path: Path) -> dict:
    df = pd.read_excel(path, sheet_name="Metadata_automated")
    report = pd.to_numeric(df["data_report"], errors="coerce")
    approx = df["A_approx"].eq(1) | df["B_approx"].eq(1)
    neg_approx = report.lt(0) & approx
    sub = df.loc[neg_approx].copy()
    sub["abs_rel"] = (
        pd.to_numeric(sub["value_difference_inferred"], errors="coerce").abs()
        / pd.to_numeric(sub["data_report"], errors="coerce").abs()
    )
    false = sub["abs_rel"].gt(0.01)
    false_by = (
        sub.loc[false, "KPI ID"].map(norm_keyid).value_counts().sort_index().to_dict()
    )
    return {
        "gii2026_current_negative_approx": int(len(sub)),
        "gii2026_false_signed_denominator": int(false.sum()),
        "gii2026_legit_negative_approx": int((~false).sum()),
        "gii2026_false_by_kpi": {str(k): int(v) for k, v in false_by.items()},
        "gii2026_abs_gap_mean": float(sub["abs_rel"].mean()),
        "gii2026_abs_gap_median": float(sub["abs_rel"].median()),
        "gii2026_abs_gap_max": float(sub["abs_rel"].max()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uce-root", type=Path, required=True,
                    help="Extracted main UCE reproduction package root, e.g. .../pkg24")
    ap.add_argument("--uce-extra-root", type=Path, action="append", default=[],
                    help="Optional additional UCE package root(s), e.g. the dedicated BREADY pkg24")
    ap.add_argument("--reference-code", type=Path, required=True)
    ap.add_argument("--bready-workbook", type=Path, required=False,
                    help="Fallback only if standardized BREADY UCE inputs are unavailable")
    ap.add_argument("--gii-dqp-output", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, required=True)
    args = ap.parse_args()

    ref = load_reference_module(args.reference_code)

    roots = [args.uce_root] + list(args.uce_extra_root or [])
    structured_locations = {}
    for root in roots:
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or "_" not in folder.name:
                continue
            family, year = folder.name.rsplit("_", 1)
            if family not in MANDATORY_FAMILIES or not year.isdigit():
                continue
            meta = folder / f"metadata_{folder.name}.xlsx"
            raw = folder / f"raw_{folder.name}.xlsx"
            if meta.exists() and raw.exists():
                structured_locations.setdefault(folder.name, folder)

    structured = sorted(structured_locations)
    rows = []
    failures = []

    for vintage in structured:
        folder = structured_locations[vintage]
        meta = folder / f"metadata_{vintage}.xlsx"
        raw = folder / f"raw_{vintage}.xlsx"
        raw_df = read_uce_raw(raw)
        vals = numeric_payload(raw_df)

        r = {
            "vintage": vintage,
            "family": vintage.rsplit("_", 1)[0],
            "year": int(vintage.rsplit("_", 1)[1]),
            "generator_mandatory": vintage in MANDATORY_GENERATOR_CANDIDATES,
            "uce_structured_inputs": True,
        }
        r.update(assert_snippet1(ref, vals))
        r.update(test_uce_bounds(ref, meta, raw_df))
        r.update(test_provenance(
            ref,
            vintage=vintage,
            code_path=args.reference_code,
            inputs=[
                {"role": "uce_metadata", "path": meta},
                {"role": "uce_raw", "path": raw},
            ],
        ))
        r["overall"] = "PASS" if all(r[k] == "PASS" for k in ("snippet1", "snippet2", "snippet3")) else "FAIL"
        if r["overall"] != "PASS":
            failures.append(vintage)
        rows.append(r)

    # Fallback only: if BREADY is absent from all standardized UCE roots, test the
    # Generator workbook numerically. In v41 a dedicated BREADY UCE package exists,
    # so the normal structured path above is preferred.
    if "BREADY_2025" not in structured_locations:
        if args.bready_workbook is None:
            raise FileNotFoundError(
                "BREADY_2025 is mandatory but no standardized UCE folder or "
                "--bready-workbook fallback was supplied"
            )
        vals = scan_bready_workbook(args.bready_workbook)
        b = {
            "vintage": "BREADY_2025",
            "family": "BREADY",
            "year": 2025,
            "generator_mandatory": True,
            "uce_structured_inputs": False,
        }
        b.update(assert_snippet1(ref, vals))
        b.update({
            "bound_rules_tested": 0,
            "actual_beyond_bound_values": 0,
            "bound_semantics": "N/A — fallback Generator workbook numeric-domain test",
            "snippet2": "N/A (NO STANDARDIZED UCE BOUNDS)",
            "snippet2_failures": [],
        })
        b.update(test_provenance(
            ref,
            vintage="BREADY_2025",
            code_path=args.reference_code,
            inputs=[{"role": "generator_workbook", "path": args.bready_workbook}],
        ))
        b["overall"] = "PASS*" if b["snippet1"] == "PASS" and b["snippet3"] == "PASS" else "FAIL"
        if b["overall"] == "FAIL":
            failures.append("BREADY_2025")
        rows.append(b)

    rows = sorted(rows, key=lambda x: (not x["generator_mandatory"], x["family"], x["year"]))
    mandatory_found = {r["vintage"] for r in rows if r["generator_mandatory"]}
    missing_mandatory = sorted(set(MANDATORY_GENERATOR_CANDIDATES) - mandatory_found)

    gii = gii_regression(args.gii_dqp_output)

    result = {
        "mandatory_generator_candidates": MANDATORY_GENERATOR_CANDIDATES,
        "mandatory_count": len(MANDATORY_GENERATOR_CANDIDATES),
        "mandatory_found_count": len(mandatory_found),
        "missing_mandatory": missing_mandatory,
        "structured_uce_vintages_count": len(structured),
        "supplemental_older_uce_count": sum(not r["generator_mandatory"] for r in rows),
        "total_test_rows": len(rows),
        "total_numeric_values": sum(r["numeric_cells_tested"] for r in rows),
        "total_negative_values": sum(r["negative_values"] for r in rows),
        "total_zero_values": sum(r["zero_values"] for r in rows),
        "total_bound_rules_tested": sum(r["bound_rules_tested"] for r in rows),
        "total_actual_beyond_bound": sum(r["actual_beyond_bound_values"] for r in rows),
        "failures": failures,
        **gii,
        "rows": rows,
    }

    args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in [
        "mandatory_count", "mandatory_found_count", "missing_mandatory",
        "structured_uce_vintages_count", "supplemental_older_uce_count",
        "total_test_rows", "total_numeric_values", "total_negative_values",
        "total_zero_values", "total_bound_rules_tested",
        "total_actual_beyond_bound", "failures",
        "gii2026_current_negative_approx",
        "gii2026_false_signed_denominator",
        "gii2026_legit_negative_approx",
        "gii2026_false_by_kpi",
    ]}, indent=2))


if __name__ == "__main__":
    main()
