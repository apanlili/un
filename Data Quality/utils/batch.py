"""
Command line + batch loop shared by metadata_automation.py and metadata_snippet2.py.

Each script supplies a `run_index(index_name, hist_file, sim_file, args)` function;
this module parses the options, resolves folders, picks the indices whose files
exist, and runs them one after another (one failure does not stop the batch).
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from datetime import datetime, timezone

from utils.index_files import DATA_FILES, edition
from utils.run_stamp import (code_version, file_input, make_run_manifest, batch_fingerprint,
                             run_folder_name, new_run_folder, write_manifest_json)

DEFAULT_DATA_ROOT = Path('C:/Users/alfon/Desktop/UN/Data')
TEMPLATE_REL = Path('Reference templates') / 'Data_Diagnosis_Assessment_template.xlsx'

# (local subfolder, gdrive subfolder) for each output, as in the notebooks
OUTPUT_DIRS = {
    'metadata': ('Metadata Automation Outputs', 'Metadata_automation_excels'),
    'ispar':    ('Profile Input ISPAR',         'Country Profiles (ISPAR Input)'),
    'profile':  ('Profile Output',              'Country Profiles'),
}


def utf8_console() -> None:
    """The pipeline prints emoji status marks; don't crash on a cp1252 console/pipe."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def build_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description,
                                formatter_class=argparse.RawDescriptionHelpFormatter)

    g = p.add_argument_group('input folders')
    g.add_argument('--hist', type=Path,
                   help='Folder with historical data files (default: <data-root>/Historical)')
    g.add_argument('--sim', type=Path,
                   help='Folder with simulator data files (default: <data-root>/Simulator Data)')
    g.add_argument('--data-root', type=Path,
                   help=f'Base data folder (default: {DEFAULT_DATA_ROOT}, or the shared drive with --gdrive)')
    g.add_argument('--gdrive', action='store_true',
                   help="Use the 'ISPAR Team Shared/Metadata Automation' Google Drive folder for data and outputs")
    g.add_argument('--index', nargs='+', metavar='NAME',
                   help='Only run these indices (default: every index in utils/index_files.py whose files are found)')
    g.add_argument('--list', action='store_true',
                   help='List indices and whether their files were found, then exit')

    g = p.add_argument_group('outputs (default: metadata file only)')
    g.add_argument('--no-metadata', action='store_true',
                   help='Do not write Metadata_Automation_<index>.xlsx')
    g.add_argument('--ispar', action='store_true',
                   help='Also write Profile_Input_ISPAR_<index>.xlsx')
    g.add_argument('--profile', action='store_true',
                   help='Also write Profile_ESCWA_<index>.xlsx (country profiles; needs the reference template)')
    g.add_argument('--all-outputs', action='store_true',
                   help='Shortcut for --ispar --profile')
    g.add_argument('--out', type=Path,
                   help='Write every output into this one folder (default: the per-output folders under <data-root>). '
                        'Each run creates a new <date-time>_<fingerprint> subfolder; nothing is overwritten.')
    g.add_argument('--template', type=Path,
                   help=f'Data diagnosis template for --profile (default: <data-root>/{TEMPLATE_REL.as_posix()})')

    g = p.add_argument_group('run options')
    g.add_argument('--escwa-only', action='store_true',
                   help='Metadata sheet, summary stats and long data limited to ESCWA countries')
    g.add_argument('--from-db', action='store_true',
                   help='Read simulator/historical data from the database instead of the Excel files (needs .env)')
    g.add_argument('--db-env', default='prod', help='Database environment for --from-db (default: prod)')
    g.add_argument('--stop-on-error', action='store_true',
                   help='Stop the batch at the first failing index')
    return p


def resolve(args: argparse.Namespace) -> argparse.Namespace:
    """Fill in folders/output paths and validate. Mutates and returns args."""
    if args.gdrive:
        from utils.excel_functions import find_shared_folder
        base = Path(find_shared_folder('ISPAR Team Shared')) / 'Metadata Automation'
        root = args.data_root or base / 'Data'
        out_dirs = {k: base / v[1] for k, v in OUTPUT_DIRS.items()}
    else:
        root = args.data_root or DEFAULT_DATA_ROOT
        out_dirs = {k: root / v[0] for k, v in OUTPUT_DIRS.items()}
    if args.out:
        out_dirs = {k: args.out for k in OUTPUT_DIRS}

    args.hist = args.hist or root / 'Historical'
    args.sim = args.sim or root / 'Simulator Data'
    args.template = args.template or root / TEMPLATE_REL
    args.out_dirs = out_dirs

    args.write_metadata = not args.no_metadata
    args.write_ispar = args.ispar or args.all_outputs
    args.write_profile = args.profile or args.all_outputs

    for name, folder in (('--hist', args.hist), ('--sim', args.sim)):
        if not folder.is_dir():
            sys.exit(f'{name} folder not found: {folder}')
    if args.index:
        unknown = [i for i in args.index if i not in DATA_FILES]
        if unknown:
            sys.exit(f'Unknown index name(s): {unknown}. Add them to utils/index_files.py. '
                     f'Known: {", ".join(DATA_FILES)}')
    if args.write_profile and not args.template.is_file():
        sys.exit(f'--profile needs the reference template, not found: {args.template}')
    if args.from_db:
        from dotenv import load_dotenv, find_dotenv
        env_path = find_dotenv(usecwd=True)
        if not env_path:
            sys.exit('--from-db: no .env file found in the current directory or its parents')
        load_dotenv(env_path, override=True)
    return args


