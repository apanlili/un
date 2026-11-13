"""
Metadata Compare - script version of 'Metadata Compare.ipynb', run over two folders.

Pairs Metadata_Automation_<index>.xlsx files from two folders by index (by default
the original script outputs vs the Snippet 2 outputs) and compares each pair the
way the notebook does:
  Overall Summary    - bucket counts / % side by side + percentage-point change
  KPI Comparison     - Bucket A % per KPI (+ A1 and A+A1, which Snippet 2 changes)
  Country Comparison - ESCWA A match % (A + A1) per country
Delta = folder 2 minus folder 1, in percentage points.

All indices are merged into one workbook (Index column first), with an
'Index Overview' sheet (one row per index) and a 'Structure Checks' sheet.

Examples
--------
  python metadata_compare.py
  python metadata_compare.py --dir1 "D:/out/a" --dir2 "D:/out/b" --suffix2 "" --label1 run_a --label2 run_b
  python metadata_compare.py --per-index        # also one notebook-style file per index
"""
import os
os.environ.setdefault('MPLBACKEND', 'Agg')

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from utils.batch import DEFAULT_DATA_ROOT, utf8_console
from utils.excel_functions import write_dataframes_to_excel_v2
from datetime import datetime, timezone

from utils.index_files import DATA_FILES, ESCWA_MEMBERS
from utils.run_stamp import (code_version, file_input, make_run_manifest, batch_fingerprint, run_folder_name,
                             new_run_folder, ensure_new, run_info_df, read_run_id, write_manifest_json,
                             RUN_INFO_SHEET)   # Snippet 3

escwa_members = ESCWA_MEMBERS

overall_summary_sheet = 'Summary Stats'
kpi_summary_sheet = 'KPI Data Summary'
country_summary_sheet = 'Summary Stats by Country'
metadata_sheet = 'Metadata_automated'
sheet_names = [overall_summary_sheet, kpi_summary_sheet, country_summary_sheet]

# Rename the category labels (these are row values, not column headers)
col_renames = {
    'A_total'                         : 'Bucket A: Data timely and accurate',
    'A1_cap_adjusted_match'           : 'Bucket A1: Data timely and accurate but capped',
    'B_total'                         : 'Bucket B: Data old but accurate',
    'C_data_available_no_match'       : 'Bucket C: Historical data available but no match',
    'D_possible_impute'               : 'Bucket D: Expert judgement / imputed',
    'E_no_historical_data'            : 'Bucket E: No Historical data available (Report data available)',
    'F_no_report_data'                : 'Bucket F: No Report data available (Historical data available)',
    'G_no_historical_and_report_data' : 'Bucket G: Neither Historical nor Report data available',
}
BUCKET_SHORT = dict(zip(col_renames, ['A', 'A1', 'B', 'C', 'D', 'E', 'F', 'G']))

PREFIX = 'Metadata_Automation_'


def suffix_columns(df, suffix, keep=()):
    """Append '_<suffix>' to every column except those in `keep` (e.g. join keys)."""
    return df.rename(columns={c: f"{c}_{suffix}" for c in df.columns if c not in keep})


def drop_total(df, key):
    """Remove the total row(s)."""
    return df[~df[key].astype(str).str.strip().str.lower().str.startswith('total')]


def side_by_side(df1, key1, df2, key2, index_name):
    """Join side by side on the key, keeping file 1's row order; rows only in file 2 go at the end."""
    idx1 = df1[key1].tolist()
    idx2 = [k for k in df2[key2].tolist() if k not in idx1]
    return (
        df1.set_index(key1)
           .join(df2.set_index(key2), how='outer', sort=False)
           .reindex(idx1 + idx2)
           .rename_axis(index_name)
           .reset_index()
    )


