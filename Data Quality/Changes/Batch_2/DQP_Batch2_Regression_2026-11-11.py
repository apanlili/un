from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

MANDATORY = [
    "GGI_2026", "SDI_2026", "EPI_2026", "FII_2025", "SDI_2025", "EPI_2024",
    "WPS_2025", "GDI_2025", "GII_2025", "WJP_2025", "HDI_2025", "GHI_2025",
    "GGI_2025", "NRI_2025", "WPF_2024", "WPF_2025", "WPF_2026", "WBL_2026",
    "AIR_2025", "EPART_2024", "EGDI_2024", "WBL2_2026", "BTI_2026", "PHDI_2025",
    "BREADY_2025", "LNOB_2025", "LNOB_2026", "GKI_2024", "GCI_2024",
]
FAMILIES = {v.rsplit("_", 1)[0] for v in MANDATORY}
ESCWA = ['DZA','BHR','COM','DJI','EGY','IRQ','JOR','KWT','LBN','LBY','MRT','MAR','OMN','PSE','QAT','SAU','SOM','SDN','SYR','TUN','ARE','YEM']
QUALITY = list("ABCDEFGH")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("batch2_ref", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def read_raw(folder: Path, vintage: str) -> pd.DataFrame:
    return pd.read_excel(folder / f"raw_{vintage}.xlsx", header=0, skiprows=[1])


def synthetic_quality_frame(n: int) -> pd.DataFrame:
    # Deterministic one-hot category assignment; percentage mathematics is index-independent.
    cats = np.arange(max(n, 1)) % len(QUALITY)
    data = {q: (cats == i).astype(int) for i, q in enumerate(QUALITY)}
    data["KPI ID"] = np.arange(max(n, 1)) % 17
    data["Country"] = [f"C{i%23:02d}" for i in range(max(n, 1))]
    return pd.DataFrame(data)


def test_percentage_semantics(ref, n: int) -> dict:
    df = synthetic_quality_frame(n)
    kpi = ref.profile_quality_summary_table_pct100(df, QUALITY, groupby="KPI ID", pct_only=True)
    ref.assert_pct100_columns(kpi)
    country = ref.summary_by_group_pct100(df, QUALITY, groupby="Country")
    pct = country[[q + "_pct" for q in QUALITY]]
    if ((pct < 0) | (pct > 100)).any().any():
        raise AssertionError("country percentage outside 0–100")
    if not np.allclose(pct.sum(axis=1), 100, atol=.15):
        raise AssertionError("country percentages do not sum to 100")

    sample = pd.DataFrame({"value_difference_percentage_inferred": [0, .0061, .7692, np.nan]})
    exp = ref.prepare_metadata_export_percentages(sample)
    expected = [0.0, 0.61, 76.92]
    got = exp["value_difference_pct_inferred"].dropna().round(2).tolist()
    if got != expected:
        raise AssertionError(f"ratio→percentage export mismatch: {got}")
    if "value_difference_percentage_inferred" in exp.columns:
        raise AssertionError("ambiguous percentage column left in user-facing export")
    return {"snippet10": "PASS", "synthetic_rows": int(max(n,1))}


def test_uce_country_domain(ref, folder: Path, vintage: str) -> dict:
    raw = read_raw(folder, vintage)
    meta = pd.read_excel(folder / f"metadata_{vintage}.xlsx", sheet_name="country")
    raw_iso = raw["ISO"].dropna().astype(str).str.strip().str.upper()
    meta_iso = meta["ISO"].dropna().astype(str).str.strip().str.upper()
    # UCE raw country codes should be defined in its own country metadata and unique at raw-country level.
    missing = sorted(set(raw_iso) - set(meta_iso))
    dup = int(raw_iso.duplicated().sum())
    if missing:
        raise AssertionError(f"{vintage}: raw ISO absent from UCE country metadata: {missing[:10]}")
    if dup:
        raise AssertionError(f"{vintage}: duplicate ISO rows in UCE raw: {dup}")
    coverage = ref.build_profile_coverage_table(raw, ESCWA)
    if len(coverage) != len(ESCWA) or coverage["ISO"].nunique() != len(ESCWA):
        raise AssertionError(f"{vintage}: incomplete ESCWA coverage table")
    if not set(coverage.profile_status).issubset({"AVAILABLE", "NOT_COVERED_BY_INDEX_EDITION"}):
        raise AssertionError(f"{vintage}: invalid coverage status")
    return {
        "country_domain": "PASS",
        "raw_countries": int(raw_iso.nunique()),
        "escwa_available": int((coverage.profile_status == "AVAILABLE").sum()),
        "escwa_not_covered": int((coverage.profile_status != "AVAILABLE").sum()),
    }


def discover(roots: list[Path]) -> dict[str, Path]:
    locations = {}
    for root in roots:
        for p in root.iterdir():
            if not p.is_dir() or "_" not in p.name:
                continue
            fam, year = p.name.rsplit("_", 1)
            if fam not in FAMILIES or not year.isdigit():
                continue
            if (p / f"metadata_{p.name}.xlsx").exists() and (p / f"raw_{p.name}.xlsx").exists():
                locations.setdefault(p.name, p)
    return locations


def real_dqp_country_cases(ref, local_root: Path) -> list[dict]:
    # Existing v0.3 universal pre-check, used only to canonicalize aliases before the audit.
    sys.path.insert(0, str(local_root / "dqp_precheck_v03_code"))
    from dqp_precheck import run
    from dqp_precheck.adapters import read_simulator_excel, read_historical_excel

    cfgs = {
        "WPS_2025": ("1022", 2025, "raw_WPS_2025.xlsx", "index_1022 Women Peace and security Index.xlsx"),
        "FII_2025": ("1024", 2025, "raw_FII_2025 1.xlsx", "index_1024_FII.xlsx"),
        "EGDI_2024": ("9", 2024, "raw_EGDI_2024.xlsx", "index_9 EGDI.xlsx"),
        "GII_2026": ("7", 2026, "raw_GII_2026.xlsx", "20261019_historical_data_index_7_GII_2026 v2.xlsx"),
    }
    out = []
    for label,(idx,edition,simf,histf) in cfgs.items():
        sim = read_simulator_excel(local_root / simf)
        hist = read_historical_excel(local_root / histf)
        pre = run(sim, hist, index_id=idx, edition=edition)
        audit = ref.country_presence_audit(pre.sim.rename(columns={"KPI":"KPI ID"}), pre.hist.rename(columns={"KPI":"KPI ID"}))
        summ = ref.country_audit_summary(audit)
        out.append({"vintage":label, **summ,
                    "sim_only_codes":";".join(audit.loc[audit.presence_status.eq("SIMULATOR_ONLY"),"ISO"].tolist()),
                    "hist_only_codes":";".join(audit.loc[audit.presence_status.eq("HISTORICAL_ONLY"),"ISO"].tolist())})
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--uce-root", type=Path, required=True)
    ap.add_argument("--uce-extra-root", type=Path, action="append", default=[])
    ap.add_argument("--reference-code", type=Path, required=True)
    ap.add_argument("--local-root", type=Path, required=True)
    ap.add_argument("--alfonso-notebook", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, required=True)
    args=ap.parse_args()
    ref=load_module(args.reference_code)
    loc=discover([args.uce_root]+list(args.uce_extra_root))
    rows=[]; failures=[]
    for vintage,folder in sorted(loc.items()):
        if vintage.rsplit("_",1)[0] not in FAMILIES: continue
        try:
            c=test_uce_country_domain(ref,folder,vintage)
            raw=read_raw(folder,vintage)
            p=test_percentage_semantics(ref,len(raw))
            row={"vintage":vintage,"mandatory":vintage in MANDATORY,**c,**p}
            row["snippet11_coverage"]="PASS"
        except Exception as e:
            row={"vintage":vintage,"mandatory":vintage in MANDATORY,"country_domain":"FAIL","snippet10":"FAIL","snippet11_coverage":"FAIL","error":str(e)}
            failures.append(vintage)
        rows.append(row)
    found={r['vintage'] for r in rows if r.get('mandatory')}
    missing=sorted(set(MANDATORY)-found)
    if missing: failures += missing

    real=real_dqp_country_cases(ref,args.local_root)

    txt=args.alfonso_notebook.read_text(encoding="utf-8")
    coverage_scan={
        "latent_skip_message_bug_present": 'skipped {country}' in (args.local_root / "excel_functions.py").read_text(encoding="utf-8"),
    }

    result={
        "mandatory_count":len(MANDATORY),
        "mandatory_found":len(found),
        "missing_mandatory":missing,
        "total_vintages_tested":len(rows),
        "older_regression_vintages":sum(not r.get('mandatory',False) for r in rows),
        "failures":failures,
        "rows":rows,
        "real_dqp_country_cases":real,
        "coverage_scan_current_alfonso":coverage_scan,
    }
    args.json_out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:result[k] for k in ["mandatory_count","mandatory_found","missing_mandatory","total_vintages_tested","older_regression_vintages","failures","real_dqp_country_cases","coverage_scan_current_alfonso"]},indent=2))

if __name__=="__main__": main()
