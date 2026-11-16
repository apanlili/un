"""Known-answer tests for dqp_precheck. Run: python -m dqp_precheck.tests  (from the folder holding the packages).

Each test builds a small input whose right answer is known, runs the checks and compares. Cases T01 to T14 come
from problems met in the ISPAR files (October 2026); the file where each was met is given."""
import numpy as np
import pandas as pd

from .checks import run


def _sim(rows):
    return pd.DataFrame(rows, columns=['ISO', 'Country', 'KPI', 'KPI name', 'v'])


def _hist(rows):
    return pd.DataFrame(rows, columns=['ISO', 'KPI', 'year', 'h'])


def _base(n=8, kpi='1700', scale=1.0):
    """n countries, one KPI, index value = source value of 2023 x scale."""
    isos = ['FRA', 'DEU', 'ITA', 'ESP', 'NLD', 'BEL', 'AUT', 'PRT', 'GRC', 'IRL'][:n]
    s = [(c, c, kpi, 'Indicator', round(10 + i * 1.7, 2)) for i, c in enumerate(isos)]
    h = [(c, kpi, y, round((10 + i * 1.7) / scale, 4) if y == 2023 else 5.0) for i, c in enumerate(isos) for y in (2021, 2022, 2023)]
    return _sim(s), _hist(h)


def _has(r, check, severity=None, iso=None, kpi=None):
    q = r.issues[r.issues.check == check]
    if severity: q = q[q.severity == severity]
    if iso: q = q[q.ISO == iso]
    if kpi: q = q[q.KPI == kpi]
    return len(q) > 0


CASES = []


def case(cid, text):
    def deco(f):
        CASES.append((cid, text, f)); return f
    return deco


@case('T01', 'Clean files pass (no review item)')
def t01():
    s, h = _base()
    r = run(s, h, index_id='9999')
    return r.status == 'pass' and r.kpis.share_matched.iloc[0] == 1.0


@case('T02', 'CYP written for Cyprus and Northern Cyprus: flagged (not refused), Northern Cyprus moved to XNC and logged (WPF 2025, 2026)')
def t02():
    s, h = _base()
    s = pd.concat([s, _sim([('CYP', 'Cyprus', '1700', 'Indicator', 42.85), ('CYP', 'Northern Cyprus', '1700', 'Indicator', 46.86)])])
    r = run(s, h, index_id='1036')
    x = r.sim.set_index('Country')
    return r.status == 'review' and _has(r, 'one code for two entities', 'review', 'CYP') and \
        _has(r, 'one code for two entities', 'review', 'XNC') and \
        x.at['Northern Cyprus', 'ISO'] == 'XNC' and x.at['Cyprus', 'ISO'] == 'CYP' and \
        ((r.mappings['from'] == 'CYP') & (r.mappings['to'] == 'XNC')).any()


@case('T03', 'Publisher and old codes converted and logged: KSV, WBG, PES, ZAR, ROM, TMP (WBL, GovTech, DARE)')
def t03():
    s, h = _base()
    extra = [('KSV', 'Kosovo', '1700', 'Indicator', 1.0), ('WBG', 'West Bank and Gaza', '1700', 'Indicator', 2.0),
             ('PES', 'Palestine', '1700', 'Indicator', 3.0), ('ZAR', 'Congo', '1700', 'Indicator', 4.0),
             ('ROM', 'Romania', '1700', 'Indicator', 5.0), ('TMP', 'Timor-Leste', '1700', 'Indicator', 6.0)]
    r = run(pd.concat([s, _sim(extra)]), h, index_id='1021')
    got = dict(zip(r.mappings.loc[r.mappings.kind == 'country code', 'from'], r.mappings.loc[r.mappings.kind == 'country code', 'to']))
    return got == {'KSV': 'XKX', 'WBG': 'PSE', 'PES': 'PSE', 'ZAR': 'COD', 'ROM': 'ROU', 'TMP': 'TLS'} and \
        set(r.sim.loc[r.sim.ISO_original == 'WBG', 'ISO']) == {'PSE'}


@case('T04', 'CSS becomes XOE only in RSF files (index 1036); elsewhere it is the World Bank aggregate and is not converted')
def t04():
    s, h = _base()
    x = _sim([('CSS', 'OECS', '1700', 'Indicator', 60.0)])
    r1 = run(pd.concat([s, x]), h, index_id='1036')
    r2 = run(pd.concat([s, x]), h, index_id='1032')
    return 'XOE' in set(r1.sim.ISO) and 'XOE' not in set(r2.sim.ISO) and _has(r2, 'country code not recognised', iso='CSS')