def structure_checks(metadata_1, metadata_2, n1, n2):
    """Notebook structure checks (on the ORIGINAL column names). Prints and returns one row per sheet."""
    rows = []
    for name in sheet_names:
        df1, df2 = metadata_1[name], metadata_2[name]
        print(f"\n=== {name} ===")
        print(f"Shape: {n1}={df1.shape}, {n2}={df2.shape}")

        cols1, cols2 = set(df1.columns), set(df2.columns)
        same_ncols = df1.shape[1] == df2.shape[1]
        print(f"✅ Same number of columns ({df1.shape[1]})" if same_ncols else
              f"⚠️ Column count differs: {n1}={df1.shape[1]}, {n2}={df2.shape[1]}")

        only_1 = sorted(cols1 - cols2, key=str)
        only_2 = sorted(cols2 - cols1, key=str)
        if cols1 == cols2:
            print("✅ Same column names")
        else:
            print("⚠️ Column names differ")
            if only_1:
                print(f"   Only in {n1}: {only_1}")
            if only_2:
                print(f"   Only in {n2}: {only_2}")

        same_order = cols1 == cols2 and list(df1.columns) == list(df2.columns)
        if cols1 == cols2:
            print("✅ Same column order" if same_order else "⚠️ Same columns but different order")

        shared = [c for c in df1.columns if c in cols2]
        dtype_diffs = {c: (str(df1[c].dtype), str(df2[c].dtype)) for c in shared if df1[c].dtype != df2[c].dtype}
        if not dtype_diffs:
            print("✅ Same dtypes on shared columns")
        else:
            print("⚠️ Dtype differences:")
            for c, (d1, d2) in dtype_diffs.items():
                print(f"   {c}: {n1}={d1}, {n2}={d2}")

        same_nrows = df1.shape[0] == df2.shape[0]
        print(f"✅ Same number of rows ({df1.shape[0]})" if same_nrows else
              f"⚠️ Row count differs: {n1}={df1.shape[0]}, {n2}={df2.shape[0]}")

        rows.append({
            'Sheet': name,
            f'rows_{n1}': df1.shape[0], f'rows_{n2}': df2.shape[0],
            f'cols_{n1}': df1.shape[1], f'cols_{n2}': df2.shape[1],
            'same_rows': same_nrows, 'same_columns': cols1 == cols2, 'same_column_order': same_order,
            f'only_in_{n1}': ', '.join(map(str, only_1)), f'only_in_{n2}': ', '.join(map(str, only_2)),
            'dtype_differences': '; '.join(f'{c}: {d1} vs {d2}' for c, (d1, d2) in dtype_diffs.items()),
        })
    return pd.DataFrame(rows)


