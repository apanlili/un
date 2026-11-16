"""Training files with planted mistakes, built from a clean index (SDG Index 2026: no item to fix or review).
Writes a simulator file and a historical file with 12 planted mistakes, the untouched files as 'last edition'
reference, an answer key, and checks that dqp_precheck finds every planted mistake.
usage: python build_training.py raw.xlsx historical.xlsx uce_metadata.xlsx out_dir"""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from openpyxl import load_workbook
from dqp_precheck import run
from dqp_precheck.readers import read_simulator, read_historical, read_uce_metadata

RAW, HIST, META, OUT = map(Path, sys.argv[1:5])
OUT.mkdir(parents=True, exist_ok=True)
sim_out = OUT / 'raw_SDG_2026_TRAINING.xlsx'
hist_out = OUT / 'historical_data_index_1032_SDG_2026_TRAINING.xlsx'
shutil.copy(RAW, sim_out); shutil.copy(HIST, hist_out)
shutil.copy(HIST, OUT / 'historical_data_index_1032_SDG_2026_PREVIOUS_FILE.xlsx')
shutil.copy(META, OUT / 'metadata_SDI_2026.xlsx')

ws_wb = load_workbook(sim_out); ws = ws_wb.worksheets[0]
hs_wb = load_workbook(hist_out); hs = hs_wb.worksheets[0]
head = [c.value for c in ws[1]]
col = {str(v): i + 1 for i, v in enumerate(head) if v is not None}          # KPI ID or label -> column number
row_of = {ws.cell(r, col['ISO']).value: r for r in range(3, ws.max_row + 1)}  # ISO -> row number
hhead = [c.value for c in hs[2]]
hcol = {hs.cell(1, j).value: j for j in range(4, hs.max_column + 1)}          # ISO -> column number (historical)
key = []


def plant(no, what, where, check, how, kpi='', iso=''):
    key.append({'no': no, 'mistake': what, 'where': where, 'expected check': check, 'how to spot it by eye': how,
                'kpi': kpi, 'iso': iso})


# 1 value copied from another country's row
src = ws.cell(row_of['TUN'], col['3617']).value
ws.cell(row_of['JOR'], col['3617']).value = src
plant(1, "Jordan's value replaced by Tunisia's", 'simulator, KPI 3617, row JOR', 'value matches another country',
      "Jordan's index value is not in Jordan's source series, but is Tunisia's latest source value.", '3617', 'JOR')
# 2 rows shifted for one KPI (10 consecutive countries)
k = '1408'; rs = list(range(20, 31))
vals = [ws.cell(r, col[k]).value for r in rs]
for r, v in zip(rs[1:], vals[:-1]):
    ws.cell(r, col[k]).value = v
plant(2, 'Ten rows shifted down by one', f'simulator, KPI {k}, rows {rs[1]}-{rs[-1]}', 'rows shifted',
      'Each of these countries shows the value of the country above it.', k)
# 3 one country in percentage while others are in shares... here: one value x100
k = '1366'
c = ws.cell(row_of['EGY'], col[k]); c.value = round(float(c.value) * 100, 6)
plant(3, "Egypt's value multiplied by 100", f'simulator, KPI {k}, row EGY', 'unit differs for one country',
      "Egypt's value is 100 times its source value; all other countries match without factor.", k, 'EGY')
# 4 whole KPI x100
k = '1367'
for r in range(3, ws.max_row + 1):
    c = ws.cell(r, col[k])
    if isinstance(c.value, (int, float)):
        c.value = round(float(c.value) * 100, 6)
plant(4, 'A whole KPI multiplied by 100', f'simulator, KPI {k}', 'scale factor between files',
      'Every value is 100 times the source.', k)
# 5 text in a value cell
ws.cell(row_of['FRA'], col['1374']).value = '..'
plant(5, 'Text ".." in a value cell', 'simulator, KPI 1374, row FRA', 'value not numeric', 'The cell holds ".." instead of a number.')
# 6 old code and name in the code column
ws.cell(row_of['ROU'], col['ISO']).value = 'ROM'
ws.cell(row_of['LAO'], col['ISO']).value = 'Lao PDR'
plant(6, 'Old ISO code (ROM) and a name in the code column (Lao PDR)', 'simulator, ISO column, rows Romania and Lao PDR',
      'country code converted (Automatic changes: alias / name in the code column)', 'ROM was replaced by ROU in 2002; a code cell holds a name.')
# 7 two entities under one code
ws.cell(row_of['MLT'], col['ISO']).value = 'CYP'
plant(7, "Malta coded CYP (Cyprus's code)", 'simulator, ISO column, row Malta', 'one code for two entities',
      'Two different country names carry the same code.')