@case('T05', 'Palestine is found whichever code the file uses (coverage of ESCWA members)')
def t05():
    s, h = _base()
    r = run(pd.concat([s, _sim([('WBG', 'West Bank and Gaza', '1700', 'Indicator', 2.0)])]), h, index_id='1037')
    return bool(r.coverage.set_index('ISO').at['PSE', 'in_simulator'])


@case('T06', 'A country name in the code column is converted by name (WPF 2026: Liechtenstein; GCI: Lao PDR)')
def t06():
    s, h = _base()
    r = run(pd.concat([s, _sim([('Liechtenstein', 'Liechtenstein', '1700', 'Indicator', 80.0), ('Lao PDR', 'Lao PDR', '1700', 'Indicator', 30.0)])]), h, index_id='1036')
    return {'LIE', 'LAO'} <= set(r.sim.ISO) and (r.mappings.reason == 'name in the code column').sum() == 2


@case('T07', 'Aggregates and empty columns are dropped as information (GDI: ZZA.VHHD; DARE: Unnamed: 68)')
def t07():
    s, h = _base()
    h2 = pd.concat([h, _hist([('ZZA.VHHD', '1700', 2023, 1.0), ('Unnamed: 68', '1700', 2023, 1.0)])])
    r = run(s, h2, index_id='1030')
    return r.status == 'pass' and _has(r, 'aggregate or regional code', 'info') and _has(r, 'empty or unnamed country column', 'info') \
        and not r.hist.ISO_original.isin(['ZZA.VHHD', 'Unnamed: 68']).any()


@case('T08', 'A second column for the same country (ITU: ATG.1, IRN.1) is set aside for review')
def t08():
    s, h = _base()
    r = run(s, pd.concat([h, _hist([('FRA.1', '1700', 2023, 99.0)])]), index_id='5')
    return r.status == 'review' and _has(r, 'country appears twice in the file', 'review', 'FRA.1') and 99.0 not in set(r.hist.h)


@case('T09', 'Unknown code is reported, never guessed')
def t09():
    s, h = _base()
    r = run(pd.concat([s, _sim([('QQQ', 'Atlantis', '1700', 'Indicator', 1.0)])]), h, index_id='9999')
    return _has(r, 'country code not recognised', 'review', 'QQQ') and 'QQQ' not in set(r.sim.ISO)


@case('T10', 'KPI traceability: missing from historical, metadata and canonical list; IDs cleaned (1366.0 -> 1366)')
def t10():
    s, h = _base(kpi='1366.0')
    s2 = pd.concat([s, _sim([('FRA', 'FRA', '1367', 'Other', 1.0)])])
    meta = pd.DataFrame({'KPI': ['1366', '1999']})
    r = run(s2, h, meta=meta, canonical_kpis=['1366'], index_id='1032')
    k = r.kpis.set_index('KPI')
    return _has(r, 'KPI in simulator, not in historical file', kpi='1367') and _has(r, 'KPI not in metadata file', kpi='1367') \
        and _has(r, 'KPI in metadata, not in simulator', kpi='1999') and _has(r, 'KPI ID not in the canonical list', kpi='1367') \
        and '1366' in k.index and bool(k.at['1366', 'in_historical']) and (r.mappings.kind == 'KPI ID').any()


@case('T11', 'Two series under one KPI ID in the historical file are flagged (GII KPI 136)')
def t11():
    s, h = _base()
    r = run(s, pd.concat([h, _hist([('FRA', '1700', 2023, 77.0)])]), index_id='7')
    return _has(r, 'two series under one KPI ID (historical)', 'review', 'FRA', '1700') and \
        (r.issues.check == 'two series under one KPI ID (historical)').sum() == 1


@case('T12', 'Factor 100 between files is detected, applied in h_scaled only, logged (WPS KPI 1120; FII computers)')
def t12():
    s, h = _base(scale=100.0)
    r = run(s, h, index_id='1022')
    k = r.kpis.set_index('KPI')
    return k.at['1700', 'scale_factor'] == 100 and k.at['1700', 'share_matched'] == 1.0 and \
        np.allclose(r.hist.h_scaled, r.hist.h * 100) and _has(r, 'scale factor between files', 'review', kpi='1700') \
        and (r.mappings.kind == 'scale factor').sum() == 1


@case('T13', 'A factor confirmed in metadata is used and not listed for review')
def t13():
    s, h = _base(scale=100.0)
    r = run(s, h, index_id='1022', confirmed_scale={'1700': 100})
    return r.kpis.set_index('KPI').at['1700', 'scale_basis'] == 'confirmed in metadata' and not _has(r, 'scale factor between files')


