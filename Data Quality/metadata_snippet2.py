"""
Metadata Automation - Snippet 2 (UCE cap/floor bounds) - script version of
'Metadata Automation - Snippet 2.ipynb'.

Same as metadata_automation.py, plus DQP Batch 1 Snippet 2:
- Caps/floors come from the UCE bounds extract (Changes/DQP_UCE_Bounds_Extract_v41_2026-11-01.csv)
  via utils/bound_rules.py.
- A1 is evaluated before A/B is finalised and takes precedence (A1_overrode_A_B records overridden matches).
- Only report-value bounds (RAW_PRETRANSFORM_CLIP, RAW_TRUNCATE) can produce A1; all other bounds are
  flagged in uce_beyond_bound only.
- Legacy A1 logic is kept and runs with --legacy-a1.
- Outputs are written with the _snippet2 suffix (change with --suffix).

Examples
--------
  python metadata_snippet2.py
  python metadata_snippet2.py --hist "D:/data/Historical" --sim "D:/data/Simulator Data" --index index_9 --ispar

Outputs (per index)
  Metadata_Automation_<index>_snippet2.xlsx    default on   (--no-metadata to turn off)
  Profile_Input_ISPAR_<index>_snippet2.xlsx    default off  (--ispar)
  Profile_ESCWA_<index>_snippet2.xlsx          default off  (--profile)
"""
import os
os.environ.setdefault('MPLBACKEND', 'Agg')   # outlier plots are rendered off-screen

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from utils.batch import build_parser, resolve, run_batch, utf8_console
from utils.index_files import ESCWA_MEMBERS, UCE_VINTAGES
from utils.bound_rules import load_uce_bounds, empty_uce_bounds, uce_beyond_bound, uce_a1_mask   # Snippet 2
from utils.outlier_detection import detect_outliers_by_series
from utils.formatting_functions import (
    format_simulator_data, format_historical_kpi_data, get_simulator_data_cap,
    get_kpi_country_summary, get_match_data, get_kpi_totals, get_kpi_year_stats,
    get_summary_stats, run_exact_match_checks,
    profile_data_quality_summary, profile_quality_summary_table,
)
from utils.excel_functions import write_dataframes_to_excel, write_country_sheets_to_excel
from utils.ispar_profile import get_profile_data_ispar, MAJORITY_THRESHOLD
from utils.run_stamp import run_info_df, append_run_info, ensure_new, file_input, RUN_INFO_SHEET   # Snippet 3

DEFAULT_UCE_BOUNDS_CSV = Path(__file__).resolve().parent / 'Changes' / 'DQP_UCE_Bounds_Extract_v41_2026-11-01.csv'

escwa_members = ESCWA_MEMBERS

# Bucket column -> label used in the country profile outputs
COL_RENAMES = {'A_total'                            : 'Bucket A: Data timely and accurate',
               'A1_cap_adjusted_match'              : 'Bucket A1: Data timely and accurate but capped',
               'B_total'                            : 'Bucket B: Data old but accurate',
               'C_data_available_no_match'          : 'Bucket C: Historical data available but no match',
               'D_possible_impute'                  : 'Bucket D: Expert judgement / imputed',
               'E_no_historical_data'               : 'Bucket E: No Historical data available (Report data available)',
               'F_no_report_data'                   : 'Bucket F: No Report data available (Historical data available)',
               'G_no_historical_and_report_data'    : 'Bucket G: Neither Historical nor Report data available'}


#####################################################
########## Data Checks and Validation ###############
#####################################################
def compare_kpi_sets(historical_long, simulator_data, kpi_key):
    """Compare KPI IDs between historical and simulator data, with series names."""
    hist_names = (historical_long[['KPI ID', 'Series Name']]
                  .drop_duplicates('KPI ID').set_index('KPI ID')['Series Name'])
    sim_names = kpi_key.drop_duplicates('KPI ID').set_index('KPI ID')['Series Name']

    hist_set = set(historical_long['KPI ID'].unique())
    sim_set = set(simulator_data['KPI ID'].unique())

    only_in_historical = sorted(hist_set - sim_set)
    only_in_simulator = sorted(sim_set - hist_set)

    print('=' * 60)
    print('KPI ID CHECK: historical vs simulator')
    print('=' * 60)
    print(f'Historical KPIs: {len(hist_set)}')
    print(f'Simulator KPIs:  {len(sim_set)}')
    print(f'In both:         {len(hist_set & sim_set)}')
    print()

    print(f'In SIMULATOR but MISSING from HISTORICAL ({len(only_in_simulator)}):')
    for kpi in only_in_simulator:
        print(f'   {kpi:>6}  {sim_names.get(kpi, "(no name in kpi_key)")}')
    if not only_in_simulator:
        print('   none')
    print()

    print(f'In HISTORICAL but MISSING from SIMULATOR ({len(only_in_historical)}):')
    for kpi in only_in_historical:
        print(f'   {kpi:>6}  {hist_names.get(kpi, "(no name)")}')
    if not only_in_historical:
        print('   none')
    print()

    passed = not only_in_simulator and not only_in_historical
    print('RESULT:', '✅ PASS, same KPI set' if passed else '⚠️ FAIL, KPI sets differ')
    print('=' * 60)

    report = pd.DataFrame(
        [{'KPI ID': k, 'Series Name': sim_names.get(k), 'Missing from': 'Historical'}
         for k in only_in_simulator] +
        [{'KPI ID': k, 'Series Name': hist_names.get(k), 'Missing from': 'Simulator'}
         for k in only_in_historical],
        columns=['KPI ID', 'Series Name', 'Missing from'])
    return report