def compare_pair(metadata_file_1_path, metadata_file_2_path, metadata_1_name, metadata_2_name):
    """Notebook cells 2-7 for one pair of files. Returns the comparison tables."""
    n1, n2 = metadata_1_name, metadata_2_name

    # ISO -> Country lookup from the first two columns (Country, ISO) of the metadata sheet, both files combined
    iso_country = pd.concat([
        pd.read_excel(p, sheet_name=metadata_sheet, usecols=[0, 1])
        for p in (metadata_file_1_path, metadata_file_2_path)
    ]).drop_duplicates()
    iso_to_country = dict(zip(iso_country['ISO'], iso_country['Country']))

    # ESCWA members that appear in the data
    escwa_iso_to_country = {iso: iso_to_country[iso] for iso in escwa_members if iso in iso_to_country}
    escwa_missing = [iso for iso in escwa_members if iso not in iso_to_country]
    print(f"ESCWA members in data: {len(escwa_iso_to_country)}/{len(escwa_members)}")
    if escwa_missing:
        print(f"   Not in data: {escwa_missing}")

    # Read each sheet of each file into its own DataFrame
    metadata_1 = pd.read_excel(metadata_file_1_path, sheet_name=sheet_names)
    metadata_2 = pd.read_excel(metadata_file_2_path, sheet_name=sheet_names)

    checks = structure_checks(metadata_1, metadata_2, n1, n2)

    # Add the metadata name to the column names
    metadata_1 = {s: suffix_columns(df, n1) for s, df in metadata_1.items()}
    metadata_2 = {s: suffix_columns(df, n2) for s, df in metadata_2.items()}

    ##########################
    #### Overall Summary #####
    ##########################
    df1 = metadata_1[overall_summary_sheet].copy()
    df2 = metadata_2[overall_summary_sheet].copy()
    key1, key2 = df1.columns[0], df2.columns[0]          # Category
    df1, df2 = drop_total(df1, key1), drop_total(df2, key2)

    overall_summary_df = side_by_side(df1, key1, df2, key2, 'Metric')
    pct1, pct2 = df1.columns[2], df2.columns[2]          # Percentage
    overall_summary_df[pct1] = pd.to_numeric(overall_summary_df[pct1], errors='coerce')
    overall_summary_df[pct2] = pd.to_numeric(overall_summary_df[pct2], errors='coerce')
    overall_summary_df['pct_change_delta'] = (overall_summary_df[pct2] - overall_summary_df[pct1]).round(2)
    overall_summary_df['Metric'] = overall_summary_df['Metric'].replace(col_renames)

    ########################
    #### KPI Comparison ####
    ########################
    id1, name1 = f'KPI ID_{n1}', f'Series Name_{n1}'
    id2, name2 = f'KPI ID_{n2}', f'Series Name_{n2}'
    # Notebook compares pct_A; A1 and A+A1 are added because Snippet 2 moves records between A/B and A1
    pct_cols = ['pct_A', 'pct_A1_cap_adj']
    df1 = metadata_1[kpi_summary_sheet][[id1, name1] + [f'{c}_{n1}' for c in pct_cols]].copy()
    df2 = metadata_2[kpi_summary_sheet][[id2, name2] + [f'{c}_{n2}' for c in pct_cols]].copy()

    kpi_summary_df = side_by_side(df1, id1, df2, id2, 'KPI ID')
    # Single Series Name column (fall back to file 2 name for KPIs only in file 2)
    kpi_summary_df.insert(1, 'Series Name', kpi_summary_df[name1].fillna(kpi_summary_df[name2]))
    kpi_summary_df = kpi_summary_df.drop(columns=[name1, name2])
    for c in pct_cols:
        for n in (n1, n2):
            kpi_summary_df[f'{c}_{n}'] = pd.to_numeric(kpi_summary_df[f'{c}_{n}'], errors='coerce')
    for n in (n1, n2):
        kpi_summary_df[f'pct_A_A1_{n}'] = (kpi_summary_df[f'pct_A_{n}'] + kpi_summary_df[f'pct_A1_cap_adj_{n}']).round(2)
    kpi_summary_df['pct_A_change_delta'] = (kpi_summary_df[f'pct_A_{n2}'] - kpi_summary_df[f'pct_A_{n1}']).round(2)
    kpi_summary_df['pct_A1_change_delta'] = (kpi_summary_df[f'pct_A1_cap_adj_{n2}'] - kpi_summary_df[f'pct_A1_cap_adj_{n1}']).round(2)
    kpi_summary_df['pct_A_A1_change_delta'] = (kpi_summary_df[f'pct_A_A1_{n2}'] - kpi_summary_df[f'pct_A_A1_{n1}']).round(2)
    kpi_summary_df = kpi_summary_df[['KPI ID', 'Series Name',
                                     f'pct_A_{n1}', f'pct_A1_cap_adj_{n1}', f'pct_A_A1_{n1}',
                                     f'pct_A_{n2}', f'pct_A1_cap_adj_{n2}', f'pct_A_A1_{n2}',
                                     'pct_A_change_delta', 'pct_A1_change_delta', 'pct_A_A1_change_delta']]

    ##############################################
    #### Country Comparison (ESCWA members) ######
    ##############################################
    escwa_country_to_iso = {country: iso for iso, country in escwa_iso_to_country.items()}

    def a_match(df, suffix):
        """ESCWA rows only: ISO, Country and A_match_pct = A_total_pct + A1_cap_adjusted_match_pct (as %, 0-100)."""
        country = f'Country_{suffix}'
        out = df[df[country].isin(escwa_country_to_iso)].copy()
        out['ISO'] = out[country].map(escwa_country_to_iso)
        a_pct = pd.to_numeric(out[f'A_total_pct_{suffix}'], errors='coerce')
        a1_pct = pd.to_numeric(out[f'A1_cap_adjusted_match_pct_{suffix}'], errors='coerce')
        out[f'A_match_pct_{suffix}'] = ((a_pct + a1_pct) * 100).round(2)   # sheet stores fractions
        return out[['ISO', country, f'A_match_pct_{suffix}']]

    df1 = a_match(metadata_1[country_summary_sheet], n1)
    df2 = a_match(metadata_2[country_summary_sheet], n2)

    # Join side by side on ISO, keeping the ESCWA list order
    order = [iso for iso in escwa_members if iso in set(df1['ISO']) | set(df2['ISO'])]
    country_summary_df = (
        df1.set_index('ISO')
           .join(df2.set_index('ISO'), how='outer', sort=False)
           .reindex(order)
           .rename_axis('ISO')
           .reset_index()
    )
    country_summary_df.insert(1, 'Country', country_summary_df[f'Country_{n1}'].fillna(country_summary_df[f'Country_{n2}']))
    country_summary_df = country_summary_df.drop(columns=[f'Country_{n1}', f'Country_{n2}'])
    country_summary_df['A_match_pct_change_delta'] = (
        country_summary_df[f'A_match_pct_{n2}'] - country_summary_df[f'A_match_pct_{n1}']
    ).round(2)

    return {
        'Overall Summary': overall_summary_df,
        'KPI Comparison': kpi_summary_df,
        'Country Comparison': country_summary_df,
        'Structure Checks': checks,
    }


