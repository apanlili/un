"""
DQP Batch 1 - Snippet 3: reproducible run stamp and non-overwriting outputs.

"A later run must create a new output filename rather than silently overwrite an earlier file."
- Output files end with the run date: Metadata_Automation_index_9_20261115.xlsx
  (a second run on the same day adds _2, _3, ...). --flat keeps the old names and overwrites.
- Every workbook gets a 'Run Info' sheet: run time, run ID, version, index, edition, settings and
  input files (with a content ID), plus an input fingerprint.
- Version is set in each script (VERSION): original pipeline 1.0, Batch 1 1.1. Raise it when the code changes.

Based on make_run_manifest() in Changes/Batch_1/DQP_Batch1_Reference_Snippets_v2_2026-11-01.py.
"""
from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

RUN_INFO_SHEET = 'Run Info'

ROLE_LABELS = {'historical': 'Historical file', 'simulator': 'Simulator file',
               'uce_bounds': 'UCE bounds file', 'profile_template': 'Profile template',
               'canonical_countries': 'Canonical country list'}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
def sha256_file(path: str | Path) -> str:
    h = sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def file_input(role: str, path: str | Path) -> dict[str, Any]:
    """Identity of one input file. Only name, size and content hash go into the fingerprint."""
    path = Path(path)
    st = path.stat()
    return {'role': role, 'name': path.name, 'sha256': sha256_file(path), 'size_bytes': st.st_size,
            'modified': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')}


# ---------------------------------------------------------------------------
# Run record
# ---------------------------------------------------------------------------
def make_run_manifest(*, index_id: str, edition: str, version: str, script: str,
                      inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None,
                      run_time: datetime) -> dict[str, Any]:
    """Run record for one index.

    run_id: index, version and run time, e.g. index_9_v1.1_20261115-164338.
    input_fingerprint: same version + inputs + settings -> same fingerprint.
    """
    inputs = sorted(inputs, key=lambda x: (str(x.get('role')), str(x.get('name'))))
    options = dict(sorted((options or {}).items()))
    fingerprint = sha256_json({
        'index_id': str(index_id), 'edition': str(edition), 'version': str(version), 'options': options,
        'inputs': [{k: i[k] for k in ('role', 'name', 'sha256', 'size_bytes')} for i in inputs]})
    return {
        'run_id': f"{index_id}_v{version}_{run_time.strftime('%Y%m%d-%H%M%S')}",
        'run_time': run_time.isoformat(sep=' ', timespec='seconds'),
        'version': str(version),
        'index_id': str(index_id),
        'edition': str(edition),
        'script': script,
        'input_fingerprint': fingerprint,
        'options': options,
        'inputs': inputs,
    }


# ---------------------------------------------------------------------------
# Output file names
# ---------------------------------------------------------------------------
def output_path(folder: str | Path, stem: str, run_time: datetime, flat: bool = False) -> Path:
    """folder/<stem>_<YYYYMMDD>.xlsx; _2, _3, ... for further runs on the same day.
    flat=True: folder/<stem>.xlsx (old name, overwritten)."""
    folder = Path(folder)
    if flat:
        return folder / f'{stem}.xlsx'
    base = f"{stem}_{run_time.strftime('%Y%m%d')}"
    path, n = folder / f'{base}.xlsx', 2
    while path.exists():
        path, n = folder / f'{base}_{n}.xlsx', n + 1
    return path


def ensure_new(path: str | Path, allow_overwrite: bool = False) -> Path:
    """Refuse to overwrite an existing output (unless allow_overwrite, used by --flat)."""
    path = Path(path)
    if path.exists() and not allow_overwrite:
        raise FileExistsError(f'Refusing to overwrite existing output: {path}')
    return path


# ---------------------------------------------------------------------------
# 'Run Info' sheet
# ---------------------------------------------------------------------------
def run_info_df(manifest: dict[str, Any]) -> pd.DataFrame:
    """Readable two-column (Field, Value) table describing the run."""
    m = manifest
    rows = [
        ('Run time', m['run_time']),
        ('Run ID', m['run_id']),
        ('Version', m['version']),
        ('Index', m['index_id']),
        ('Edition', m['edition']),
        ('Script', m['script']),
    ]
    # The input fingerprint, settings and file content hashes are computed (make_run_manifest) but not listed.
    for i in m.get('inputs', []):
        rows.append((ROLE_LABELS.get(i['role'], i['role']), f"{i['name']}  |  modified {i['modified']}"))
    return pd.DataFrame(rows, columns=['Field', 'Value']).astype({'Value': str})


def append_run_info(xlsx_path: str | Path, info: pd.DataFrame) -> None:
    """Add the 'Run Info' sheet to an already written workbook (used for workbooks without images)."""
    with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='error') as writer:
        info.to_excel(writer, sheet_name=RUN_INFO_SHEET, index=False)
        ws = writer.sheets[RUN_INFO_SHEET]
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 110


def read_run_id(xlsx_path: str | Path) -> str | None:
    """Run ID from a workbook's 'Run Info' sheet, or None (e.g. made before Snippet 3)."""
    try:
        info = pd.read_excel(xlsx_path, sheet_name=RUN_INFO_SHEET)
    except ValueError:
        return None
    hit = info.loc[info['Field'].isin(['Run ID', 'run_id']), 'Value']
    return None if hit.empty else str(hit.iloc[0])
