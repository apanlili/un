"""
Index -> data file mapping used by metadata_automation.py and metadata_snippet2.py.

Same shape as `data_files_dict` in the Metadata Automation notebooks:
    index_name : [historical file, metadata file (unused), simulator file]

The scripts look for the historical file in the --hist folder and the
simulator file in the --sim folder. Add new indices here.
"""

DATA_FILES = {
    'index_9'      : ['index_9 EGDI.xlsx', '20251102_metadata_E-Government Development Index_2024.xlsx', 'raw_EGDI_2024.xlsx'],
    'index_1032'   : ['20260710_historical data_index_1032_SDG 2026.xlsx', '20260710_metadata_Sustainable_Development_Index_2026.xlsx', 'raw_SDG_2026.xlsx'],

    # Somalia indices
    'index_12'     : ['index_12 E-participation Index.xlsx', '', 'raw_EPI_2024.xlsx'],
    'index_1049'   : ['index_1049.xlsx', '', 'raw_IIAG_2024.xlsx'],
    'index_1037'   : ['index_1037.xlsx', '', 'raw_GOVTECH_2022.xlsx'],
    'index_1022'   : ['index_1022 Women Peace and security Index.xlsx', '', 'raw_WPS_2025.xlsx'],

    # Somalia second batch
    'index_1050'   : ['index_1050 Global Hunger.xlsx', '', 'raw_GHI.xlsx'],
    'index_5'      : ['index_5 ICT Developement Index.xlsx', '', 'raw_ITU_2024.xlsx'],
    'index_1036'   : ['20262205_historical data_index_1036_WPF_2026.xlsx', '', 'raw_WPF_2026.xlsx'],

    # Third
    'index_1027'   : ['index_1027 Human Development Index.xlsx', '', 'raw_HDI.xlsx'],
    'index_1030'   : ['index_1030 Gender Development Index.xlsx', '', 'raw_GDI_2024.xlsx'],
    'index_1031'   : ['index_1031 Planetary adjusted HDI.xlsx', '', 'raw_PPHDI.xlsx'],
    'index_1035'   : ['20260303_Historical data _WBL2.0_2026.xlsx', '', 'raw_WBL2.0_2026.xlsx'],
    'index_1026'   : ['index_1026 Open data Policies.xlsx', '', 'raw_ODP_2022.xlsx'],
    'index_1053'   : ['20260721_historical data_index_1053_BTI2026.xlsx', '', 'raw_BTI_2026.xlsx'],
    'index_1021'   : ['index_1021.xlsx', '', 'raw_WBL 1.0.xlsx'],
    'index_1052'   : ['20260717_historical data_index_1052_WPJ2026.xlsx', '', 'raw_WJP_2025.xlsx'],
    'index_1034'   : ['index_1034.xlsx', '', 'raw_EnviPI_2026.xlsx'],

    # Check below on Outlier detection
    'index_1024'   : ['index_1024_FII.xlsx', '', 'raw_FII_2025 1.xlsx'],   # No Somalia
    'index_1051'   : ['20263007_historical data_LNOB_index_1051_2026 1.xlsx', '', 'raw_LNOB_2026 1.xlsx'],
    'index_3'      : ['index_3.xlsx', '', 'raw_GCYB_2024.xlsx'],
    'index_10'     : ['index_10 DARE.xlsx', '', 'raw_DARE 1.xlsx'],
    'index_7_2025' : ['index_7 GII.xlsx', '', 'raw_GII_2025.xlsx'],        # No Somalia
    'index_7_2026' : ['20261019_historical_data_index_7_GII_2026 v2.xlsx', '', 'raw_GII_2026 4.xlsx'],   # No Somalia
}

# Snippet 2: index_name -> UCE vintage in the bounds extract.
# None = vintage not confirmed / not in the extract (no UCE bounds -> no A1 for that index).
UCE_VINTAGES = {
    'index_9'      : 'EGDI_2024',
    'index_1032'   : 'SDI_2026',
    'index_1030'   : 'GDI_2024',
    'index_1022'   : 'WPS_2025',
    'index_1034'   : 'EPI_2026',
    'index_1024'   : 'FII_2025',
    'index_1051'   : 'LNOB_2026',
    'index_1053'   : 'BTI_2026',
    'index_7_2025' : 'GII_2025',
    'index_7_2026' : 'GII_2026',
    'index_1027'   : None,   # HDI - confirm vintage (extract has HDI_2022/2024/2025)
    'index_1031'   : None,   # PHDI - confirm vintage (extract has PHDI_2022/2024/2025)
    'index_1050'   : None,   # GHI - confirm vintage (extract has GHI_2024/2025)
}

ESCWA_MEMBERS = ['DZA', 'BHR', 'COM', 'DJI', 'EGY', 'IRQ', 'JOR', 'KWT', 'LBN', 'LBY', 'MRT',
                 'MAR', 'OMN', 'PSE', 'QAT', 'SAU', 'SOM', 'SDN', 'SYR', 'TUN', 'ARE', 'YEM']


# Snippet 3: edition stamped on every output.
# Default = simulator file name without 'raw_' and without a trailing copy number
# ('raw_GII_2026 4.xlsx' -> 'GII_2026'). Override here when the file name is wrong or has no year.
# Kept separate from UCE_VINTAGES on purpose: names clash across families
# (index_12 'EPI_2024' is E-participation, while UCE 'EPI_2024' is the Environmental Performance Index).
EDITION_OVERRIDES = {
}


def edition(index_name: str) -> str:
    import re
    if index_name in EDITION_OVERRIDES:
        return EDITION_OVERRIDES[index_name]
    stem = DATA_FILES[index_name][2].rsplit('.', 1)[0]
    stem = re.sub(r'^raw_', '', stem)
    stem = re.sub(r'\s+\d+$', '', stem)          # ' 1', ' 4' copy numbers
    return stem.replace(' ', '')


def edition_has_year(index_name: str) -> bool:
    import re
    return bool(re.search(r'(19|20)\d\d', edition(index_name)))
