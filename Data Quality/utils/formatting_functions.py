import pandas as pd
import numpy as np

def format_simulator_data(simulator_data_raw, kpi_key,
                          pivot_names=('Country', 'ISO', 'Region', 'Sub-region', 'Income Type')):
    """Reshape raw simulator data from wide to long and attach KPI metadata."""
    df = simulator_data_raw.copy()
    df = df[1:].reset_index(drop=True)

    df = df.melt(id_vars=list(pivot_names),
                 var_name='KPI ID', value_name='data_report')
    df['KPI ID'] = df['KPI ID'].astype(str).str.strip()

    df = df.merge(kpi_key,on='KPI ID', how='left')
    df = df[['Country', 'ISO', 'Series Name', 'KPI ID', 'data_report']]
    df['data_report'] = pd.to_numeric(df['data_report'], errors='coerce')

    # Drop ISOs where every data_report value is NaN
    #iso_has_data = df.groupby('ISO')['data_report'].apply(lambda g: g.notna().any())
    #dropped_isos = iso_has_data[~iso_has_data].index.tolist()

    #if dropped_isos:
    #    print(f"Filtered out {len(dropped_isos)} ISO(s) with no data: {dropped_isos}")

    #df = df[df['ISO'].isin(iso_has_data[iso_has_data].index)]

    return df

def format_historical_kpi_data(historical_kpi_data_raw, iso_filter=None):
    """Reshape raw historical KPI data from wide to long and normalize dtypes."""
    rename_map = {
        'Unnamed: 0': 'KPI ID',
        'Unnamed: 1': 'Series Name',
        'Unnamed: 2': 'year_historical_automated',
        'year': 'year_historical_automated',
        'Series name': 'Series Name',
        'KeyID': 'KPI ID',
    }
    replacement_dict = {
        'Mean years of schooling': 'Mean Year of Schooling',
        'Expected years of schooling': 'Expected Year of Schooling',
    }

    df = historical_kpi_data_raw.copy()
    df = df.rename(columns=rename_map)
    df = df.iloc[1:]
    df['Series Name'] = df['Series Name'].replace(replacement_dict)

    df_long = df.melt(
        id_vars=['KPI ID', 'Series Name', 'year_historical_automated'],
        var_name='ISO', value_name='data_historical_automated'
    )

    if iso_filter is not None:
        df_long = df_long[df_long['ISO'].isin(iso_filter)]

    df_long['data_historical_automated'] = pd.to_numeric(
        df_long['data_historical_automated'], errors='coerce').astype('Float64')
    df_long['KPI ID'] = df_long['KPI ID'].astype(str).str.strip()
    df_long['year_historical_automated'] = pd.to_numeric(
        df_long['year_historical_automated'], errors='coerce').astype('Int64')

    return df_long.reset_index(drop=True)


# KPI Summary stats
def get_kpi_totals(df):
    """Constant-per-KPI fields + total/availability summary. Uses .agg."""
    out = df.groupby(['KPI ID', 'Series Name']).agg(
        n_unique_categorical_simulator=('n_unique_categorical_simulator', 'first'),
        unique_categorical_values_simulator=('unique_categorical_values_simulator', 'first'),
        possible_cap=('possible_cap', 'first'),
        cap_count=('cap_count', 'first'),
        max_kpi_value_hist=('max_kpi_value_hist', 'first'),
        possible_floor=('possible_floor', 'first'),
        floor_count=('floor_count', 'first'),
        n_datapoints=('KPI ID', 'size'),
        A_exact_sum=('A_exact', 'sum'),
        A_approx_sum=('A_approx', 'sum'),
        A1_cap_adj_sum=('A1_cap_adjusted_match', 'sum'),
        B_exact_sum=('B_exact', 'sum'),
        B_approx_sum=('B_approx', 'sum'),
        total_sum=('A_A1_B_match_total', 'sum'),
    )

    # roll-ups
    out['A_sum'] = out['A_exact_sum'] + out['A_approx_sum'] + out['A1_cap_adj_sum']
    out['B_sum'] = out['B_exact_sum'] + out['B_approx_sum']
    out['exact_sum'] = out['A_exact_sum'] + out['A1_cap_adj_sum'] + out['B_exact_sum'] # Cap adjusted sum considered exact
    out['approx_sum'] = out['A_approx_sum'] + out['B_approx_sum']

    # percentages (denominator = n_datapoints)
    out['pct_A'] = (out['A_sum'] / out['n_datapoints'] * 100).round(1)
    out['pct_A1_cap_adj'] = (out['A1_cap_adj_sum'] / out['n_datapoints'] * 100).round(1)
    out['pct_B'] = (out['B_sum'] / out['n_datapoints'] * 100).round(1)
    out['pct_exact'] = (out['exact_sum'] / out['n_datapoints'] * 100).round(1)
    out['pct_approx'] = (out['approx_sum'] / out['n_datapoints'] * 100).round(1)
    out['pct_matched'] = (out['total_sum'] / out['n_datapoints'] * 100).round(1)

    return out.reset_index()

