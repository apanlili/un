"""
DQP Batch 1 - Snippet 3: reproducible run stamp and non-overwriting outputs.

Based on make_run_manifest() in Changes/DQP_Batch1_Reference_Snippets_v2_2026-11-01.py,
with these deliberate differences:
- The fingerprint also covers the run options that change results (e.g. legacy vs UCE A1,
  ESCWA-only), not only the input files.
- Code identity = git commit (with '-dirty' when the code has uncommitted changes)
  plus a SHA-256 of the actual .py files used, so it is exact even without git.
- Each batch run writes into its own folder '<YYYYMMDD-HHMMSS>_<fingerprint8>'; file names
  inside stay short and unchanged. Writing never replaces an existing file.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

RUN_INFO_SHEET = 'Run Info'


# ---------------------------------------------------------------------------
# Hashing helpers
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
    """Identity of one local input file (as in the reference snippet)."""
    path = Path(path)
    return {'role': role, 'name': path.name, 'sha256': sha256_file(path), 'size_bytes': path.stat().st_size}


# ---------------------------------------------------------------------------
# Code identity
# ---------------------------------------------------------------------------
def code_version(script_file: str | Path) -> dict[str, Any]:
    """git commit of the code folder (+ '-dirty' if uncommitted changes) and a hash of the .py files used."""
    script_file = Path(script_file).resolve()
    folder = script_file.parent
    files = [script_file] + sorted((folder / 'utils').glob('*.py'))
    code_hash = sha256_json({f.relative_to(folder).as_posix(): sha256_file(f) for f in files})

    git = None
    try:
        head = subprocess.run(['git', '-C', str(folder), 'rev-parse', '--short', 'HEAD'],
                              capture_output=True, text=True, timeout=20)
        if head.returncode == 0:
            dirty = subprocess.run(['git', '-C', str(folder), 'status', '--porcelain', '--', '.'],
                                   capture_output=True, text=True, timeout=20).stdout.strip()
            git = head.stdout.strip() + ('-dirty' if dirty else '')
    except (OSError, subprocess.SubprocessError):
        pass
    label = git or 'no-git'
    return {'code_version': f'{label}+src-{code_hash[:8]}', 'git_commit': git, 'code_sha256': code_hash}


# ---------------------------------------------------------------------------
# Manifest (one per index) and run folder (one per batch)
# ---------------------------------------------------------------------------
def make_run_manifest(*, index_id: str, edition: str, code: dict[str, Any],
                      inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None,
                      run_time: datetime | None = None) -> dict[str, Any]:
    """Reproducibility stamp for one index.

    input_fingerprint is deterministic: same code + inputs + options -> same fingerprint.
    run_id adds the run timestamp, so reruns never collide.
    """
    ts = run_time or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    inputs = sorted(inputs, key=lambda x: (str(x.get('role')), str(x.get('name'))))
    options = dict(sorted((options or {}).items()))
    fingerprint = sha256_json({'index_id': str(index_id), 'edition': str(edition),
                               'code_sha256': code['code_sha256'], 'inputs': inputs, 'options': options})
    stamp = ts.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return {
        'run_id': f'DQP_{index_id}_{edition}_{stamp}_{fingerprint[:8]}',
        'run_timestamp_utc': ts.astimezone(timezone.utc).isoformat(timespec='seconds'),
        'index_id': str(index_id),
        'edition': str(edition),
        **code,
        'input_fingerprint': fingerprint,
        'options': options,
        'inputs': inputs,
    }


def batch_fingerprint(manifests: Iterable[dict[str, Any]]) -> str:
    return sha256_json(sorted(m['input_fingerprint'] for m in manifests))


def run_folder_name(run_time: datetime, fingerprint: str) -> str:
    return f"{run_time.astimezone().strftime('%Y%m%d-%H%M%S')}_{fingerprint[:8]}"


def new_run_folder(parent: Path, name: str) -> Path:
    """Create parent/name; fail rather than reuse an existing run folder."""
    folder = Path(parent) / name
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def ensure_new(path: str | Path) -> Path:
    """Refuse to overwrite: raise if the output file already exists."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite existing output: {path}')
    return path


# ---------------------------------------------------------------------------
# 'Run Info' sheet + manifest.json
# ---------------------------------------------------------------------------
def run_info_df(manifest: dict[str, Any]) -> pd.DataFrame:
    """Two-column (Field, Value) table describing the run, for a 'Run Info' sheet."""
    rows = [(k, manifest.get(k)) for k in ('run_id', 'run_timestamp_utc', 'index_id', 'edition', 'code_version',
                                           'git_commit', 'code_sha256', 'input_fingerprint')]
    rows += [(f'option: {k}', v) for k, v in manifest.get('options', {}).items()]
    for item in manifest.get('inputs', []):
        role = item.get('role')
        rows += [(f'input {role}: {k}', v) for k, v in item.items() if k != 'role']
    return pd.DataFrame(rows, columns=['Field', 'Value']).astype({'Value': str})


def append_run_info(xlsx_path: str | Path, manifest: dict[str, Any]) -> None:
    """Add the 'Run Info' sheet to an already written workbook (no images in the target workbooks)."""
    with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='error') as writer:
        run_info_df(manifest).to_excel(writer, sheet_name=RUN_INFO_SHEET, index=False)
        ws = writer.sheets[RUN_INFO_SHEET]
        ws.column_dimensions['A'].width = 40
        ws.column_dimensions['B'].width = 90


def read_run_id(xlsx_path: str | Path) -> str | None:
    """run_id from a workbook's 'Run Info' sheet, or None if it has none (e.g. made before Snippet 3)."""
    try:
        info = pd.read_excel(xlsx_path, sheet_name=RUN_INFO_SHEET)
    except ValueError:
        return None
    hit = info.loc[info['Field'] == 'run_id', 'Value']
    return None if hit.empty else str(hit.iloc[0])


def write_manifest_json(folder: Path, payload: dict[str, Any]) -> Path:
    path = ensure_new(Path(folder) / 'manifest.json')
    path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    return path
