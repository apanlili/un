"""Run dqp_precheck on every active index, reading the simulator (raw_) and historical files directly, with the UCE
metadata (publisher country list, indicator KeyIDs) when it exists. Writes one workbook for all indices and one folder
per index with a note and the items to check.

usage: python run_precheck.py jobs.csv out_dir
jobs.csv columns: index, index ID, edition, raw, hist, uce_meta (optional), hist_previous (optional),
                  raw_title, hist_title, uce_title (titles as on Drive, for the notes), drive_raw, drive_hist (file ids)
"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from dqp_precheck import run
from dqp_precheck.readers import read_simulator, read_historical, read_uce_metadata, edition_from_name

JOBS, DEST = Path(sys.argv[1]), Path(sys.argv[2])
DEST.mkdir(parents=True, exist_ok=True)

WHAT = {
    'historical file layout': 'Historical files on Drive come in two layouts (ISO codes in row 1 or in row 2) and with extra or differently spelled header columns. The Data Quality Profile code reads row 1 as ISO codes, so a file in the other layout gives no match at all (everything in bucket E).',
    'one code for two entities': 'The same country code is written for two entities. Each entity gets its own line. When the second entity has its own code it is moved there in the check; the file itself must be corrected at ingestion.',
    'KPI not reconciled': 'For this KPI, the index values (what the publisher used) are not found in the historical file for most countries, so the profile cannot say which year the publisher used. The diagnosis says why.',
    'two series under one KPI ID (historical)': 'The historical file holds two different values for the same country, KPI and year: two series were loaded under one KPI ID. One line per country and year.',
    'scale factor between files': 'Every index value equals the source value times a power of ten (for example a share in the source, a percentage in the index). Applied in the check; to confirm.',
    'country appears twice in the file': 'A second column for the same country exists in the source file (pandas renames it ATG.1). One of the two columns is wrong.',
    'country code not recognised': 'The code is not in the Geographic Reference sheet, as an official code or as an alias. Nothing is guessed: add it to the sheet or correct the file.',
    'country in historical file, not in the index': 'The country has historical data but no index value: the publisher does not cover it in this edition. Information only; ESCWA members are marked.',
    'value not numeric': 'Some value cells hold text (for example ".." or "n/a"). They are read as missing.',
    'KPI in simulator, not in historical file': 'The index uses this KPI but the historical file has no series for it.',
    'KPI not in metadata file': 'The KPI has no row in the metadata file.',
    'KPI in metadata, not in simulator': 'The metadata describes a KPI that the simulator does not hold.',
    'KPI not in the UCE metadata': 'The KPI is in the simulator but not in the indicators sheet of the UCE metadata.',
    'KPI in the UCE metadata, not in the simulator': 'The UCE metadata lists an indicator that the simulator does not hold.',
    'KPI ID not valid': 'KPI IDs must be a number, or a number followed by _female or _male.',
    'simulator and historical file from different editions': 'The year in the simulator file name and the year in the historical file name differ.',
    'source years after the index edition': 'The historical file holds years later than the edition. They cannot make an index value old, but the label may be wrong.',
    'value matches another country': "The country's index value is not in its own source series, but equals another country's source value for the year the publisher used. Usually a value pasted on the wrong row.",
    'rows shifted': 'Many countries carry the value of the country next to them in the file: a block of rows has moved by one.',
    'KPI values match another KPI': "This KPI's index values are found in the series of another KPI. Usually two KPI IDs swapped, or one series loaded under the wrong ID.",
    'unit differs for one country': "This country's value is 100 times (or a hundredth of) its source value, while the other countries match without a factor.",
    'year labels possibly shifted': 'The year the publisher used, as found in the historical file, is later than the edition: the year labels are probably one year off.',
    'year labels shifted between historical files': 'Compared with the previous historical file, the same values carry a different year.',
    'country ranked by the publisher, missing from the simulator': 'The country is in the publisher list (country sheet of the UCE metadata) but has no row or no values in the simulator.',
    'country in the simulator, not in the publisher list': 'The country has values in the simulator but is not in the publisher list of the UCE metadata.',
    'one KPI ID, several names (simulator)': 'One KPI ID carries several different names.',
    'duplicate row, different values (simulator)': 'The same country appears twice in the simulator with different values.',
}


def slug(t):
    return re.sub(r'[^A-Za-z0-9]+', '_', str(t)).strip('_')


def val(x):
    return None if (x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == '') else str(x)


jobs = pd.read_csv(JOBS, dtype=str)
I, M, K, S = [], [], [], []
for j in jobs.itertuples(index=False):
    j = j._asdict()
    title, num, ed = j['index'], str(j['index_ID']), int(j['edition'])
    row = {'index': title, 'index ID': num, 'edition': ed, 'simulator file': j.get('raw_title'), 'historical file': j.get('hist_title'),
           'UCE metadata': j.get('uce_title') or 'none on Drive'}
    try:
        sim = read_simulator(j['raw']); lay = []; hist = read_historical(j['hist'], notes=lay)
        hist = hist[hist.year.notna()]
        uce = read_uce_metadata(j['uce_meta']) if val(j.get('uce_meta')) else None
        prev = read_historical(j['hist_previous']) if val(j.get('hist_previous')) else None
        he = edition_from_name(j.get('hist_title') or '')
        r = run(sim, hist, index_id=num, edition=ed, hist_edition=he, uce_meta=uce, hist_previous=prev)
        if lay:
            add = pd.DataFrame([{'check': 'historical file layout', 'severity': 'review', 'KPI': '', 'ISO': '', 'n': None,
                                 'detail': f'{x}. Read correctly here; correct the file so that every reader gets the same layout.'} for x in lay])
            r.issues = pd.concat([r.issues, add.reindex(columns=r.issues.columns)], ignore_index=True)
            if r.status == 'pass':
                r.status = 'review'
    except Exception as e:
        row.update({'status': 'not run', 'note': f'{type(e).__name__}: {e}'[:300]}); S.append(row)
        print(title, 'NOT RUN', e, flush=True); continue
    for t, acc in ((r.issues, I), (r.mappings, M), (r.kpis, K)):
        t = t.copy(); t.insert(0, 'index', title); t.insert(1, 'index ID', num); t.insert(2, 'edition', ed); acc.append(t)
    cnt = r.issues.severity.value_counts()
    row.update({'status': r.status, 'to fix': int(cnt.get('refuse', 0)), 'to review': int(cnt.get('review', 0)),
                'information': int(cnt.get('info', 0)), 'automatic changes': len(r.mappings),
                'KPIs': int(r.kpis.in_simulator.sum()), 'KPIs not reconciled': int((r.issues.check == 'KPI not reconciled').sum()),
                'ESCWA members in simulator': int(r.coverage.in_simulator.sum())})
    S.append(row)
    d = DEST / 'by_index' / f'{slug(title)}_{num}_{ed}'
    d.mkdir(parents=True, exist_ok=True)
    act = r.issues[r.issues.severity != 'info']
    lines = [f'# {title} (index {num}), edition {ed}', '',
             f'Status: **{r.status}**. To fix: {cnt.get("refuse", 0)}. To review: {cnt.get("review", 0)}. Information: {cnt.get("info", 0)}.', '',
             'Files checked (Google Drive):', '',
             f'- simulator: [{j.get("raw_title")}](https://drive.google.com/file/d/{j.get("drive_raw")}/view)',
             f'- historical: [{j.get("hist_title")}](https://drive.google.com/file/d/{j.get("drive_hist")}/view)',
             f'- UCE metadata: ' + (f'[{j.get("uce_title")}](https://drive.google.com/file/d/{j.get("drive_uce")}/view)' if val(j.get('uce_meta')) else 'none on Drive (publisher list and KeyIDs not compared)'), '']
    if val(j.get('note')):
        lines += [f'Note on the files: {j["note"]}', '']
    if len(act):
        lines += ['## Items to fix or review', '']
        for chk, g in act.groupby('check', sort=False):
            lines += [f'### {chk} ({len(g)})', '', WHAT.get(chk, ''), '']
            for q in g.itertuples():
                where = ' '.join(x for x in [f'KPI {q.KPI}' if q.KPI else '', f'{q.ISO}' if q.ISO else ''] if x)
                lines += [f'- {where}: {q.detail}' if where else f'- {q.detail}']
            lines += ['']
    else:
        lines += ['Nothing to fix or review.', '']
    info = r.issues[r.issues.severity == 'info']
    if len(info):
        lines += ['## Information', '']
        for chk, g in info.groupby('check', sort=False):
            lines += [f'- {chk}: {len(g)}' + (f' ({", ".join(sorted(set(map(str, g.ISO)) - {""}))[:400]})' if 'ISO' in g else '')]
        lines += ['']
    absent = r.coverage[~r.coverage.in_simulator].ISO.tolist()
    lines += ['## ESCWA member states', '', f'{int(r.coverage.in_simulator.sum())} of 22 in the simulator.' +
              (f' Not covered by the publisher: {", ".join(absent)}.' if absent else ''), '']
    (d / 'note.md').write_text('\n'.join(lines), encoding='utf-8')
    with pd.ExcelWriter(d / 'items.xlsx', engine='openpyxl') as w:
        act.to_excel(w, sheet_name='To fix or review', index=False)
        r.mappings.to_excel(w, sheet_name='Automatic changes', index=False)
        r.kpis.to_excel(w, sheet_name='KPIs', index=False)
        info.to_excel(w, sheet_name='Information', index=False)
    print(title, ed, r.status, dict(cnt), flush=True)

S = pd.DataFrame(S)
cat = lambda L: pd.concat(L, ignore_index=True) if L else pd.DataFrame()
I, M, K = cat(I), cat(M), cat(K)
expl = pd.DataFrame([{'check': k, 'what it means': v} for k, v in WHAT.items()])
with pd.ExcelWriter(DEST / 'precheck_all_indices.xlsx', engine='openpyxl') as w:
    S.to_excel(w, sheet_name='Summary', index=False)
    I[I.severity != 'info'].to_excel(w, sheet_name='To fix or review', index=False)
    M.to_excel(w, sheet_name='Automatic changes', index=False)
    K.to_excel(w, sheet_name='KPIs', index=False)
    I[I.severity == 'info'].to_excel(w, sheet_name='Information', index=False)
    expl.to_excel(w, sheet_name='What each check means', index=False)
print(S.to_string())
if len(I):
    print(I[I.severity != 'info'].groupby(['severity', 'check']).size().to_string())