def get_kpi_year_stats(df):
    """Year spread, mode, and distribution per KPI. Needs .apply."""
    def _stats(years):
        years = years.dropna()
        if years.empty:
            return pd.Series({
                'year_min': np.nan, 'year_max': np.nan, 'year_range': np.nan,
                'year_median': np.nan, 'most_common_year': np.nan,
                'most_common_year_pct': np.nan, 'n_distinct_years': 0,
                'year_distribution': {},
            })
        counts = years.value_counts()
        pct = (counts / len(years) * 100).round(1)
        return pd.Series({
            'year_min': years.min(),
            'year_max': years.max(),
            'year_range': years.max() - years.min(),
            'year_median': years.median(),
            'most_common_year': counts.index[0],
            'most_common_year_pct': pct.iloc[0],
            'n_distinct_years': counts.size,
            'year_distribution': pct.sort_index().to_dict(),
        })

    return df.groupby('KPI ID')['year_inferred'].apply(_stats).unstack().reset_index()
    
def get_kpi_year_stats(df):
    """Year spread, mode, and distribution per KPI. Needs .apply."""
    def _stats(years):
        years = years.dropna()
        if years.empty:
            return pd.Series({
                'year_min': np.nan, 'year_max': np.nan, 'year_range': np.nan,
                'year_median': np.nan, 'most_common_year': np.nan,
                'most_common_year_pct': np.nan, 'n_distinct_years': 0,
                'year_distribution': {},
                'year_distribution_formatted': '',
            })
        counts = years.value_counts()
        pct = (counts / len(years) * 100).round(1)

        # Sort by percentage descending (ties broken by year, ascending)
        pct_sorted = pct.sort_values(ascending=False)

        # Convert np.int64 keys -> plain int, and build an Excel-friendly string
        year_distribution_clean = {int(k): float(v) for k, v in pct_sorted.items()}
        year_distribution_formatted = ', '.join(
            f'{k}: {v}%' for k, v in year_distribution_clean.items()
        )

        return pd.Series({
            'year_min': years.min(),
            'year_max': years.max(),
            'year_range': years.max() - years.min(),
            'year_median': years.median(),
            'most_common_year': counts.index[0],
            'most_common_year_pct': pct.iloc[0],
            'n_distinct_years': counts.size,
            'year_distribution': year_distribution_clean,
            'year_distribution_formatted': year_distribution_formatted,
        })
    return df.groupby('KPI ID')['year_inferred'].apply(_stats).unstack().reset_index()
    


# Reference Tables
def latest_year_max(data_long, 
                    group_by='KPI ID', 
                    year_col='year_historical_automated', 
                    data='data_historical_automated'):
    # Step 1: sort by group, then by year descending (keeps all rows, no dedup)
    df_sorted = data_long.sort_values([group_by, year_col], ascending=[True, False])

    # Step 2: find the most recent year per group, filter to only those rows
    latest_year = df_sorted.groupby(group_by)[year_col].transform('max')
    df_latest = df_sorted[df_sorted[year_col] == latest_year]

    # Step 3: within the most-recent-year rows, get the max data value per group
    result = (
        df_latest.groupby(group_by, as_index=False)[data]
        .max()
        .rename(columns={data:'max_kpi_value_hist'})
    )
    return result

