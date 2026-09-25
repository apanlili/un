import pandas as pd

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