def _find_files(args):
    """[(index_name, hist_file, sim_file, missing_reason or None)] in mapping order."""
    names = args.index or list(DATA_FILES)
    rows = []
    for name in names:
        hist_name, _, sim_name = DATA_FILES[name]
        hist_file, sim_file = args.hist / hist_name, args.sim / sim_name
        missing = [str(f.name) for f in (hist_file, sim_file) if not f.is_file()]
        rows.append((name, hist_file, sim_file, ('missing: ' + ', '.join(missing)) if missing else None))
    return rows


def base_options(args) -> dict:
    """Run options that change the content of the outputs (part of the input fingerprint)."""
    return {'escwa_only': bool(args.escwa_only),
            'data_source': f'db:{args.db_env}' if args.from_db else 'excel'}


def run_batch(run_index, args: argparse.Namespace, script_file,
              stamp_inputs=None, stamp_options=None) -> int:
    """Run every index found. Snippet 3: each index gets a run manifest (passed to run_index),
    each batch writes into its own new run folder, and a manifest.json records the whole batch.

    stamp_inputs(args, index_name)  -> extra [file_input(...)] for the fingerprint (script specific)
    stamp_options(args, index_name) -> extra {option: value} for the fingerprint (script specific)
    """
    rows = _find_files(args)

    if args.list:
        for name, hist_file, sim_file, reason in rows:
            print(f"{name:<14} {'ok' if reason is None else reason}   edition: {edition(name)}")
            print(f"{'':<14}   hist: {hist_file.name}\n{'':<14}   sim:  {sim_file.name}")
        return 0

    todo = [r for r in rows if r[3] is None]
    outputs = [k for k, on in (('metadata', args.write_metadata), ('ispar', args.write_ispar),
                               ('profile', args.write_profile)) if on]

    # --- Snippet 3: fingerprint every index before running anything ---
    code = code_version(script_file)
    run_time = datetime.now(timezone.utc)
    manifests = {}
    for name, hist_file, sim_file, _ in todo:
        inputs = [file_input('historical', hist_file), file_input('simulator', sim_file)]
        if args.write_profile:
            inputs.append(file_input('profile_template', args.template))
        inputs += list(stamp_inputs(args, name)) if stamp_inputs else []
        options = {**base_options(args), **(stamp_options(args, name) if stamp_options else {})}
        manifests[name] = make_run_manifest(index_id=name, edition=edition(name), code=code,
                                            inputs=inputs, options=options, run_time=run_time)
    batch_fp = batch_fingerprint(manifests.values())
    run_name = run_folder_name(run_time, batch_fp)
    run_dirs = {}
    for k in outputs:                                  # one new run folder per output folder
        parent = args.out_dirs[k]
        if parent not in run_dirs:
            run_dirs[parent] = new_run_folder(parent, run_name)
        args.out_dirs[k] = run_dirs[parent]

    print(f"Historical folder: {args.hist}")
    print(f"Simulator folder:  {args.sim}")
    print(f"Code version:      {code['code_version']}")
    if code['git_commit'] is None or code['git_commit'].endswith('-dirty'):
        print("⚠️ Code is not a clean git commit - outputs are tied to the source hash only.")
    print(f"Run folder:        {run_name}   (batch fingerprint {batch_fp[:12]})")
    print(f"Outputs:           {', '.join(outputs) or 'none (checks only)'}")
    for k in outputs:
        print(f"  {k:<9} -> {args.out_dirs[k]}")
    print(f"Indices to run:    {len(todo)} of {len(rows)}")

    results, n_run, records = [], 0, []
    try:
        for name, hist_file, sim_file, reason in rows:
            if reason is not None:
                results.append((name, 'skipped', reason))
                records.append({'index_id': name, 'status': 'skipped', 'reason': reason})
                continue
            n_run += 1
            m = manifests[name]
            print('\n' + '#' * 70 + f'\n# {name}   ({n_run}/{len(todo)})\n'
                  f'#   hist: {hist_file.name}\n#   sim:  {sim_file.name}\n'
                  f'#   run:  {m["run_id"]}\n' + '#' * 70)
            t0 = time.perf_counter()
            try:
                written = run_index(name, hist_file, sim_file, args, m) or []
                results.append((name, 'ok', f'{time.perf_counter() - t0:.1f}s  ' +
                                ', '.join(Path(w).name for w in written)))
                records.append({**m, 'status': 'ok', 'outputs': [Path(w).name for w in written]})
            except Exception as exc:  # keep going with the other indices
                traceback.print_exc()
                results.append((name, 'FAILED', f'{type(exc).__name__}: {exc}'))
                records.append({**m, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'})
                if args.stop_on_error:
                    break
    finally:
        payload = {'run_folder': run_name, 'run_timestamp_utc': run_time.isoformat(timespec='seconds'),
                   'script': Path(script_file).name, **code, 'batch_fingerprint': batch_fp,
                   'options': base_options(args), 'outputs': outputs, 'indices': records}
        for folder in run_dirs.values():
            write_manifest_json(folder, payload)

    print('\n' + '=' * 70 + '\nBATCH SUMMARY\n' + '=' * 70)
    for name, status, detail in results:
        print(f'{name:<14} {status:<8} {detail}')
    n_fail = sum(s == 'FAILED' for _, s, _ in results)
    print(f"\n{sum(s == 'ok' for _, s, _ in results)} ok, "
          f"{sum(s == 'skipped' for _, s, _ in results)} skipped, {n_fail} failed")
    print(f"Run folder: {run_name}")
    return 1 if n_fail else 0