def latest_year_min_max(data_long,
                        group_by='KPI ID',
                        year_col='year_historical_automated',
                        data='data_historical_automated'):
    # Step 1: sort by group, then by year descending (keeps all rows, no dedup)
    df_sorted = data_long.sort_values([group_by, year_col], ascending=[True, False])

    # Step 2: find the most recent year per group, filter to only those rows
    latest_year = df_sorted.groupby(group_by)[year_col].transform('max')
    df_latest = df_sorted[df_sorted[year_col] == latest_year]

    # Step 3: within the most-recent-year rows, get min and max data value per group
    result = (
        df_latest.groupby(group_by, as_index=False)
        .agg(min_kpi_value_hist=(data, 'min'),
             max_kpi_value_hist=(data, 'max'))
    )
    return result

def find_value_type(group, data_col='data_report', suffix='',
                     max_categories=10, min_group_size=1):
    """
    Inspects the distinct values of `data_col` within a group (e.g. grouped
    by KPI ID) and flags whether they look boolean or categorical.
 
    Criteria:
      - Boolean: all non-null values are integer-valued AND the unique set
        is a subset of {0, 1} (i.e. it's exactly {0}, {1}, or {0, 1}).
      - Categorical: all non-null values are integer-valued, the unique
        set is NOT a subset of {0, 1} (so this excludes booleans, even
        2-value ones like {1, 2}), there are at least 2 unique values,
        and the number of unique values is small (<= max_categories).
        This distinguishes true categories (e.g. {1,2} or {0,1,2,3})
        from continuous-looking numeric data (e.g. ratios/percentages
        like 0.1111, 0.5556, ...).
      - Neither: values aren't all integers, there's only a single
        unique value that isn't 0/1, or there are too many unique
        integer values to reasonably be a category (likely a
        continuous/count variable).
 
    Returns a pd.Series with just two fields, so this can be used with
    groupby(...).apply(...):
      - n_unique: count of unique values, only populated if the group
        is boolean or categorical; NA otherwise.
      - unique_values: the set of unique integer values, only populated
        if the group is boolean or categorical; NA otherwise.
    """
    vals = group[data_col].dropna()
 
    # nothing to work with
    if len(vals) == 0 or len(group) < min_group_size:
        return pd.Series({
            f'n_unique_categorical{suffix}': pd.NA,
            f'unique_categorical_values{suffix}': pd.NA,
        })
 
    # check all values are integer-valued (e.g. 1.0, 0.0, 2.0 -- not 0.1111)
    all_integer = vals.apply(lambda v: float(v).is_integer()).all()
 
    unique_vals = sorted(vals.unique().tolist())
    n_unique = len(unique_vals)
 
    is_boolean = False
    is_categorical = False
 
    if all_integer:
        unique_int_vals = set(int(v) for v in unique_vals)
        if unique_int_vals.issubset({0, 1}):
            is_boolean = True
        elif 1 < n_unique <= max_categories:
            is_categorical = True
 
    is_flagged = is_boolean or is_categorical
 
    return pd.Series({
        f'n_unique_categorical{suffix}': n_unique if is_flagged else pd.NA,
        f'unique_categorical_values{suffix}': (unique_int_vals if is_flagged else pd.NA),
    })
 
# Summary KPI
def find_floor_cap(group, data_col='data_report'):
    counts = group[data_col].value_counts()
    
    min_val = group[data_col].min()
    max_val = group[data_col].max()
    
    min_count = counts.get(min_val, 0)
    max_count = counts.get(max_val, 0)
    # Floor: min value, repeated >4 times, integer
    is_floor = (
        pd.notna(min_val) and
        min_count > 1 and
        float(min_val).is_integer())
    # Cap: max value, repeated >4 times, integer
    is_cap = (
        pd.notna(max_val) and
        max_count > 1 and
        float(max_val).is_integer())
    return pd.Series({
        'possible_cap': max_val if is_cap else np.nan,
        'cap_count': max_count if is_cap else np.nan,
        'possible_floor': min_val if is_floor else np.nan,
        'floor_count': min_count if is_floor else np.nan,
    })



