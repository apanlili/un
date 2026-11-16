"""Compare the Data Quality Profile run (Alfonso's code, unchanged) with the precheck run on the same files.
usage: python compare_runs.py jobs.csv alfonso_out precheck_out layout_changes.csv out.xlsx [alfonso_out_on_cleaned]"""
import sys, json
from pathlib import Path
import pandas as pd

JOBS, AO, PO, LAY, OUT = sys.argv[1:6]
AC = sys.argv[6] if len(sys.argv) > 6 else None
jobs = pd.read_csv(JOBS, dtype=str); lay = pd.read_csv(LAY, dtype=str)
log = json.load(open(Path(AO) / 'run_log.json'))
pk = pd.read_excel(Path(PO) / 'precheck_all_indices.xlsx', 'KPIs', dtype={'KPI': str, 'index ID': str})
pi = pd.read_excel(Path(PO) / 'precheck_all_indices.xlsx', 'To fix or review', dtype={'KPI': str, 'index ID': str})
ps = pd.read_excel(Path(PO) / 'precheck_all_indices.xlsx', 'Summary', dtype={'index ID': str})
B = ['A_total', 'A1_cap_adjusted_match', 'B_total', 'C_data_available_no_match', 'D_possible_impute', 'E_no_historical_data', 'F_no_report_data']
LAB = {'A_total': 'A timely', 'A1_cap_adjusted_match': 'A1 capped', 'B_total': 'B old', 'C_data_available_no_match': 'C no match',
       'D_possible_impute': 'D imputed?', 'E_no_historical_data': 'E no history', 'F_no_report_data': 'F no index value'}
rows, krows = [], []
for j in jobs.itertuples():
    key = f'index_{j.index_ID}_{j.edition}'
    ed = int(j.edition)
    f = Path(AO) / f'{key}_metadata_full.pkl'
    if not f.exists():
        continue
    m = pd.read_pickle(f)
    n = len(m)
    r = {'index': j.index, 'index ID': j.index_ID, 'edition': ed, 'country x KPI rows': n}
    for b in B:
        r[LAB[b] + ' %'] = round(100 * m[b].fillna(0).astype(float).sum() / n, 1)
    if AC and (Path(AC) / f'{key}_metadata_full.pkl').exists():
        c = pd.read_pickle(Path(AC) / f'{key}_metadata_full.pkl'); nc = len(c)
        r['matched A+B % (files as on Drive)'] = round(r['A timely %'] + r['B old %'], 1)
        r['matched A+B % (after precheck cleaning)'] = round(100 * (c.A_total.fillna(0).astype(float).sum() + c.B_total.fillna(0).astype(float).sum()) / nc, 1)
        r['E no history % (after cleaning)'] = round(100 * c.E_no_historical_data.fillna(0).astype(float).sum() / nc, 1)
    s = ps[(ps['index ID'] == j.index_ID) & (ps.edition == ed)]
    r['precheck status'] = s.status.iloc[0] if len(s) else ''
    r['precheck items to review'] = int(s['to review'].iloc[0]) if len(s) else None
    q = pi[(pi['index ID'] == j.index_ID) & (pi.edition == ed)]
    top = q.groupby('check').size().sort_values(ascending=False)
    r['main precheck items'] = '; '.join(f'{c} ({v})' for c, v in top.head(4).items())
    l = lay[(lay['index'] == j.index) & (lay.edition == j.edition)]
    r['layout changes needed for the profile code'] = l['layout changes made for the run'].iloc[0] if len(l) else ''
    rows.append(r)
    # per KPI
    m['KPI ID'] = m['KPI ID'].astype(str).str.strip().str.lower()
    g = m.groupby('KPI ID')
    kk = pd.DataFrame({'rows': g.size()})
    for b in ['A_total', 'B_total', 'C_data_available_no_match', 'E_no_historical_data']:
        kk[LAB[b] + ' %'] = (100 * g[b].apply(lambda x: x.fillna(0).astype(float).sum()) / kk.rows).round(0)
    kk = kk.reset_index().rename(columns={'KPI ID': 'KPI'})
    kk['KPI'] = kk.KPI.astype(str).str.lower()
    p = pk[(pk['index ID'] == j.index_ID) & (pk.edition == ed)][['KPI', 'share_matched', 'scale_factor', 'diagnosis']].copy()
    p['KPI'] = p.KPI.astype(str).str.lower(); p = p.drop_duplicates('KPI')
    kk = kk.merge(p, on='KPI', how='left')
    flags = q[q.KPI.notna() & (q.KPI.astype(str) != '')].groupby(q.KPI.astype(str).str.lower()).check.apply(
        lambda x: '; '.join(f'{c} ({v})' for c, v in x.value_counts().items()))
    kk['precheck items'] = kk.KPI.map(flags).fillna('')
    kk['precheck: found in source %'] = (100 * kk.share_matched).round(0)
    nr = kk['precheck items'].str.contains('KPI not reconciled')
    kk['profile matched % (A+B)'] = kk['A timely %'] + kk['B old %']
    pm = kk['profile matched % (A+B)']
    kk['reading'] = ''
    kk.loc[nr & (pm < 50), 'reading'] = 'both: index values not found in the source for most countries (the precheck diagnosis says why)'
    kk.loc[nr & (pm >= 50), 'reading'] = 'profile matches most countries, precheck does not: the profile accepts approximate matches; check them'
    kk.loc[~nr & (kk['precheck: found in source %'] >= 50) & (pm < 50), 'reading'] = 'precheck matches most countries, profile does not: see the precheck items (scale factor, KeyID case...)'
    kk.insert(0, 'index', j.index); kk.insert(1, 'edition', ed)
    krows.append(kk.drop(columns=['share_matched']))
S = pd.DataFrame(rows); K = pd.concat(krows, ignore_index=True)
not_run = pd.DataFrame([
    {'index': 'Open Data Inventory (ODIN)', 'edition': 2022, 'why': 'The historical file on Drive (index_16.xlsx, backoffice download) lists the 22 KeyIDs but holds no values or years. The simulator values exist in the publisher dataset (ODIN2022 v29062023.xlsx) and can be converted once the historical file exists.'},
    {'index': 'Public Administration Index', 'edition': 2024, 'why': 'No simulator file of any kind on Drive (no raw_ file, no calculation workbook, no UCE metadata).'}])
expl = pd.DataFrame({'sheet': ['By index', 'By KPI', 'Not run', 'Layout changes'], 'content': [
    'For each index: the profile buckets from the profile code (unchanged) on the files as on Drive (layout unified only), the share matched again after the precheck cleaning (codes, KPI IDs, scale factors), and the precheck items.',
    'For each KPI: share of countries per bucket in the profile, share found in the source by the precheck, precheck items, and a reading of the two.',
    'Active indices that could not be run, and why.',
    'Changes to the historical files needed before the profile code could read them (layout only; values unchanged).']})
with pd.ExcelWriter(OUT, engine='openpyxl') as w:
    expl.to_excel(w, sheet_name='Read me', index=False)
    S.to_excel(w, sheet_name='By index', index=False)
    K.to_excel(w, sheet_name='By KPI', index=False)
    not_run.to_excel(w, sheet_name='Not run', index=False)
    lay.to_excel(w, sheet_name='Layout changes', index=False)
print(S[['index', 'edition', 'A timely %', 'B old %', 'C no match %', 'E no history %', 'precheck items to review']].to_string())
print(K.reading.value_counts().to_string())
