"""Write the precheck-cleaned simulator and historical tables back in the file layouts the profile code reads, to run
the profile code on cleaned inputs (run C). Cleaned means: country codes and KPI IDs as corrected by the precheck,
historical values times the detected scale factor (h_scaled), layout unified. Nothing else changes: two series
under one KPI ID stay as two rows.
usage: python write_cleaned.py jobs.csv data_dir files.json"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from dqp_precheck import run
from dqp_precheck.readers import read_simulator, read_historical

JOBS, D, FJ = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
(D / 'Historical').mkdir(parents=True, exist_ok=True); (D / 'Simulator Data').mkdir(parents=True, exist_ok=True)
files = {}
for j in pd.read_csv(JOBS, dtype=str).itertuples():
    k = f'{j.index_ID}_{j.edition}'
    sim = read_simulator(j.raw); hist = read_historical(j.hist); hist = hist[hist.year.notna()]
    r = run(sim, hist, index_id=j.index_ID, edition=int(j.edition))
    s = r.sim.dropna(subset=['ISO'])
    s = s[s.ISO.astype(str).str.fullmatch(r'[A-Z]{3}')]
    kpis = list(dict.fromkeys(s.KPI))
    names = s.drop_duplicates('KPI').set_index('KPI')['KPI name']
    w = s.pivot_table(index=['ISO'], columns='KPI', values='v', aggfunc='first').reindex(columns=kpis)
    cn = s.drop_duplicates('ISO').set_index('ISO').Country
    head = ['Country', 'ISO', 'Region', 'Sub-region', 'Income Type'] + kpis
    rows = [head, [None] * 5 + [names.get(x) for x in kpis]]
    rows += [[cn.get(iso), iso, None, None, None] + w.loc[iso].tolist() for iso in w.index]
    pd.DataFrame(rows).to_excel(D / 'Simulator Data' / f'{k}_raw.xlsx', header=False, index=False)
    h = r.hist.dropna(subset=['h_scaled'])
    h = h[h.ISO.astype(str).str.fullmatch(r'[A-Z]{3}')]
    h = h.assign(nm=h['KPI name'].fillna('').astype(str))
    h = h.assign(occ=h.groupby(['KPI', 'nm', 'year', 'ISO']).cumcount())   # second value for the same cell -> second row
    hw = h.pivot_table(index=['KPI', 'nm', 'year', 'occ'], columns='ISO', values='h_scaled', aggfunc='first')
    isos = list(hw.columns)
    out = [[None, None, None] + isos, ['KeyID', 'Series name', 'year'] + isos]
    out += [[a, b, int(c)] + v.tolist() for (a, b, c, _), v in hw.iterrows()]
    pd.DataFrame(out).to_excel(D / 'Historical' / f'{k}_hist.xlsx', header=False, index=False)
    files[f'index_{k}'] = [f'{k}_hist.xlsx', '', f'{k}_raw.xlsx']
    print(k, 'written', flush=True)
json.dump(files, open(FJ, 'w'), indent=1)