def get_simulator_data_cap(simulator_data, historical_kpi_data_long):
    """
    Identify possible caps and floors in simulator data per KPI, validated
    against historical min/max values and categorical status.

    Relies on helper functions defined elsewhere:
    find_value_type, latest_year_min_max, find_floor_cap.

    Parameters
    ----------
    simulator_data : pd.DataFrame
        Simulator data with 'KPI ID' and 'data_report' columns.
    historical_kpi_data_long : pd.DataFrame
        Historical KPI data in long format with 'KPI ID',
        'year_historical_automated' and 'data_historical_automated' columns.

    Returns
    -------
    pd.DataFrame
        One row per KPI with cap/floor info and a 'cap_present' flag.
    """
    # Categorical value detection per KPI
    simulator_categorical = (
        simulator_data.groupby(['KPI ID'])
        .apply(find_value_type, data_col='data_report', suffix='_simulator')
        .reset_index()
    )

    # Min/max of the most recent historical value per KPI
    kpi_min_max_historical_value = latest_year_min_max(
        historical_kpi_data_long,
        group_by='KPI ID',
        year_col='year_historical_automated',
        data='data_historical_automated',
    )

    simulator_data_cap = (
        simulator_data.copy()
        .groupby('KPI ID')
        .apply(find_floor_cap)
        .reset_index()
    )

    # Merge in most recent historical data for each KPI
    simulator_data_cap = simulator_data_cap.merge(
        kpi_min_max_historical_value, how='left', on='KPI ID'
    )
    numeric_cols = [
        'possible_cap', 'max_kpi_value_hist',
        'possible_floor', 'min_kpi_value_hist',
    ]
    for col in numeric_cols:
        simulator_data_cap[col] = pd.to_numeric(
            simulator_data_cap[col], errors='coerce'
        )

    simulator_data_cap = simulator_data_cap.merge(
        simulator_categorical, how='left', on='KPI ID'
    )
    simulator_data_cap = simulator_data_cap[[
        'KPI ID', 'n_unique_categorical_simulator',
        'unique_categorical_values_simulator',
        'possible_cap', 'cap_count',
        'min_kpi_value_hist', 'max_kpi_value_hist',
        'possible_floor', 'floor_count',
    ]].copy()

    # Invalidate caps: cap vs. historical max check, missing history, or categorical KPI
    mask_cap = (
        (simulator_data_cap['possible_cap'] >= simulator_data_cap['max_kpi_value_hist'])
        | simulator_data_cap['max_kpi_value_hist'].isna()
        | simulator_data_cap['n_unique_categorical_simulator'].notna()
    )
    simulator_data_cap.loc[mask_cap, ['possible_cap', 'cap_count']] = np.nan

    # Invalidate floors: categorical KPI, floor vs. historical min check,
    # 0-1 or 0-100 historical ranges, or missing history
    min_hist = simulator_data_cap['min_kpi_value_hist']
    max_hist = simulator_data_cap['max_kpi_value_hist']
    mask_floor = (
        simulator_data_cap['n_unique_categorical_simulator'].notna()
        | (simulator_data_cap['possible_floor'] <= min_hist)
        | ((min_hist == 0) & (max_hist == 1))
        | ((min_hist == 0) & (max_hist == 100))
        | min_hist.isna()
    )
    simulator_data_cap.loc[mask_floor, ['possible_floor', 'floor_count']] = np.nan

    simulator_data_cap['cap_present'] = np.where(
        simulator_data_cap['possible_cap'].notna(), 1, 0
    )

    return simulator_data_cap


def get_kpi_country_summary(historical_kpi_data_long):
    """
    Summarize data coverage per KPI and country.

    Parameters
    ----------
    historical_kpi_data_long : pd.DataFrame
        Historical KPI data in long format with 'KPI ID', 'ISO',
        'year_historical_automated' and 'data_historical_automated' columns.

    Returns
    -------
    pd.DataFrame
        One row per KPI ID / ISO pair with total_rows, nonnull_rows,
        nonnull_pct and latest_year_nonnull.
    """
    kpi_country_summary_df = (
        historical_kpi_data_long.groupby(['KPI ID', 'ISO'])
        .agg(
            total_rows=('data_historical_automated', 'size'),
            nonnull_rows=('data_historical_automated', 'count'),
        )
        .reset_index()
    )
    kpi_country_summary_df['nonnull_pct'] = (
        kpi_country_summary_df['nonnull_rows']
        / kpi_country_summary_df['total_rows']
        * 100
    ).round(2)

    # Most recent year with a non-null value per KPI / country
    latest_nonnull = (
        historical_kpi_data_long[
            historical_kpi_data_long['data_historical_automated'].notna()
        ]
        .groupby(['KPI ID', 'ISO'])['year_historical_automated']
        .max()
        .rename('latest_year_nonnull')
    )
    kpi_country_summary_df = kpi_country_summary_df.merge(
        latest_nonnull, how='left', on=['KPI ID', 'ISO']
    )
    kpi_country_summary_df['latest_year_nonnull'] = (
        kpi_country_summary_df['latest_year_nonnull'].astype('Int64')
    )

    return kpi_country_summary_df

