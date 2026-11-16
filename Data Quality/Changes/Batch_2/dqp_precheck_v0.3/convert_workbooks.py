"""Convert M&J calculation workbooks (no raw_ file on Drive) to the raw_ simulator layout read by the profile code.
Each indicator column is identified by its name, matched to a KeyID through the UCE metadata indicators sheet
(indicator_label) or the historical file (Series name): exact match after removing case and punctuation, or the
label being the start of the column name (TTDI writes "Burden of government regulation, 1-7 (best)").
Country codes: the ISO column when there is one; otherwise the country name, looked up in the country sheet of the
UCE metadata (publisher names), then converted by the precheck.
Every unmatched indicator is listed. usage: python convert_workbooks.py out_dir"""
import sys, re, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from dqp_precheck.readers import read_uce_metadata, read_historical
from dqp_precheck.checks import reconcile_codes  # noqa: F401  (imported to fail early if the package is missing)
from dqp_precheck import run

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
norm = lambda t: re.sub(r'[^a-z0-9]', '', str(t).lower())
CFG = {
    '6_2025': dict(title='Network Readiness Index', sheet='2025', name_row=2, first=3, country=0, iso=1),
    '14_2025': dict(title='AI Readiness Index', sheet='Indicator Level', name_row=2, first=4, country=0, iso=None),
    '1033_2026': dict(title='Travel and Tourism Development Index', sheet='calculation', name_row=2, first=4, country=0, iso=1),
    '1020_2023': dict(title='Global Development Index', sheet='GDI (2023)', name_row=0, first=6, country=0, iso=1),
}
report = []
for k, c in CFG.items():
    base = Path('inv_files') / k
    labels = []
    if (base / 'uce_meta.xlsx').exists():
        ind = read_uce_metadata(base / 'uce_meta.xlsx').get('indicators')
        if ind is not None:
            labels += [(norm(l), str(i), 'UCE metadata') for i, l in zip(ind.KeyID, ind.indicator_label)]
    h = read_historical(base / 'hist.xlsx')
    labels += [(norm(n), str(i), 'historical file') for i, n in h.drop_duplicates('KPI')[['KPI', 'KPI name']].values]
    x = pd.read_excel(base / 'raw.xlsx', sheet_name=c['sheet'], header=None, dtype=object)
    names = x.iloc[c['name_row']].tolist()
    body = x.iloc[c['first']:]
    body = body[body[c['country']].notna()]
    cols, used = [], set()
    for j, nm in enumerate(names):
        if nm is None or (isinstance(nm, float) and pd.isna(nm)) or j in (c['country'], c['iso']):
            continue
        n = norm(nm)
        hit = next(((i, src) for l, i, src in labels if l and n == l), None) or \
              next(((i, src) for l, i, src in sorted(labels, key=lambda t: -len(t[0])) if len(l) >= 8 and n.startswith(l)), None)
        if hit and hit[0] not in used:
            used.add(hit[0]); cols.append((j, hit[0], str(nm).strip(), hit[1]))
    kpis = {i for _, i, _ in labels}
    by_name = {}
    if (base / 'uce_meta.xlsx').exists():                       # publisher names and codes (country sheet)
        cs = pd.read_excel(base / 'uce_meta.xlsx', sheet_name='country')
        nc = next((q for q in cs.columns if str(q).strip().lower() == 'country'), None)
        ic = next((q for q in cs.columns if str(q).strip().upper() == 'ISO'), None)
        if nc and ic:
            by_name = {norm(a): str(b).strip() for a, b in zip(cs[nc], cs[ic]) if pd.notna(a) and pd.notna(b)}
    rows = []
    for _, r in body.iterrows():
        iso = r[c['iso']] if c['iso'] is not None else by_name.get(norm(r[c['country']]), r[c['country']])
        for j, kid, nm, _ in cols:
            rows.append({'ISO': str(iso).strip(), 'Country': str(r[c['country']]).strip(), 'KPI': kid, 'KPI name': nm,
                         'v': pd.to_numeric(r[j], errors='coerce')})
    sim = pd.DataFrame(rows)
    res = run(sim, h[h.year.notna()], index_id=k.split('_')[0], edition=int(k.split('_')[1]))
    s = res.sim[res.sim.ISO.astype(str).str.fullmatch(r'[A-Z]{3}')]
    order = [i for _, i, _, _ in cols]
    w = s.pivot_table(index='ISO', columns='KPI', values='v', aggfunc='first').reindex(columns=order)
    cn = s.drop_duplicates('ISO').set_index('ISO').Country
    nm = {i: n for _, i, n, _ in cols}
    grid = [['Country', 'ISO', 'Region', 'Sub-region', 'Income Type'] + order, [None] * 5 + [nm[i] for i in order]]
    grid += [[cn.get(iso), iso, None, None, None] + w.loc[iso].tolist() for iso in w.index]
    pd.DataFrame(grid).to_excel(OUT / f'raw_{k}_converted.xlsx', header=False, index=False)
    sh = res.kpis.set_index('KPI').share_matched
    report.append({'index': c['title'], 'key': k, 'sheet used': c['sheet'], 'indicator columns matched to a KeyID': len(cols),
                   'KeyIDs known (UCE metadata + historical)': len(kpis), 'countries': len(w),
                   'KeyIDs not found in the workbook': ', '.join(sorted(kpis - used, key=lambda t: (len(t), t))),
                   'median share of countries whose value is in the source': round(float(sh.median()), 2) if len(sh) else None,
                   'KPIs with a value in the source for most countries': int((sh >= 0.5).sum())})
    print(report[-1], flush=True)
R = pd.DataFrame(report); R.to_csv(OUT / 'conversion_report.csv', index=False)