def index_overview(index_name, overall_summary_df, n1, n2):
    """One row per index: A+A1 % for both files and the percentage-point change per bucket."""
    labels = {v: BUCKET_SHORT[k] for k, v in col_renames.items()}
    o = overall_summary_df[overall_summary_df['Metric'].isin(labels)].copy()
    o['bucket'] = o['Metric'].map(labels)
    p1 = o.set_index('bucket')[f'Percentage_{n1}']
    p2 = o.set_index('bucket')[f'Percentage_{n2}']
    row = {'Index': index_name,
           'records': int(pd.to_numeric(o[f'Count_{n1}'], errors='coerce').sum()),
           f'A_A1_pct_{n1}': round(p1.get('A', 0) + p1.get('A1', 0), 2),
           f'A_A1_pct_{n2}': round(p2.get('A', 0) + p2.get('A1', 0), 2)}
    row['A_A1_delta'] = round(row[f'A_A1_pct_{n2}'] - row[f'A_A1_pct_{n1}'], 2)
    row['net_bucket_shift_pct'] = round((p2 - p1).abs().sum() / 2, 2)   # net % of records that changed bucket
    for b in BUCKET_SHORT.values():
        row[f'{b}_delta'] = round(p2.get(b, 0) - p1.get(b, 0), 2)
    return row


def formatting(n1, n2, sheets):
    delta = {
        'Index Overview': ['A_A1_delta'] + [f'{b}_delta' for b in BUCKET_SHORT.values()],
        'Overall Summary': ['pct_change_delta'],
        'KPI Comparison': ['pct_A_change_delta', 'pct_A1_change_delta', 'pct_A_A1_change_delta'],
        'Country Comparison': ['A_match_pct_change_delta'],
    }
    shade = {
        'Index Overview': [[f'A_A1_pct_{n1}'], [f'A_A1_pct_{n2}']],
        'Overall Summary': [[f'Count_{n1}', f'Percentage_{n1}'], [f'Count_{n2}', f'Percentage_{n2}']],
        'KPI Comparison': [[f'pct_A_{n1}', f'pct_A1_cap_adj_{n1}', f'pct_A_A1_{n1}'],
                           [f'pct_A_{n2}', f'pct_A1_cap_adj_{n2}', f'pct_A_A1_{n2}']],
        'Country Comparison': [[f'A_match_pct_{n1}'], [f'A_match_pct_{n2}']],
    }
    return ({k: v for k, v in delta.items() if k in sheets},
            {k: v for k, v in shade.items() if k in sheets})