def get_match_data(simulator_data, historical_kpi_data_long, kpi_country_summary_df):
    """
    Match simulator data to historical data per KPI and country, and compute
    match / difference fields.

    Parameters
    ----------
    simulator_data : pd.DataFrame
        Simulator data with 'Country', 'ISO', 'Series Name', 'KPI ID'
        and 'data_report' columns.
    historical_kpi_data_long : pd.DataFrame
        Historical KPI data in long format with 'ISO', 'KPI ID',
        'Series Name', 'year_historical_automated' and
        'data_historical_automated' columns.
    kpi_country_summary_df : pd.DataFrame
        Output of get_kpi_country_summary.

    Returns
    -------
    pd.DataFrame
        One row per simulator row and historical year, with exact_match,
        latest_year, value_difference and value_difference_percentage.
    """
    # Attach historical data
    match_data = simulator_data.merge(
        historical_kpi_data_long.drop(columns='Series Name'),
        how='left',
        on=['ISO', 'KPI ID'],
    )
    # Include summary data, for reasoning down the line
    match_data = match_data.merge(
        kpi_country_summary_df, how='left', on=['KPI ID', 'ISO']
    )
    match_data = match_data[[
        'Country', 'ISO', 'Series Name', 'KPI ID', 'data_report',
        'year_historical_automated', 'data_historical_automated',
        'total_rows', 'nonnull_rows', 'nonnull_pct', 'latest_year_nonnull',
    ]].copy()

    # Calculated fields
    match_data['exact_match'] = (
        match_data['data_report'] == match_data['data_historical_automated']
    )
    match_data['latest_year'] = (
        match_data['year_historical_automated'] == match_data['latest_year_nonnull']
    )

    # Value difference & pct
    match_data['value_difference'] = abs(
        match_data['data_report'] - match_data['data_historical_automated']
    )
    denom = match_data['data_report'].replace(0, np.nan)
    condition = (match_data['value_difference'] == 0).fillna(False)
    match_data['value_difference_percentage'] = np.where(
        condition,
        0,
        match_data['value_difference'] / denom,
    )

    return match_data