def run_index(index_name, index_historical_kpi_data_path, index_simulator_data_path, args, manifest):
    """Notebook cells 3-26 for one index. Returns the list of files written."""
    only_escwa_countries = args.escwa_only
    OUTPUT_SUFFIX = args.suffix
    written = []

    # Snippet 2 - UCE authoritative cap/floor bounds (config)
    # True  -> A1 uses the UCE bounds extract (single source of truth) and takes precedence over A/B
    # False -> legacy A1 logic (cap inferred from simulator data via get_simulator_data_cap)
    USE_UCE_BOUNDS = not args.legacy_a1
    UCE_BOUNDS_CSV = args.uce_csv
    uce_vintage = UCE_VINTAGES.get(index_name)

    ###############
    #### Setup ####
    ###############
    # Read raw data
    historical_kpi_data_raw = pd.read_excel(index_historical_kpi_data_path)
    simulator_data_raw = pd.read_excel(index_simulator_data_path)

    kpi_key = (simulator_data_raw.iloc[0]
               .rename('Series Name')
               .rename_axis('KPI ID')
               .reset_index()
               .dropna(subset=['Series Name']))
    kpi_key['Series Name'] = kpi_key['Series Name'].astype(str).str.strip()
    kpi_key['KPI ID'] = kpi_key['KPI ID'].astype(str).str.strip()
    kpi_list = kpi_key['KPI ID'].unique().tolist()

    ###############################################
    #### Format Simulator and Historical Data #####
    ###############################################
    if args.from_db:
        from utils.db_functions import get_connection_string, get_latest_sim_data, get_latest_hist_data
        connection_string = get_connection_string(env=args.db_env)
        # Simulator Data
        simulator_data = get_latest_sim_data(connection_string, kpi_list)

        # Historical KPI Data
        historical_kpi_data_long = get_latest_hist_data(connection_string, kpi_list)
        historical_kpi_data_long['data_historical_automated'] = pd.to_numeric(
            historical_kpi_data_long['data_historical_automated'], errors='coerce').astype('Float64')
        historical_kpi_data_long['KPI ID'] = historical_kpi_data_long['KPI ID'].astype(str).str.strip()
        historical_kpi_data_long['year_historical_automated'] = pd.to_numeric(
            historical_kpi_data_long['year_historical_automated'], errors='coerce').astype('Int64')
    else:
        simulator_data = format_simulator_data(simulator_data_raw, kpi_key,
                                               pivot_names=('Country', 'ISO', 'Region', 'Sub-region', 'Income Type'))
        historical_kpi_data_long = format_historical_kpi_data(historical_kpi_data_raw, iso_filter=None)
    historical_kpi_data_long_escwa = historical_kpi_data_long[historical_kpi_data_long['ISO'].isin(escwa_members)]

    kpi_mismatch_report = compare_kpi_sets(historical_kpi_data_long, simulator_data, kpi_key)

    #############################################
    #### Reference Tables + Outlier Detection ###
    #############################################
    # Simulator Data Cap/Floor
    simulator_data_cap = get_simulator_data_cap(simulator_data, historical_kpi_data_long)   # legacy (kept for reference columns)

    # Snippet 2 - UCE authoritative bounds
    if USE_UCE_BOUNDS:
        uce_bounds = load_uce_bounds(UCE_BOUNDS_CSV, uce_vintage)
        print(f"UCE bounds for {index_name} ({uce_vintage}): {len(uce_bounds)} KPIs, "
              f"{int(uce_bounds['uce_a1_eligible'].sum())} A1-eligible")
        if uce_vintage is None or uce_bounds.empty:
            print("⚠️ No UCE bounds for this index - no A1 will be assigned.")
    else:
        uce_bounds = empty_uce_bounds()

    # Summary KPI/Country data
    kpi_country_summary_df = get_kpi_country_summary(historical_kpi_data_long)

    # Match Data - to be used for bucketing records
    match_data = get_match_data(simulator_data, historical_kpi_data_long, kpi_country_summary_df)

    # Newest KPI Data for each country
    newest_kpi_data = historical_kpi_data_long.copy()
    newest_kpi_data = newest_kpi_data.dropna(subset=['data_historical_automated'])                            # drop na
    newest_kpi_data = newest_kpi_data[
        newest_kpi_data['year_historical_automated'] ==
        newest_kpi_data.groupby(['ISO', 'KPI ID'])['year_historical_automated'].transform('max')]
    newest_kpi_data = newest_kpi_data[['KPI ID', 'ISO', 'year_historical_automated', 'data_historical_automated']]
    newest_kpi_data = newest_kpi_data.rename(columns={'year_historical_automated': 'most_recent_year',
                                                      'data_historical_automated': 'most_recent_data'})

    # Detected Outliers
    start_time = time.perf_counter()

    # Columns downstream code expects
    OUTLIER_MARKER_COLS = ['KPI ID', 'ISO', 'year_inferred', 'outlier_detected']

    # Exclude categorical KPIs
    kpi_categorical = (
        simulator_data_cap[simulator_data_cap['unique_categorical_values_simulator'].notna()]['KPI ID']
        .unique()
        .tolist()
    )

    # Filter to non-categorical KPIs for ESCWA countries
    kpi_data_for_outliers = historical_kpi_data_long_escwa[
        ~historical_kpi_data_long_escwa['KPI ID'].isin(kpi_categorical)
    ]

    if kpi_data_for_outliers.empty:
        print(f"Outlier detection skipped: all {historical_kpi_data_long_escwa['KPI ID'].nunique()} "
              f"KPIs in the ESCWA data are categorical.")
        outliers = pd.DataFrame()
        outliers_marker = pd.DataFrame(columns=OUTLIER_MARKER_COLS)
    else:
        outliers = detect_outliers_by_series(kpi_data_for_outliers)

        # Also guard against the detector returning nothing / no flag column
        if outliers is None or outliers.empty or 'outlier_total' not in outliers.columns:
            print("Outlier detection returned no results; no outliers flagged.")
            outliers = pd.DataFrame() if outliers is None else outliers
            outliers_marker = pd.DataFrame(columns=OUTLIER_MARKER_COLS)
        else:
            outliers_marker = outliers[outliers['outlier_total'] >= 3].copy().reset_index(drop=True)
            outliers_marker['outlier_detected'] = 1
            outliers_marker = outliers_marker[
                ['KPI ID', 'ISO', 'year_historical_automated', 'outlier_detected']
            ].rename(columns={'year_historical_automated': 'year_inferred'})

    end_time = time.perf_counter()
    print(f"Outlier detection execution time: {end_time - start_time:.6f} seconds")

    ###########################
    #### Recreate metadata ####
    ###########################
    # Start from simulator data
    metadata_automated = simulator_data.copy()
    print(f"Baseline Simulator data structure: {metadata_automated.shape}")
    baseline_sim_len = metadata_automated.shape[0]

    metadata_automated = metadata_automated.merge(kpi_country_summary_df, how='left', on=['KPI ID', 'ISO'])
    metadata_automated = metadata_automated.merge(simulator_data_cap, how='left', on=['KPI ID'])
    metadata_automated = metadata_automated.merge(uce_bounds, how='left', on=['KPI ID'])           # Snippet 2
    metadata_automated = metadata_automated.merge(newest_kpi_data, how='left', on=['KPI ID', 'ISO'])  # Include most recent year
    metadata_automated['uce_beyond_bound'] = uce_beyond_bound(metadata_automated)                 # Snippet 2 - info flag, any bound type
    print(f"Structure after additional data: {metadata_automated.shape}")
    metadata_sim_len = metadata_automated.shape[0]

    if metadata_sim_len != baseline_sim_len:
        print(f"⚠️ Row count changed after merges: {baseline_sim_len} → {metadata_sim_len} "
              f"({metadata_sim_len - baseline_sim_len:+} rows). Check for duplicate keys in the merged tables.")
    else:
        print(f"✅ Confirmed: row count unchanged after merges ({metadata_sim_len} rows).")

    error_tol = 0.01  # 1%
    exact_match = match_data[match_data['exact_match']].copy()
    approx_match = match_data[~match_data['exact_match'] &
                              (match_data['value_difference_percentage'] <= error_tol)].copy()

    # Col Names
    A_exact_year = 'A_exact_year'
    A_exact_data = 'A_exact_data'
    A_exact_value_diff = 'A_exact_value_diff'
    A_exact_value_diff_pct = 'A_exact_value_diff_pct'

    A_approx_year = 'A_approx_year'
    A_approx_data = 'A_approx_data'
    A_approx_value_diff = 'A_approx_value_diff'
    A_approx_value_diff_pct = 'A_approx_value_diff_pct'

    B_exact_year = 'B_exact_year'
    B_exact_data = 'B_exact_data'
    B_exact_value_diff = 'B_exact_value_diff'
    B_exact_value_diff_pct = 'B_exact_value_diff_pct'

    B_approx_year = 'B_approx_year'
    B_approx_data = 'B_approx_data'
    B_approx_value_diff = 'B_approx_value_diff'
    B_approx_value_diff_pct = 'B_approx_value_diff_pct'

    A1_cap_adj_year = 'A1_cap_adj_year'
    A1_cap_adj_data = 'A1_cap_adj_data'
    A1_cap_adj_value_diff = 'A1_cap_adj_value_diff'
    A1_cap_adj_value_diff_pct = 'A1_cap_adj_value_diff_pct'

    match_cols = ['ISO', 'KPI ID', 'year_historical_automated', 'data_historical_automated', 'value_difference', 'value_difference_percentage']

    # A - Most Recent Year & Match
    # A.1 (Exact Match)
    A_exact_match = exact_match[exact_match['latest_year']].copy()
    A_exact_match = A_exact_match[match_cols]
    A_exact_match = A_exact_match.rename(columns={'year_historical_automated': A_exact_year,
                                                  'data_historical_automated': A_exact_data,
                                                  'value_difference': A_exact_value_diff,
                                                  'value_difference_percentage': A_exact_value_diff_pct})
    # A.2 (Approximate Match)
    A_approx_match = approx_match[approx_match['latest_year']].copy()
    A_approx_match = A_approx_match[match_cols]
    A_approx_match = A_approx_match.rename(columns={'year_historical_automated': A_approx_year,
                                                    'data_historical_automated': A_approx_data,
                                                    'value_difference': A_approx_value_diff,
                                                    'value_difference_percentage': A_approx_value_diff_pct})

    # B - Older Year & Match
    # B.1 (Exact Match)
    # - exclude values from A
    exclude_keys = pd.concat([A_exact_match[['ISO', 'KPI ID']], A_approx_match[['ISO', 'KPI ID']]]).drop_duplicates()
    exclude_index = pd.MultiIndex.from_frame(exclude_keys)
    B_exact_match = exact_match[~exact_match['latest_year']].copy()
    B_exact_match = B_exact_match[~pd.MultiIndex.from_frame(B_exact_match[['ISO', 'KPI ID']]).isin(exclude_index)]
    # - Max year value available
    B_exact_match = B_exact_match[
        B_exact_match['year_historical_automated'] ==
        B_exact_match.groupby(['ISO', 'KPI ID'])['year_historical_automated'].transform('max')]
    B_exact_match = B_exact_match[match_cols]
    B_exact_match = B_exact_match.rename(columns={'year_historical_automated': B_exact_year,
                                                  'data_historical_automated': B_exact_data,
                                                  'value_difference': B_exact_value_diff,
                                                  'value_difference_percentage': B_exact_value_diff_pct})
    # B.2 (Approximate Match)
    exclude_keys = pd.concat([A_exact_match[['ISO', 'KPI ID']], A_approx_match[['ISO', 'KPI ID']], B_exact_match[['ISO', 'KPI ID']]]).drop_duplicates()
    exclude_index = pd.MultiIndex.from_frame(exclude_keys)
    B_approx_match = approx_match[~approx_match['latest_year']].copy()
    B_approx_match = B_approx_match[B_approx_match['value_difference_percentage'] <= error_tol]
    B_approx_match = B_approx_match[~pd.MultiIndex.from_frame(B_approx_match[['ISO', 'KPI ID']]).isin(exclude_index)]
    # - Max year value available
    B_approx_match = B_approx_match[
        B_approx_match['year_historical_automated'] ==
        B_approx_match.groupby(['ISO', 'KPI ID'])['year_historical_automated'].transform('max')]
    B_approx_match = B_approx_match[match_cols]
    B_approx_match = B_approx_match.rename(columns={'year_historical_automated': B_approx_year,
                                                    'data_historical_automated': B_approx_data,
                                                    'value_difference': B_approx_value_diff,
                                                    'value_difference_percentage': B_approx_value_diff_pct})

    metadata_automated = metadata_automated.merge(A_exact_match, how='left', on=['KPI ID', 'ISO'])
    metadata_automated = metadata_automated.merge(A_approx_match, how='left', on=['KPI ID', 'ISO'])
    metadata_automated = metadata_automated.merge(B_exact_match, how='left', on=['KPI ID', 'ISO'])
    metadata_automated = metadata_automated.merge(B_approx_match, how='left', on=['KPI ID', 'ISO'])

    # Matched fields
    metadata_automated['A_exact'] = np.where(metadata_automated[A_exact_data].isna(), 0, 1)
    metadata_automated['A_approx'] = np.where(metadata_automated[A_approx_data].isna(), 0, 1)
    metadata_automated['A_total'] = metadata_automated['A_exact'] + metadata_automated['A_approx']

    metadata_automated['B_exact'] = np.where(metadata_automated[B_exact_data].isna(), 0, 1)
    metadata_automated['B_approx'] = np.where(metadata_automated[B_approx_data].isna(), 0, 1)
    metadata_automated['B_total'] = metadata_automated['B_exact'] + metadata_automated['B_approx']

    metadata_automated['A_B_match_total'] = metadata_automated['A_total'] + metadata_automated['B_total']

    # A_1_cap_adjusted match
    if USE_UCE_BOUNDS:
        ##### Snippet 2 - authoritative UCE bound, evaluated before A/B is finalised #####
        # A1: data_report sits on the UCE cap/floor and the most recent historical value is beyond it
        #     (only report-value bounds: RAW_PRETRANSFORM_CLIP / RAW_TRUNCATE).
        a1_mask = uce_a1_mask(metadata_automated, report_col='data_report', hist_col='most_recent_data')

        # A1 takes precedence over A/B: record what was overridden, then clear the A/B match
        metadata_automated['A1_overrode_A_B'] = (a1_mask & (metadata_automated['A_B_match_total'] > 0)).astype(int)
        ab_value_cols = [A_exact_year, A_exact_data, A_exact_value_diff, A_exact_value_diff_pct,
                         A_approx_year, A_approx_data, A_approx_value_diff, A_approx_value_diff_pct,
                         B_exact_year, B_exact_data, B_exact_value_diff, B_exact_value_diff_pct,
                         B_approx_year, B_approx_data, B_approx_value_diff, B_approx_value_diff_pct]
        metadata_automated.loc[a1_mask, ab_value_cols] = np.nan
        metadata_automated.loc[a1_mask, ['A_exact', 'A_approx', 'B_exact', 'B_approx']] = 0
        metadata_automated['A_total'] = metadata_automated['A_exact'] + metadata_automated['A_approx']
        metadata_automated['B_total'] = metadata_automated['B_exact'] + metadata_automated['B_approx']
        metadata_automated['A_B_match_total'] = metadata_automated['A_total'] + metadata_automated['B_total']

        metadata_automated[A1_cap_adj_year] = metadata_automated['most_recent_year'].where(a1_mask)
        metadata_automated[A1_cap_adj_data] = metadata_automated['data_report'].where(a1_mask)
        metadata_automated[A1_cap_adj_value_diff] = np.where(a1_mask, 0, np.nan)      # - value equals the bound, 0 diff
        metadata_automated[A1_cap_adj_value_diff_pct] = np.where(a1_mask, 0, np.nan)
        metadata_automated['A1_cap_adjusted_match'] = a1_mask.astype(int)

        print(f"UCE A1 records: {int(a1_mask.sum())} "
              f"(of which previously A/B: {int(metadata_automated['A1_overrode_A_B'].sum())}); "
              f"records beyond a UCE bound: {int(metadata_automated['uce_beyond_bound'].sum())}")
    else:
        ##### Legacy A1 logic (inferred cap, only when no A/B match) - kept, not active when USE_UCE_BOUNDS #####
        metadata_automated['A1_overrode_A_B'] = 0
        cap_adjusted_match = metadata_automated.copy()
        mask = (
            (cap_adjusted_match['A_B_match_total'] == 0) &                                   # - No A or B match
            (cap_adjusted_match['cap_present'] == 1) &                                       # - cap_present == 1
            (cap_adjusted_match['most_recent_data'].notna()) &                               # - most_recent_data available
            (cap_adjusted_match['most_recent_data'] > cap_adjusted_match['possible_cap']) &  # - most_recent_data > likely_cap
            (cap_adjusted_match['data_report'] == cap_adjusted_match['possible_cap'])        # - data_report == likely_cap
        )
        cap_adjusted_match = cap_adjusted_match[mask]
        cap_adjusted_match[A1_cap_adj_year] = cap_adjusted_match['most_recent_year']
        cap_adjusted_match[A1_cap_adj_data] = cap_adjusted_match['data_report']
        cap_adjusted_match[A1_cap_adj_value_diff] = 0     # - Assume values is the same as data_report, 0 diff
        cap_adjusted_match[A1_cap_adj_value_diff_pct] = 0
        cap_adjusted_match['A1_cap_adjusted_match'] = 1
        # - join into df
        cap_adjusted_match = cap_adjusted_match[['KPI ID', 'ISO', A1_cap_adj_year, A1_cap_adj_data,
                                                 A1_cap_adj_value_diff, A1_cap_adj_value_diff_pct, 'A1_cap_adjusted_match']]
        metadata_automated = metadata_automated.merge(cap_adjusted_match, how='left', on=['KPI ID', 'ISO'])

    metadata_automated['A1_cap_adjusted_match'] = metadata_automated['A1_cap_adjusted_match'].fillna(0)
    metadata_automated['A_A1_B_match_total'] = metadata_automated['A_total'] + metadata_automated['B_total'] + metadata_automated['A1_cap_adjusted_match']

    #### NO MATCH BUCKETS ####
    # Bucket D - possible impute
    # No matches (A, A1, or B) & less than or equal to 5 years of historical data
    metadata_automated['D_possible_impute'] = (
        (metadata_automated['A_A1_B_match_total'] == 0) &  # No A/B/C matches
        (metadata_automated['most_recent_data'].notna()) &  # Historical data exists
        (metadata_automated['nonnull_rows'] <= 5) &         # Less than or equal to 5 yrs historical data
        (metadata_automated['nonnull_pct'] < 50)            # Non-null pct is greater than .50
    ).fillna(False).astype(int)

    no_hist = metadata_automated['most_recent_data'].isna()
    no_report = metadata_automated['data_report'].isna()
    # Bucket E - No historical data exists
    metadata_automated['E_no_historical_data'] = (no_hist & ~no_report).astype(int)
    # Bucket F - No report/simulator data
    metadata_automated['F_no_report_data'] = (no_report & ~no_hist).astype(int)
    # Bucket G - No historical AND report/simulator data
    metadata_automated['G_no_historical_and_report_data'] = (no_hist & no_report).astype(int)
    # - if there is no report data then clear D to 0
    metadata_automated['D_possible_impute'] = np.where(no_report, 0, metadata_automated['D_possible_impute'])

    # Bucket C - everything else
    flag_cols_e = ['A_A1_B_match_total',
                   'D_possible_impute',
                   'E_no_historical_data',
                   'F_no_report_data',
                   'G_no_historical_and_report_data']
    metadata_automated['C_data_available_no_match'] = (
        (metadata_automated[flag_cols_e] == 0).all(axis=1)
    ).fillna(False).astype(int)
    # Values matches for A, B, C_cap_adjusted
    metadata_automated['year_inferred'] = metadata_automated[[A_exact_year, A_approx_year, B_exact_year, B_approx_year, A1_cap_adj_year]].bfill(axis=1).iloc[:, 0]
    metadata_automated['data_inferred'] = metadata_automated[[A_exact_data, A_approx_data, B_exact_data, B_approx_data, A1_cap_adj_data]].bfill(axis=1).iloc[:, 0]
    metadata_automated['year_difference_inferred'] = metadata_automated['most_recent_year'] - metadata_automated['year_inferred']
    metadata_automated['value_difference_inferred'] = metadata_automated[[A_exact_value_diff, A_approx_value_diff,
                                                                          B_exact_value_diff, B_approx_value_diff,
                                                                          A1_cap_adj_value_diff]].bfill(axis=1).iloc[:, 0]
    metadata_automated['value_difference_percentage_inferred'] = metadata_automated[[A_exact_value_diff_pct, A_approx_value_diff_pct,
                                                                                     B_exact_value_diff_pct, B_approx_value_diff_pct,
                                                                                     A1_cap_adj_value_diff_pct]].bfill(axis=1).iloc[:, 0]

    # Final Count (A. B, C, D, E, F buckets)
    metadata_automated['total_buckets'] = metadata_automated[
        ['A_A1_B_match_total', 'C_data_available_no_match', 'D_possible_impute', 'E_no_historical_data', 'F_no_report_data', 'G_no_historical_and_report_data']
    ].sum(axis=1)

    ### Profile Buckets ###
    tol_yr_old = 4
    # Percent Accurate [A + C]
    metadata_automated['Accurate_A_A1'] = metadata_automated['A_total'] + metadata_automated['A1_cap_adjusted_match']
    # Percent Old (Within 4 years of most recent data, could be within 4 years of most recent KPI data)
    metadata_automated['Old_B'] = np.where(
        (metadata_automated['B_total'] == 1) & (metadata_automated['year_difference_inferred'] <= tol_yr_old), 1, 0)
    metadata_automated['Very_Old_B'] = np.where(
        (metadata_automated['B_total'] == 1) & (metadata_automated['year_difference_inferred'] > tol_yr_old), 1, 0)
    # Percent Unmatched (D, E, F)
    metadata_automated['Unmatched_C_D_E_F'] = metadata_automated[
        ['C_data_available_no_match', 'D_possible_impute', 'E_no_historical_data', 'F_no_report_data']
    ].sum(axis=1)
    metadata_automated['total_profile'] = metadata_automated[
        ['Accurate_A_A1', 'Old_B', 'Very_Old_B', 'Unmatched_C_D_E_F']
    ].sum(axis=1)

    # Merge outliers only on matched data values
    metadata_automated = metadata_automated.merge(outliers_marker, how='left')

    print(f"Structure after data quality info: {metadata_automated.shape}")
    metadata_2_sim_len = metadata_automated.shape[0]

    if metadata_2_sim_len != baseline_sim_len:
        print(f"⚠️ Row count changed after data quality merges: {baseline_sim_len} → {metadata_2_sim_len} "
              f"({metadata_2_sim_len - baseline_sim_len:+} rows). Check for duplicate keys in the merged tables.")
    else:
        print(f"✅ Confirmed: row count unchanged after data quality merges ({metadata_2_sim_len} rows).")

    print("Rows (first datapoint) should match")
    bad_buckets = metadata_automated[metadata_automated['total_buckets'] != 1]
    if len(bad_buckets) > 0:
        print(f"⚠️ {len(bad_buckets)} rows are not in exactly one bucket (total_buckets != 1)")
    else:
        print("✅ Confirmed: every row is in exactly one bucket.")
    violations = metadata_automated[
        (metadata_automated['B_total'] == 1) &
        (metadata_automated['most_recent_year'].isna() | metadata_automated['year_inferred'].isna())
    ]

    if len(violations) > 0:
        print(f"⚠️ {len(violations)} rows have B_total==1 but are missing most_recent_year or year_inferred")
    else:
        print("✅ Confirmed: all B_total==1 rows have both most_recent_year and year_inferred.")

    # For Summary sheet
    kpi_year = get_kpi_year_stats(metadata_automated)
    kpi_data = get_kpi_totals(metadata_automated).merge(kpi_year, on='KPI ID', how='left')

    # Final column ordering
    base_cols = ['Country', 'ISO', 'Series Name', 'KPI ID', 'data_report', 'total_rows',
                 'nonnull_rows', 'nonnull_pct', 'latest_year_nonnull', 'possible_cap',
                 'cap_count', 'max_kpi_value_hist', 'possible_floor', 'floor_count', 'cap_present',
                 'n_unique_categorical_simulator', 'unique_categorical_values_simulator',
                 'most_recent_year', 'most_recent_data']
    inferred_cols = ['year_inferred', 'data_inferred', 'year_difference_inferred', 'value_difference_inferred', 'value_difference_percentage_inferred']
    totals_cols = ['A_exact', 'A_approx', 'A_total', 'A1_cap_adjusted_match', 'B_exact', 'B_approx', 'B_total', 'A_B_match_total', 'A_A1_B_match_total',
                   'C_data_available_no_match', 'D_possible_impute', 'E_no_historical_data', 'F_no_report_data', 'G_no_historical_and_report_data', 'total_buckets']
    misc_cols = ['outlier_detected',
                 # Snippet 2 - UCE bounds
                 'uce_floor', 'uce_cap', 'uce_semantics', 'uce_a1_eligible', 'uce_beyond_bound', 'A1_overrode_A_B']

    # All Countries
    metadata_automated = metadata_automated[base_cols + inferred_cols + totals_cols + misc_cols]
    # ESCWA
    metadata_automated_escwa = metadata_automated[metadata_automated['ISO'].isin(escwa_members)].reset_index(drop=True).copy()
    metadata_automated_escwa = metadata_automated_escwa[base_cols + inferred_cols + totals_cols + misc_cols]

    ######################
    #### Outlier Sheet ###
    ######################
    # Only run on ESCWA countries
    detected_outliers = metadata_automated_escwa[
        metadata_automated_escwa['outlier_detected'] == 1
    ].copy()

    # Keys for flagged years
    keys = detected_outliers[['ISO', 'KPI ID', 'year_inferred']].copy()
    keys['flagged_year'] = 'X'
    keys.columns = ['ISO', 'KPI ID', 'year_historical_automated', 'flagged_year']
    keys = keys.drop_duplicates(['ISO', 'KPI ID', 'year_historical_automated'])

    # If ISO / KPI ID ended up in the index, bring them back as columns
    if 'ISO' not in outliers.columns and 'ISO' in (outliers.index.names or []):
        outliers = outliers.reset_index()

    required_cols = {'ISO', 'KPI ID', 'year_historical_automated'}

    if outliers.empty or detected_outliers.empty or not required_cols.issubset(outliers.columns):
        print("No outliers detected (or outlier output missing key columns); outlier sheet will be empty.")
        df_outliers = pd.DataFrame(columns=list(outliers.columns) + ['flagged_year']
                                   if len(outliers.columns) else
                                   ['KPI ID', 'ISO', 'year_historical_automated', 'flagged_year'])
    else:
        # Pull in only series with a detected outlier (one row per series, no duplication)
        series_keys = keys[['ISO', 'KPI ID']].drop_duplicates()
        df_outliers = outliers.merge(series_keys, on=['ISO', 'KPI ID'], how='inner')
        df_outliers = df_outliers.sort_values(
            ['KPI ID', 'ISO', 'year_historical_automated'],
            ascending=[True, True, False]
        ).reset_index(drop=True)

        df_outliers_before_len = df_outliers.shape[0]
        df_outliers = df_outliers.merge(
            keys, on=['ISO', 'KPI ID', 'year_historical_automated'], how='left'
        )
        df_outliers_after_len = df_outliers.shape[0]

        if df_outliers_before_len != df_outliers_after_len:
            print(f"⚠️ Row count changed in outlier df: {df_outliers_before_len} → {df_outliers_after_len} "
                  f"({df_outliers_after_len - df_outliers_before_len:+} rows). "
                  f"Check for duplicate keys in the merged tables.")
        else:
            print(f"✅ Confirmed: row count unchanged after outlier df ({df_outliers_after_len} rows).")

    print(df_outliers.shape)

    ############################
    #### Summary Statistics ####
    ############################
    quality_cols = ['A_total',
                    'A1_cap_adjusted_match',
                    'B_total',
                    'C_data_available_no_match',
                    'D_possible_impute',
                    'E_no_historical_data',
                    'F_no_report_data',
                    'G_no_historical_and_report_data']

    summary_stats, summary_stats_kpi, summary_stats_country = get_summary_stats(
        metadata_automated_escwa if only_escwa_countries else metadata_automated,
        quality_cols, simulator_data,
        only_escwa_countries=only_escwa_countries, escwa_members=escwa_members,
    )

    ###############################
    #### Data Checks and Flags ####
    ###############################
    iso_to_country = dict(zip(metadata_automated["ISO"], metadata_automated["Country"]))
    escwa_countries = [iso_to_country[iso] for iso in escwa_members if iso in iso_to_country]
    summary_country_escwa = summary_stats_country[
        summary_stats_country["Country"].isin(escwa_countries)
    ][["Country", "A_total_pct", "A1_cap_adjusted_match_pct"]]

    overall_check, per_kpi_check, per_escwa_country_check = run_exact_match_checks(
        summary_stats, summary_stats_kpi, summary_country_escwa,
        escwa_members, iso_to_country)

    ##############################################
    #### Metadata Automation Output to file ######
    ##############################################
    if args.write_metadata:
        output_path = args.out_dirs['metadata'] / f"Metadata_Automation_{index_name}{OUTPUT_SUFFIX}.xlsx"

        # only ESCWA countries in long format
        data_long_escwa = historical_kpi_data_long_escwa if only_escwa_countries else historical_kpi_data_long
        metadata_sheet = (metadata_automated_escwa if only_escwa_countries else metadata_automated).copy()

        sheets = {
            'Metadata_automated': metadata_sheet,
            'KPI Data Summary': kpi_data,
            'Summary Stats': summary_stats,
            'Summary Stats by KPI': summary_stats_kpi,
            'Summary Stats by Country': summary_stats_country,
            'Raw Data Long format': data_long_escwa,
            'Outliers data': df_outliers,
            RUN_INFO_SHEET: run_info_df(manifest),   # Snippet 3
        }
        ensure_new(output_path)
        write_dataframes_to_excel(
            sheets,
            output_path=output_path,
            freeze_header=True,
            autofit_columns=True,
            header_bold=True,
            add_borders=True,
            add_autofilter=True,
            index=False,
            plot_df=df_outliers,          # the frame with the plot columns
        )
        written.append(output_path)

    if not (args.write_ispar or args.write_profile):
        return written

    ################################
    #### Country Profile Output ####
    ################################
    quality_cols = list(COL_RENAMES.values())
    metadata_renamed = metadata_automated.rename(columns=COL_RENAMES)

    ###########################################
    #### Country Profile Input into ISPAR #####
    ###########################################
    if args.write_ispar:
        profile_ispar, country_data_tbl_ispar = get_profile_data_ispar(
            metadata_automated_escwa, kpi_data, index_name=index_name,
            old_only=True, threshold=MAJORITY_THRESHOLD,
        )
        country_data_tbl_ispar = country_data_tbl_ispar.rename(columns={"year_inferred": "year_used"})
        country_data_tbl_cols = ['Index_ID', 'Country', 'ISO', 'Series Name', 'KPI ID', 'year_used', 'most_common_year', 'most_common_year_pct',
                                 'Conclusion', 'Assessed']
        country_data_tbl_ispar = country_data_tbl_ispar[country_data_tbl_cols]

        output_path = args.out_dirs['ispar'] / f"Profile_Input_ISPAR_{index_name}{OUTPUT_SUFFIX}.xlsx"
        sheets = {
            'Profile_counts': profile_ispar,
            'Older data table': country_data_tbl_ispar,
            RUN_INFO_SHEET: run_info_df(manifest),   # Snippet 3
        }
        ensure_new(output_path)
        write_dataframes_to_excel(
            sheets,
            output_path=output_path,
            freeze_header=True,
            autofit_columns=True,
            header_bold=True,
            add_borders=True,
            add_autofilter=True,
            index=False,
        )
        written.append(output_path)

    ########################################
    #### Country profiles (ESCWA) Excel ####
    ########################################
    if args.write_profile:
        # Reference template (for Country Profile)
        diagnosis_assessment_template = pd.read_excel(args.template)

        # Static Tables
        summary_stats_all = profile_data_quality_summary(metadata_renamed, quality_cols)
        summary_stats_escwa = profile_data_quality_summary(metadata_automated_escwa.rename(columns=COL_RENAMES), quality_cols)
        summary_stats_kpi_profile = profile_quality_summary_table(metadata_renamed, quality_cols, groupby=['KPI ID', 'Series Name'], pct_only=True)

        index_title = index_name
        output_path = args.out_dirs['profile'] / f"Profile_ESCWA_{index_title}{OUTPUT_SUFFIX}.xlsx"
        title = 'General Overview: Overall Quality of Index'

        # constant across every sheet, in the order they should be stacked
        static_tables = {
            'All Countries': summary_stats_all,
            'ESCWA Countries': summary_stats_escwa,
            f'{index_title} - KPI Quality (All Countries)': summary_stats_kpi_profile,
        }

        # All ESCWA countries available in this index
        available_isos = set(metadata_automated['ISO'].unique())
        country_iso_list = [iso for iso in escwa_members if iso in available_isos]
        missing = [iso for iso in escwa_members if iso not in available_isos]
        print(f"{len(missing)} ISO values not available: {missing}")

        ensure_new(output_path)
        write_country_sheets_to_excel(
            metadata_renamed,
            kpi_year,
            diagnosis_assessment_template,
            country_iso_list,
            quality_cols,
            static_tables,
            output_path=output_path,
            index_title=index_title,
            title=title,
        )
        append_run_info(output_path, manifest)   # Snippet 3
        written.append(output_path)

    return written