@case('T14', 'Wrong series under the right ID: fewer than half of countries match -> KPI not reconciled')
def t14():
    s, h = _base()
    h['h'] = h['h'] * 1.37 + 3
    r = run(s, h, index_id='9999')
    return _has(r, 'KPI not reconciled', 'review', kpi='1700')


@case('T15', 'Duplicate rows: same value kept once (info); different values refused')
def t15():
    s, h = _base()
    r1 = run(pd.concat([s, s.iloc[[0]]]), h, index_id='9999')
    d = s.iloc[[0]].copy(); d['v'] = 0.5
    r2 = run(pd.concat([s, d]), h, index_id='9999')
    return r1.status == 'pass' and len(r1.sim) == len(s) and r2.status == 'refuse'


@case('T16', 'Source years after the edition are reported (they cannot make an index value "old")')
def t16():
    s, h = _base()
    r = run(s, pd.concat([h, _hist([('FRA', '1700', 2027, 1.0)])]), index_id='9999', edition=2026)
    return _has(r, 'source years after the index edition', 'info')


@case('T17', 'Text in a value cell is reported and read as missing ("..", "n/a")')
def t17():
    s, h = _base()
    s['v'] = s['v'].astype(object); s.iloc[0, s.columns.get_loc('v')] = '..'
    r = run(s, h, index_id='9999')
    return _has(r, 'value not numeric', 'review')


@case('T18', 'KPI IDs with _female or _male are valid; other text is not')
def t18():
    s, h = _base(kpi='1450_female')
    r1 = run(s, h, index_id='4')
    s2, h2 = _base(kpi='1450_F')
    r2 = run(s2, h2, index_id='4')
    return not _has(r1, 'KPI ID not valid') and _has(r2, 'KPI ID not valid')


@case('T19', 'A country in the historical file but not in the index is listed as not covered (ESCWA members marked)')
def t19():
    s, h = _base()
    r = run(s, pd.concat([h, _hist([('JOR', '1700', 2023, 12.0)])]), index_id='9999')
    q = r.issues[r.issues.check == 'country in historical file, not in the index']
    return len(q) == 1 and q.ISO.iloc[0] == 'JOR' and q.detail.iloc[0].startswith('ESCWA member') and r.status == 'pass'


@case('T20', 'Constant ratio between files (not a power of ten) is diagnosed as a unit or base difference')
def t20():
    s, h = _base()
    h['h'] = h['h'] / 1.3
    r = run(s, h, index_id='9999')
    return r.kpis.set_index('KPI').at['1700', 'diagnosis'] == 'constant ratio (unit or base)'


ISOS = ['FRA', 'DEU', 'ITA', 'ESP', 'NLD', 'BEL', 'AUT', 'PRT', 'GRC', 'IRL']


def _base2(kpi='1700', shift=0.0):
    """10 countries, values with 2 decimals, source = index value for 2023; earlier years distinct."""
    v = {c: round(10.37 + i * 1.713 + shift, 2) for i, c in enumerate(ISOS)}
    s = _sim([(c, c, kpi, 'Indicator', v[c]) for c in ISOS])
    h = _hist([(c, kpi, y, round(v[c] - (2023 - y) * 0.311, 2)) for c in ISOS for y in (2021, 2022, 2023)])
    return s, h


@case('T21', "A country's value equal to another country's source value is flagged (pasted on the wrong row)")
def t21():
    s, h = _base2()
    deu = s.loc[s.ISO == 'DEU', 'v'].iloc[0]
    s.loc[s.ISO == 'GRC', 'v'] = deu
    r = run(s, h, index_id='9999')
    q = r.issues[r.issues.check == 'value matches another country']
    return len(q) == 1 and q.ISO.iloc[0] == 'GRC' and 'DEU' in q.detail.iloc[0]


@case('T22', 'Rows shifted by one: flagged as rows shifted')
def t22():
    s, h = _base2()
    vals = s.v.tolist()
    s['v'] = [vals[0]] + vals[:-1]          # each country gets the value of the country above it
    r = run(s, h, index_id='9999')
    return _has(r, 'rows shifted', kpi='1700')