def get_summary_stats(metadata_automated, quality_cols, simulator_data,
                     only_escwa_countries=False, escwa_members=None):
    """
    Summarize data quality categories overall, by KPI and by country.

    Parameters
    ----------
    metadata_automated : pd.DataFrame
        Metadata with 'KPI ID', 'Country' and the quality_cols flag columns.
    quality_cols : list of str
        Quality category flag columns to summarize.
    simulator_data : pd.DataFrame
        Simulator data with an 'ISO' column, used for the record-count check.
    only_escwa_countries : bool, default False
        If True, restrict simulator_data to escwa_members for the count check.
    escwa_members : list-like, optional
        ISO codes of ESCWA members. Required if only_escwa_countries is True.

    Returns
    -------
    tuple of pd.DataFrame
        (summary_stats, summary_stats_kpi, summary_stats_country)
    """
    # --- overall ------------------------------------------------------------
    totals = metadata_automated[quality_cols].sum()
    total_records = totals.sum()

    if only_escwa_countries:
        simulator_data_escwa = simulator_data[
            simulator_data['ISO'].isin(escwa_members)
        ].copy()
    else:
        simulator_data_escwa = simulator_data.copy()

    if metadata_automated.shape[0] == total_records:
        print(f"✅ All {metadata_automated.shape[0]} records accounted for.")
        print(f"Simulator Data (ESCWA members) count {simulator_data_escwa.shape[0]}")
    else:
        print(f"⚠️ Record count mismatch {total_records} of {metadata_automated.shape[0]}")

    summary_stats = pd.DataFrame({
        'Category': quality_cols,
        'Count': totals.values,
    })
    summary_stats['Percentage'] = (
        summary_stats['Count'] / total_records * 100
    ).round(2)
    summary_stats.loc[len(summary_stats)] = ['Total', total_records, 100.0]

    # --- by KPI -------------------------------------------------------------
    summary_stats_kpi = (
        metadata_automated.groupby('KPI ID')[quality_cols].sum().reset_index()
    )
    summary_stats_kpi['Total'] = summary_stats_kpi[quality_cols].sum(axis=1)
    for col in quality_cols:
        summary_stats_kpi[col + '_pct'] = (
            summary_stats_kpi[col] / summary_stats_kpi['Total']
        ).round(2)

    # --- by country ---------------------------------------------------------
    summary_stats_country = (
        metadata_automated.groupby('Country')[quality_cols].sum().reset_index()
    )
    summary_stats_country['Total'] = summary_stats_country[quality_cols].sum(axis=1)
    for col in quality_cols:
        summary_stats_country[col + '_pct'] = (
            summary_stats_country[col] / summary_stats_country['Total']
        ).round(2)

    return summary_stats, summary_stats_kpi, summary_stats_country


####################################################
######### Country Profile Functions ################
####################################################

def profile_data_quality_summary(metadata_automated, quality_cols):
    """
    Summarize data quality flags across the whole dataset.

    Parameters
    ----------
    metadata_automation : pd.DataFrame
        The dataframe containing the quality flag columns.
    quality_cols : list[str]
        Column names representing the quality categories (values summed per row).

    Returns
    -------
    pd.DataFrame with a row per category (Count, Percentage) plus a Total row.
    """
    totals = metadata_automated[quality_cols].sum()
    total_records = totals.sum()

    if metadata_automated.shape[0] == total_records:
        print(f"All {metadata_automated.shape[0]} records accounted for.")
    else:
        print(f"Record count mismatch {total_records} of {metadata_automated.shape[0]}")

    summary_stats = pd.DataFrame({
        'Category': quality_cols,
        'Count': totals.values,
    })
    summary_stats['Percentage'] = (summary_stats['Count'] / total_records * 100).round(2)
    summary_stats.loc[len(summary_stats)] = ['Total', total_records, 100.0]

    return summary_stats

def profile_quality_summary_table(metadata_automated, quality_cols, groupby=None, pct_only=False):
    """
    Build a data quality summary table, either overall or grouped.

    Parameters
    ----------
    metadata_automation : pd.DataFrame
        The dataframe containing the quality flag columns.
    quality_cols : list[str]
        Column names representing the quality categories (summed per row/group).
    groupby : str or list[str], optional
        Column(s) to group by. If None, returns the overall summary
        (with a 'Total' row and 0-100 scale percentages).
        If provided, returns a per-group breakdown (with 0-1 scale '_pct' columns).
    pct_only : bool, default False
        Only applies when `groupby` is provided. If True, restricts the
        output to the groupby column(s) plus the '_pct' columns only
        (drops raw Count and Total columns).

    Returns
    -------
    pd.DataFrame
    """
    if groupby is None:
        # --- overall ----------------------------------------------------
        totals = metadata_automated[quality_cols].sum()
        total_records = totals.sum()

        if metadata_automated.shape[0] == total_records:
            print(f"All {metadata_automated.shape[0]} records accounted for.")
        else:
            print(f"Record count mismatch {total_records} of {metadata_automation.shape[0]}")

        summary_stats = pd.DataFrame({
            'Category': quality_cols,
            'Count': totals.values,
        })
        summary_stats['Percentage'] = (summary_stats['Count'] / total_records * 100).round(2)
        summary_stats.loc[len(summary_stats)] = ['Total', total_records, 100.0]

        return summary_stats

    else:
        # --- grouped ------------------------------------------------------
        summary_stats_group = metadata_automated.groupby(groupby)[quality_cols].sum().reset_index()
        summary_stats_group['Total'] = summary_stats_group[quality_cols].sum(axis=1)
        for col in quality_cols:
            summary_stats_group[col + ' (%)'] = (summary_stats_group[col] / summary_stats_group['Total']).round(2)

        if pct_only:
            groupby_cols = [groupby] if isinstance(groupby, str) else list(groupby)
            pct_cols = [col + ' (%)' for col in quality_cols]
            return summary_stats_group[groupby_cols + pct_cols]

        return summary_stats_group