def pair_files(dir1, dir2, suffix1, suffix2):
    """{index: (file1, file2)} for indices present in both folders, in utils/index_files.py order."""
    def keyed(folder, suffix):
        out = {}
        for f in folder.glob(f'{PREFIX}*.xlsx'):
            if f.name.startswith('~$'):
                continue
            stem = f.stem[len(PREFIX):]
            if suffix:
                if not stem.endswith(suffix):
                    continue
                stem = stem[:-len(suffix)]
            out[stem] = f
        return out
    f1, f2 = keyed(dir1, suffix1), keyed(dir2, suffix2)
    order = list(DATA_FILES)
    common = sorted(set(f1) & set(f2), key=lambda k: (order.index(k) if k in order else len(order), k))
    return {k: (f1[k], f2[k]) for k in common}, sorted(set(f1) - set(f2)), sorted(set(f2) - set(f1))


def resolve_input_dir(folder: Path) -> Path:
    """Use the folder itself if it holds metadata files, otherwise its newest run subfolder (Snippet 3 layout)."""
    if any(folder.glob(f'{PREFIX}*.xlsx')):
        return folder
    runs = sorted(d for d in folder.iterdir() if d.is_dir() and any(d.glob(f'{PREFIX}*.xlsx')))
    if not runs:
        sys.exit(f'No {PREFIX}*.xlsx files in {folder} or its run subfolders')
    return runs[-1]


def pair_manifest(index_name, file1, file2, n1, n2, code, run_time):
    inputs = []
    for label, f in ((n1, file1), (n2, file2)):
        item = file_input(f'metadata_{label}', f)
        item['source_run_id'] = read_run_id(f)
        inputs.append(item)
    return make_run_manifest(index_id=index_name, edition=f'{n1}_vs_{n2}', code=code, inputs=inputs,
                             options={'label1': n1, 'label2': n2}, run_time=run_time)