def main(argv=None):
    utf8_console()
    parser = build_parser(__doc__)
    g = parser.add_argument_group('snippet 2 (UCE bounds)')
    g.add_argument('--legacy-a1', action='store_true',
                   help='Use the legacy inferred-cap A1 logic instead of the UCE bounds extract')
    g.add_argument('--uce-csv', type=Path, default=DEFAULT_UCE_BOUNDS_CSV,
                   help=f'UCE bounds extract CSV (default: {DEFAULT_UCE_BOUNDS_CSV.relative_to(DEFAULT_UCE_BOUNDS_CSV.parents[1])})')
    g.add_argument('--suffix', default='_snippet2',
                   help="Output file name suffix (default: _snippet2; pass '' for none)")
    args = resolve(parser.parse_args(argv))
    if not args.legacy_a1 and not args.uce_csv.is_file():
        sys.exit(f'UCE bounds CSV not found: {args.uce_csv}')
    # Snippet 3: Snippet 2 settings that change results are part of the fingerprint
    def stamp_inputs(args, index_name):
        return [] if args.legacy_a1 else [file_input('uce_bounds', args.uce_csv)]

    def stamp_options(args, index_name):
        return {'a1_logic': 'legacy' if args.legacy_a1 else 'uce',
                'uce_vintage': None if args.legacy_a1 else UCE_VINTAGES.get(index_name)}

    return run_batch(run_index, args, __file__, stamp_inputs, stamp_options)


if __name__ == '__main__':
    sys.exit(main())