def profile_country_kpi_summary(country_kpi, diagnosis_assessment_template, id_col=['KPI ID', 'Series Name']):
    """
    Summarize data quality flags for a single country's KPI table.

    Mirrors data_quality_summary, but reads its categories off the already-renamed
    bucket columns of a profile_country_kpi_tbl output rather than a passed-in list.

    Joins diagnosis_assessment_template on Category to attach guidance columns,
    but only for categories with zero flagged records -- if a category has any
    flagged records (Count > 0), its joined-in columns are blanked out since the
    diagnosis text doesn't apply once issues are already present.

    Parameters
    ----------
    country_kpi : pd.DataFrame
        Output of profile_country_kpi_tbl -- ID column(s) plus one column per bucket.
    diagnosis_assessment_template : pd.DataFrame
        Must contain a 'Category' column plus one or more guidance columns.
    id_col : str or list of str
        Identifier column(s) to exclude from the totals.

    Returns
    -------
    pd.DataFrame with a row per category (Category, Count, Percentage, + template
    columns) plus a Total row.
    """
    country_kpi = country_kpi.drop(columns=['Year of Matched Data', 'Year Range'])
    
    id_cols = [id_col] if isinstance(id_col, str) else list(id_col)
    bucket_cols = [c for c in country_kpi.columns if c not in id_cols]

    totals = country_kpi[bucket_cols].sum()
    total_records = totals.sum()

    if total_records == 0:
        print("No flagged records for this country.")
    elif country_kpi.shape[0] == total_records:
        print(f"All {country_kpi.shape[0]} records accounted for.")
    else:
        print(f"Record count mismatch {total_records} of {country_kpi.shape[0]}")

    summary_stats = pd.DataFrame({
        'Category': bucket_cols,
        'Count': totals.values,
    })
    summary_stats['Percentage'] = (
        (summary_stats['Count'] / total_records * 100).round(2) if total_records else 0.0
    )
    summary_stats['Count'] = summary_stats['Count'].astype(int)

    # Join template guidance on Category
    summary_stats = summary_stats.merge(diagnosis_assessment_template, on='Category', how='left')

    # Blank out the joined-in template columns wherever Count > 0
    template_cols = [c for c in diagnosis_assessment_template.columns if c != 'Category']
    summary_stats.loc[summary_stats['Count'] == 0, template_cols] = np.nan

    summary_stats.loc[len(summary_stats)] = ['Total', total_records, 100.0] + [np.nan] * len(template_cols)
    return summary_stats

def profile_country_kpi_tbl(metadata, country_iso, quality_cols, kpi_year):

    country_kpi = metadata[metadata['ISO'] == country_iso].copy().reset_index(drop=True)

    country_kpi = country_kpi.merge(kpi_year, how='left', on='KPI ID')
    country_kpi['Year Range'] = np.where(
        country_kpi['Bucket B: Data old but accurate'] == 1,
        country_kpi['year_distribution_formatted'],
        np.nan)
    
    country_kpi['Year of Matched Data'] = np.where(
        country_kpi['Bucket B: Data old but accurate'] == 1,
        country_kpi['year_inferred'],
        np.nan)
    
    country_kpi[quality_cols] = country_kpi[quality_cols].astype(int)
    suppl_cols = ['Year of Matched Data', 'Year Range']          # Additional cols
    after_col = 'Bucket B: Data old but accurate'  # column where suppl_cols will be placed after
    country_kpi = country_kpi[['KPI ID', 'Series Name'] + quality_cols + suppl_cols]
    cols = country_kpi.columns.tolist()

    cols = [c for c in cols if c not in suppl_cols]
    insert_at = cols.index(after_col) + 1
    cols[insert_at:insert_at] = suppl_cols
    country_kpi = country_kpi[cols]


    
    return country_kpi

####################################################