# 8 country missing from the simulator
r = row_of['LBN']
for j in range(1, ws.max_column + 1):
    ws.cell(r, j).value = None
plant(8, 'Lebanon row deleted', 'simulator, row Lebanon emptied',
      'country ranked by the publisher, missing from the simulator; country in historical file, not in the index (information)',
      'Lebanon is in the publisher list of the metadata but has no values.')
ws_wb.save(sim_out)

# historical file
rows_by_key = {}
for r in range(3, hs.max_row + 1):
    rows_by_key.setdefault(str(hs.cell(r, 1).value), []).append(r)
# 9 two KPIs swapped
a, b = '1375', '1376'
for r in rows_by_key[a]:
    hs.cell(r, 1).value = int(b)
for r in rows_by_key[b]:
    hs.cell(r, 1).value = int(a)
plant(9, 'Two KPI IDs swapped in the historical file', f'historical, KeyID {a} and {b}', 'KPI values match another KPI (both ways); KPI not reconciled',
      'The values of one KPI are found under the other ID.', a)
# 10 year labels shifted by +1 for one KPI (compare with the previous file)
k = '1392'
for r in rows_by_key[k]:
    hs.cell(r, 3).value = int(hs.cell(r, 3).value) + 1
plant(10, 'Year labels moved one year later for one KPI', f'historical, KeyID {k}, column year',
      'year labels shifted between historical files', 'The same values carry year Y in the previous file and Y+1 in this one.', k)
# 11 historical series cut after 2018 (old edition of the source)
k = '1389'
for r in rows_by_key[k]:
    if int(hs.cell(r, 3).value) > 2018:
        for j in range(4, hs.max_column + 1):
            hs.cell(r, j).value = None
plant(11, 'Historical series stops in 2018', f'historical, KeyID {k}', 'none: not a file error the precheck can see',
      'The index values still match a source year, so the files look consistent. It shows in the Data Quality Profile: '
      'the data look older than for other countries, and the last source year is 2018 while the edition is 2026. To be spotted by eye.', k)
# 12 a second series under one KPI ID: duplicate the 2020 rows with other values for some countries
k = '1419'
r20 = [r for r in rows_by_key[k] if int(hs.cell(r, 3).value) == 2020][0]
new = hs.max_row + 1
for j in range(1, hs.max_column + 1):
    hs.cell(new, j).value = hs.cell(r20, j).value
hs.cell(new, 2).value = 'Gini coefficient (old series)'
n = 0
for iso in ['FRA', 'DEU', 'ITA', 'ESP', 'NLD']:
    j = hcol[iso]
    v = hs.cell(new, j).value
    if isinstance(v, (int, float)):
        hs.cell(new, j).value = round(float(v) + 1.3, 2); n += 1
plant(12, 'A second series added under one KPI ID', f'historical, KeyID {k}, year 2020, last row of the sheet',
      'two series under one KPI ID (historical)', f'{n} countries have two different values for 2020.', k)
hs_wb.save(hist_out)

# verify
s = read_simulator(sim_out); h = read_historical(hist_out); prev = read_historical(OUT / 'historical_data_index_1032_SDG_2026_PREVIOUS_FILE.xlsx')
m = read_uce_metadata(META)
r = run(s, h, index_id='1032', edition=2026, uce_meta=m, hist_previous=prev)
found = []
for x in key:
    if x['expected check'].startswith('none'):
        found.append('not a precheck item'); continue
    hit = []
    for c in [c.strip() for c in x['expected check'].split(';')]:
        name = c if c in set(r.issues.check) else c.split(' (')[0].strip()
        if name.startswith('country code converted'):
            hit.append((r.mappings.kind == 'country code').any()); continue
        q = r.issues[r.issues.check == name]
        if x['kpi'] and name not in ('country ranked by the publisher, missing from the simulator', 'one code for two entities',
                                     'country in historical file, not in the index'):
            q = q[q.KPI.astype(str) == str(x['kpi'])]
        if x['iso'] and 'ISO' in q:
            q = q[q.ISO.astype(str) == str(x['iso'])]
        hit.append(len(q) > 0)
    found.append('yes' if all(hit) else ('partly' if any(hit) else 'NO'))
K = pd.DataFrame(key); K['found by the precheck'] = found
with pd.ExcelWriter(OUT / 'ANSWER_KEY_planted_mistakes.xlsx', engine='openpyxl') as w:
    K.to_excel(w, sheet_name='Answer key', index=False)
    r.issues.to_excel(w, sheet_name='Precheck output', index=False)
    r.mappings.to_excel(w, sheet_name='Automatic changes', index=False)
print(K[['no', 'mistake', 'expected check', 'found by the precheck']].to_string())
print(r.issues[r.issues.severity != 'info'].groupby('check').size().to_string())