def main(argv=None):
    utf8_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dir1', type=Path, default=DEFAULT_DATA_ROOT / 'Metadata Automation - script',
                   help='Folder 1 (baseline). Default: <data>/Metadata Automation - script')
    p.add_argument('--dir2', type=Path, default=DEFAULT_DATA_ROOT / 'Metadata Automation Snippet2 - script',
                   help='Folder 2 (compared). Default: <data>/Metadata Automation Snippet2 - script')
    p.add_argument('--suffix1', default='', help="File name suffix in folder 1 (default: none)")
    p.add_argument('--suffix2', default='_snippet2', help="File name suffix in folder 2 (default: _snippet2)")
    p.add_argument('--label1', default='original', help='Column label for folder 1 (default: original)')
    p.add_argument('--label2', default='snippet2', help='Column label for folder 2 (default: snippet2)')
    p.add_argument('--index', nargs='+', metavar='NAME', help='Only compare these indices')
    p.add_argument('--out', type=Path, default=DEFAULT_DATA_ROOT / 'Metadata Comparison - script',
                   help='Output folder (default: <data>/Metadata Comparison - script). '
                        'Each run creates a new <date-time>_<fingerprint> subfolder.')
    p.add_argument('--per-index', action='store_true',
                   help='Also write one notebook-style comparison file per index')
    args = p.parse_args(argv)
    n1, n2 = args.label1, args.label2

    for d in (args.dir1, args.dir2):
        if not d.is_dir():
            sys.exit(f'Folder not found: {d}')
    args.dir1, args.dir2 = resolve_input_dir(args.dir1), resolve_input_dir(args.dir2)
    pairs, only1, only2 = pair_files(args.dir1, args.dir2, args.suffix1, args.suffix2)
    if args.index:
        missing = [i for i in args.index if i not in pairs]
        if missing:
            sys.exit(f'No file pair for: {missing}. Pairs found: {list(pairs)}')
        pairs = {k: pairs[k] for k in args.index}
    print(f"Folder 1 ({n1}): {args.dir1}\nFolder 2 ({n2}): {args.dir2}")
    print(f"Pairs: {len(pairs)}" + (f" | only in folder 1: {only1}" if only1 else '')
          + (f" | only in folder 2: {only2}" if only2 else ''))
    if not pairs:
        sys.exit('Nothing to compare.')

    # --- Snippet 3: fingerprint every pair, then a new run folder ---
    code = code_version(__file__)
    run_time = datetime.now(timezone.utc)
    manifests = {k: pair_manifest(k, f1, f2, n1, n2, code, run_time) for k, (f1, f2) in pairs.items()}
    batch_fp = batch_fingerprint(manifests.values())
    run_dir = new_run_folder(args.out, run_folder_name(run_time, batch_fp))
    print(f"Code version: {code['code_version']}" + chr(10) + f"Run folder:   {run_dir}")

    merged = {k: [] for k in ['Overall Summary', 'KPI Comparison', 'Country Comparison', 'Structure Checks']}
    overview, failed = [], []
    for i, (index_name, (file1, file2)) in enumerate(pairs.items(), 1):
        print('\n' + '#' * 70 + f'\n# {index_name}   ({i}/{len(pairs)})\n#   1: {file1.name}\n#   2: {file2.name}\n' + '#' * 70)
        try:
            res = compare_pair(file1, file2, n1, n2)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            failed.append((index_name, f'{type(exc).__name__}: {exc}'))
            continue
        overview.append(index_overview(index_name, res['Overall Summary'], n1, n2))
        for sheet, df in res.items():
            merged[sheet].append(df.assign(Index=index_name)[['Index'] + list(df.columns)])
        if args.per_index:
            per = {k: v for k, v in res.items() if k != 'Structure Checks'}
            delta, shade = formatting(n1, n2, per)
            per[RUN_INFO_SHEET] = run_info_df(manifests[index_name])
            write_dataframes_to_excel_v2(per, output_path=ensure_new(run_dir / f'Metadata_Comparison_{index_name}_{n1}_vs_{n2}.xlsx'),
                                         delta_cols=delta, shade_cols=shade)

    if overview:
        sheets = {'Index Overview': pd.DataFrame(overview)}
        sheets.update({k: pd.concat(v, ignore_index=True) for k, v in merged.items()})
        delta, shade = formatting(n1, n2, sheets)
        # One Run Info table for the merged workbook: one row per index and input file
        sheets[RUN_INFO_SHEET] = pd.DataFrame([
            {'Index': k, 'run_id': m['run_id'], 'input_fingerprint': m['input_fingerprint'],
             'role': i['role'], 'file': i['name'], 'sha256': i['sha256'], 'source_run_id': i['source_run_id']}
            for k, m in manifests.items() for i in m['inputs']])
        sheets[RUN_INFO_SHEET].insert(0, 'code_version', code['code_version'])
        out_file = ensure_new(run_dir / f'Metadata_Comparison_{n1}_vs_{n2}.xlsx')
        write_dataframes_to_excel_v2(sheets, output_path=out_file, delta_cols=delta, shade_cols=shade)

    write_manifest_json(run_dir, {
        'run_folder': run_dir.name, 'run_timestamp_utc': run_time.isoformat(timespec='seconds'),
        'script': Path(__file__).name, **code, 'batch_fingerprint': batch_fp,
        'dir1': str(args.dir1), 'dir2': str(args.dir2),
        'indices': [{**m, 'status': 'failed' if k in dict(failed) else 'ok'} for k, m in manifests.items()]})

    print('\n' + '=' * 70 + f'\nCOMPARISON SUMMARY: {len(overview)} compared, {len(failed)} failed\n' + '=' * 70)
    if overview:
        print(pd.DataFrame(overview)[['Index', f'A_A1_pct_{n1}', f'A_A1_pct_{n2}', 'A_A1_delta',
                                      'net_bucket_shift_pct']].to_string(index=False))
    for name, err in failed:
        print(f'FAILED {name}: {err}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