@case('T23', 'Two KPIs swapped in the historical file are detected both ways')
def t23():
    sa, ha = _base2('1700'); sb, hb = _base2('1701', shift=40.0)
    ha2 = ha.copy(); ha2['KPI'] = '1701'; hb2 = hb.copy(); hb2['KPI'] = '1700'
    r = run(pd.concat([sa, sb]), pd.concat([ha2, hb2]), index_id='9999')
    q = r.issues[r.issues.check == 'KPI values match another KPI']
    return len(q) >= 1 and 'swapped' in q.detail.iloc[0]


@case('T24', 'One country in percentage while the others are in shares: flagged for that country')
def t24():
    s, h = _base2()
    s.loc[s.ISO == 'AUT', 'v'] = s.loc[s.ISO == 'AUT', 'v'] * 100
    r = run(s, h, index_id='9999')
    return _has(r, 'unit differs for one country', iso='AUT', kpi='1700')


@case('T25', 'Index values found in the source after the edition year: year labels possibly shifted')
def t25():
    s, h = _base2()
    r = run(s, h, index_id='9999', edition=2022)
    return _has(r, 'year labels possibly shifted', kpi='1700')


@case('T26', 'Same values one year later than in the previous historical file: labels shifted')
def t26():
    s, h = _base2()
    prev = h.copy(); prev['year'] = prev['year'] - 1
    r = run(s, h, index_id='9999', hist_previous=prev)
    return _has(r, 'year labels shifted between historical files', kpi='1700')


@case('T27', 'Simulator countries compared with the publisher list of the UCE metadata, both ways')
def t27():
    s, h = _base2()
    uce = {'country': ISOS[1:] + ['JOR']}
    r = run(s, h, index_id='9999', uce_meta=uce)
    return _has(r, 'country ranked by the publisher, missing from the simulator', iso='JOR') and \
        _has(r, 'country in the simulator, not in the publisher list', iso='FRA')


@case('T29', 'Clean two-decimal data raise none of the cross-checks')
def t29():
    s, h = _base2()
    r = run(s, h, index_id='9999', edition=2026, uce_meta={'country': ISOS, 'indicators': pd.DataFrame({'KeyID': [1700], 'output_scale': [np.nan]})})
    return r.status == 'pass'


@case('T30', 'Historical file with codes in row 2, a category column and the sex in the series name is read correctly, each change stated')
def t30():
    from .readers import normalise_historical_grid
    raw = pd.DataFrame([[None, None, None, None, 'Angola', 'France'],
                        ['KeyId', 'Series name', 'category', 'Year', 'AGO', 'FRA'],
                        [26, 'Labor force participation rate (%) - Female', 1, 2024, 60.1, 70.2],
                        [26, 'Labor force participation rate (%) - Male', 1, 2024, 74.4, 75.0],
                        [27, 'Wage equality, index (1-7)', 2, 2024, 4.1, 5.0]])
    g, notes = normalise_historical_grid(raw)
    return (g.iloc[0, 3:].tolist() == ['AGO', 'FRA'] and g.iloc[1, :3].tolist() == ['KeyID', 'Series name', 'year']
            and g.iloc[2:, 0].tolist() == ['26_female', '26_male', 27] and len(notes) == 4)


@case('T31', 'Series moved by one KeyID in the historical file: reported as shifted, not as swapped')
def t31():
    ks = ['1700', '1701', '1702', '1703', '1704']
    vals = {k: {c: round(10.37 + i * 1.713 + 7.1 * n, 2) for i, c in enumerate(ISOS)} for n, k in enumerate(ks)}
    s = _sim([(c, c, k, 'Indicator ' + k, vals[k][c]) for k in ks for c in ISOS])
    rows = []
    for n, k in enumerate(ks):
        src = ks[min(n + 1, len(ks) - 1)]               # series of the next KPI written under this ID; last one repeated
        rows += [(c, k, 2023, vals[src][c]) for c in ISOS]
    r = run(s, _hist(rows), index_id='9999')
    q = r.issues[r.issues.check == 'KPI values match another KPI']
    return len(q) >= 3 and q.detail.str.contains('shifted by one KeyID').sum() >= 3 and not q.detail.str.contains('swapped').any()


def main():
    res = []
    for cid, text, f in CASES:
        try:
            ok = bool(f())
            err = ''
        except Exception as e:      # a crash is a failure
            ok, err = False, f'{type(e).__name__}: {e}'
        res.append((cid, 'pass' if ok else 'FAIL', text, err))
    for r in res:
        print(f'{r[0]}  {r[1]:4}  {r[2]}' + (f'  [{r[3]}]' if r[3] else ''))
    n = sum(r[1] == 'pass' for r in res)
    print(f'\n{n} of {len(res)} tests pass')
    return n == len(res)


if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
