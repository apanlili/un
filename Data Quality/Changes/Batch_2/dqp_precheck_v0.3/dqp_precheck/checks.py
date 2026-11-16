"""Checks run on an index's input files before matching and classification (the Data Quality Profile code).

Contract
--------
Inputs, long format, one index and one edition:
  sim   : ISO, KPI, v  [, Country, KPI name]       value used by the publisher (simulator file)
  hist  : ISO, KPI, year, h  [, KPI name]          historical source values
  meta  : KPI  [, KPI name, Source, URL]           index metadata file (optional)
  canonical_kpis : iterable of KPI IDs              canonical KeyID list for the index (optional)

run() returns a Result:
  status    'refuse'  : at least one problem that makes any comparison wrong; fix the file and run again
            'review'  : the files can be used; some items need a person (listed in issues)
            'pass'    : nothing to review
  sim, hist  cleaned copies. Nothing is overwritten: ISO_original and KPI_original keep what the file said,
             h is the source value as received, h_scaled = h x the confirmed or detected scale factor.
  issues     one row per problem: check, severity (refuse | review | info), KPI, ISO, n, detail
  mappings   log of every automatic change (country code converted, KPI ID cleaned, scale factor applied)
  kpis       one row per KPI: where it appears, scale factor, share of countries matched
  coverage   the ESCWA member states: present or absent in the simulator file (coverage is the publisher's
             decision; this is information, never corrected)

Rules (decisions of 17 to 20 October 2026)
  * Country codes are reconciled to the canonical code of the Geographic Reference sheet (official ISO
    alpha-3, approved ISPAR codes XKX, XOE, XNC, CHI). Publisher codes and old ISO codes are converted
    (ispar_reference.CountryCodes). An unknown code is never guessed: it is reported.
  * A file in which one canonical code stands for two countries (CYP for Cyprus and Northern Cyprus) is
    refused: the file is corrected at ingestion.
  * Scale and unit conversions are explicit: a power-of-ten factor between the files is detected, applied
    in h_scaled only, logged, and listed for confirmation in the metadata.
  * The checks improve matching without changing the source evidence.
"""
from dataclasses import dataclass, field
import re
import numpy as np
import pandas as pd

from ispar_reference import CountryCodes

ESCWA = ['DZA', 'BHR', 'COM', 'DJI', 'EGY', 'IRQ', 'JOR', 'KWT', 'LBN', 'LBY', 'MRT', 'MAR', 'OMN', 'PSE', 'QAT',
         'SAU', 'SOM', 'SDN', 'SYR', 'TUN', 'ARE', 'YEM']          # 22 member states (Comoros treated as a member)

PARAMS = {
    'scale_share': 0.60,     # share of countries that must agree on a power-of-ten factor
    'scale_tol': 0.02,       # relative tolerance around the power of ten
    'scale_min_n': 5,        # countries needed to detect a factor
    'match_min_share': 0.50, # below this share of countries matched (any year), the KPI is listed as not reconciled
    'max_decimals': 6,
    'cat_max_levels': 10,    # KPIs with at most this many distinct values are treated as categorical
    'rel_tol_any': 0.01,     # within 1% of a source value of any year counts as found (source revised since)
}

COLS_ISSUES = ['check', 'severity', 'KPI', 'ISO', 'n', 'detail']
COLS_MAP = ['kind', 'file', 'from', 'to', 'rows', 'reason']


@dataclass
class Result:
    status: str
    sim: pd.DataFrame
    hist: pd.DataFrame
    issues: pd.DataFrame
    mappings: pd.DataFrame
    kpis: pd.DataFrame
    coverage: pd.DataFrame
    meta: dict = field(default_factory=dict)

    def summary(self):
        s = self.issues.groupby(['severity', 'check']).size().rename('items').reset_index()
        return s.sort_values(['severity', 'check'], key=lambda c: c.map({'refuse': 0, 'review': 1, 'info': 2}) if c.name == 'severity' else c)


class _Log:
    def __init__(self):
        self.issues, self.maps = [], []

    def issue(self, check, severity, detail, n=1, kpi='', iso=''):
        self.issues.append({'check': check, 'severity': severity, 'KPI': kpi, 'ISO': iso, 'n': int(n), 'detail': detail})

    def map(self, kind, file, a, b, rows, reason):
        self.maps.append({'kind': kind, 'file': file, 'from': a, 'to': b, 'rows': int(rows), 'reason': reason})


# --------------------------------------------------------------------------- helpers
def _decimals(x, maxd=6):
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    for d in range(maxd + 1):
        hit = ok & np.isnan(out) & (np.abs(x * 10 ** d - np.round(x * 10 ** d)) < 1e-6)
        out[hit] = d
    out[ok & np.isnan(out)] = maxd
    return out


def clean_kpi_id(k):
    """KPI IDs as text without spaces or a trailing '.0' (Excel turns 1366 into 1366.0); the _female/_male suffix in
    lower case (26_FEMALE and 26_female are the same KPI)."""
    if k is None or (isinstance(k, float) and np.isnan(k)):
        return ''
    s = str(k).strip()
    s = re.sub(r'\.0+$', '', s)
    s = re.sub(r'_(female|male)$', lambda m: '_' + m.group(1).lower(), s, flags=re.I)
    return s


def _name_table():
    """Country names -> canonical code, from the ISPAR classification file (raw files 2026), for files that put a
    name in the code column (Liechtenstein, Lao PDR). Names in the Geographic Reference sheet are used first."""
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / 'reference' / 'country_classification_2026.csv'
    t = {}
    if f.exists():
        c = pd.read_csv(f)
        for iso, name in zip(c.ISO, c.Country):
            t[re.sub(r'[^a-z0-9]', '', str(name).lower())] = str(iso)
    return t


_NAMES = None


def _by_name(cc, name, index_id=None):
    global _NAMES
    if not isinstance(name, str) or not name.strip():
        return ''
    hit = cc.canonical('', name=name, index_id=index_id)
    if hit:
        return hit
    if _NAMES is None:
        _NAMES = _name_table()
    return _NAMES.get(re.sub(r'[^a-z0-9]', '', name.lower()), '')


_AGGREGATE = re.compile(r'^(ZZ[A-Z]?\.|WLD$|ARB$|EAP$|ECA$|LAC$|MNA$|SAS$|SSA$|SSF$|HIC$|LIC$|LMC$|UMC$|OED$)')
_SUFFIX = re.compile(r'^([A-Z]{3})\.\d+$')      # ATG.1: pandas renamed a second column with the same header


# --------------------------------------------------------------------------- country codes
def reconcile_codes(df, which, cc, index_id, log):
    """Map every code to its canonical code. Returns the frame with ISO (canonical) and ISO_original."""
    d = df.copy()
    d['ISO_original'] = d['ISO'].astype(str).str.strip()
    names = d['Country'] if 'Country' in d.columns else pd.Series('', index=d.index)
    out, keep = [], []
    for code, name in zip(d['ISO_original'], names):
        cu = code.upper()
        if cu.startswith('UNNAMED') or cu in ('', 'NAN', 'NONE'):
            out.append(None); keep.append(False); continue
        if _AGGREGATE.match(cu):
            out.append(None); keep.append(False); continue
        m = _SUFFIX.match(cu)
        if m:
            out.append(None); keep.append(False); continue
        can = cc.canonical(cu, index_id=index_id)
        if cc.canonical_codes and can not in cc.canonical_codes:
            byname = _by_name(cc, code, index_id) or _by_name(cc, name, index_id)
            out.append(byname or None); keep.append(bool(byname))
            continue
        out.append(can); keep.append(True)
    d['ISO'] = out
    # report, once per original code
    for code, g in d.groupby('ISO_original', dropna=False):
        cu = str(code).upper(); new = g['ISO'].iloc[0]; n = len(g)
        if cu.startswith('UNNAMED') or cu in ('', 'NAN', 'NONE'):
            log.issue('empty or unnamed country column', 'info', f'{which} file: "{code}" dropped ({n} rows)', n, iso=code)
        elif _AGGREGATE.match(cu):
            log.issue('aggregate or regional code', 'info', f'{which} file: "{code}" is a group, not a country; dropped ({n} rows)', n, iso=code)
        elif _SUFFIX.match(cu):
            log.issue('country appears twice in the file', 'review',
                      f'{which} file: "{code}" is a second column for {_SUFFIX.match(cu).group(1)}; dropped, check which column is right', n, iso=code)
        elif new is None or (isinstance(new, float) and np.isnan(new)):
            log.issue('country code not recognised', 'review', f'{which} file: "{code}" is not in the Geographic Reference sheet; rows set aside', n, iso=code)
        elif new != cu:
            how = 'name' if not re.fullmatch(r'[A-Z]{3}', cu) else 'code'
            log.map('country code', which, code, new, n, 'name in the code column' if how == 'name' else 'alias or code change (Geographic Reference sheet)')
            log.issue('country code converted', 'info', f'{which} file: {code} -> {new}', n, iso=new)
    return d[d['ISO'].notna()].copy()


def duplicate_countries(sim, cc, log, index_id=None):
    """One code written for two entities in the simulator file (CYP for Cyprus and for Northern Cyprus in the ISPAR
    WPF files). When the second entity's name has its own canonical code (Northern Cyprus = XNC), its rows are moved
    to that code, the change is logged and the file is flagged for correction. Otherwise the file is refused."""
    if 'Country' not in sim.columns:
        return sim
    sim = sim.copy()
    names = sim.dropna(subset=['Country']).groupby('ISO')['Country'].agg(lambda s: sorted(set(map(str, s))))
    for iso, ns in names.items():
        if len(ns) < 2:
            continue
        moved = {}
        for n in ns:
            target = _by_name(cc, n, index_id)
            if target and target != iso:
                rows = (sim.ISO == iso) & (sim.Country.astype(str) == n)
                sim.loc[rows, 'ISO'] = target
                log.map('country code', 'simulator', iso, target, int(rows.sum()), f'two entities under {iso}: rows named "{n}" moved to {target}')
                moved[n] = (target, int(rows.sum()))
        left = sorted(set(sim.loc[sim.ISO == iso, 'Country'].astype(str)))
        if len(left) <= 1 and moved:
            for n in ns:       # one line per entity, so the two are told apart
                if n in moved:
                    t, k = moved[n]
                    log.issue('one code for two entities', 'review',
                              f'{n}: written {iso} in the file, but {n} has its own code {t}. Moved to {t} here ({k} rows); correct the file at ingestion.', k, iso=t)
                else:
                    k = int(((sim.ISO == iso) & (sim.Country.astype(str) == n)).sum())
                    log.issue('one code for two entities', 'review',
                              f'{n}: written {iso}, which is its own code. Kept as {iso} ({k} rows).', k, iso=iso)
        else:
            log.issue('one code for two entities', 'refuse', f'{iso} is used for {", ".join(ns)} and no separate code is known. Correct the file.', len(ns), iso=iso)
    return sim


def duplicate_rows(sim, hist, log):
    collided = {i['ISO'] for i in log.issues if i['check'] == 'one code for two entities' and i['severity'] == 'refuse'}
    for (iso, kpi), g in sim[sim.duplicated(['ISO', 'KPI'], keep=False)].groupby(['ISO', 'KPI']):
        if iso in collided:
            continue
        vals = sorted(g['v'].dropna().unique().tolist())
        if len(vals) > 1:
            log.issue('duplicate row, different values (simulator)', 'refuse', f'{len(g)} rows; values {vals}', len(g), kpi, iso)
        else:
            log.issue('duplicate row, same value (simulator)', 'info', f'{len(g)} identical rows; one kept', len(g), kpi, iso)
    dh = hist[hist.duplicated(['ISO', 'KPI', 'year'], keep=False)]
    for kpi, g in dh.groupby('KPI'):
        differ = g.groupby(['ISO', 'year'])['h'].nunique() > 1
        n_c = int(g.ISO.nunique()); yrs = sorted(g['year'].dropna().astype(int).unique().tolist())
        names = sorted(set(map(str, g['KPI name'].dropna()))) if 'KPI name' in g.columns else []
        ex = g[g.set_index(['ISO', 'year']).index.isin(differ[differ].index)].head(2)
        exs = '; '.join(f"{r.ISO} {int(r.year)}: {r.h:g}" for r in ex.itertuples())
        if differ.any():
            for (iso, yr), gg in g[g.set_index(['ISO', 'year']).index.isin(differ[differ].index)].groupby(['ISO', 'year']):
                nms = gg['KPI name'].astype(str).tolist() if 'KPI name' in gg.columns else [''] * len(gg)
                parts = [f'{h:g}' + (f' ({n.strip()})' if n.strip() else '') for h, n in zip(gg['h'], nms)]
                log.issue('two series under one KPI ID (historical)', 'review',
                          f'{iso} {int(yr)}: {len(gg)} values under this KPI ID: ' + ' | '.join(parts) + '. Keep one series.', len(gg), kpi, iso)
        else:
            log.issue('duplicate year, same value (historical)', 'info', f'{n_c} countries, years {yrs[:4]}: identical copies, one kept', n_c, kpi)


# --------------------------------------------------------------------------- KPI traceability
def kpi_traceability(sim, hist, meta, canonical_kpis, log):
    sk = set(sim['KPI']); hk = set(hist['KPI'])
    mk = set(meta['KPI']) if meta is not None else None
    ck = set(map(clean_kpi_id, canonical_kpis)) if canonical_kpis is not None else None
    for k in sorted(sk - hk):
        log.issue('KPI in simulator, not in historical file', 'review', 'no source series to compare with', 1, k)
    for k in sorted(hk - sk):
        log.issue('KPI in historical file, not in simulator', 'info', 'series not used by the index', 1, k)
    if mk is not None:
        for k in sorted(sk - mk):
            log.issue('KPI not in metadata file', 'review', 'no definition, source or custodian recorded', 1, k)
        for k in sorted(mk - sk):
            log.issue('KPI in metadata, not in simulator', 'review', 'metadata describes a KPI the simulator does not hold', 1, k)
        d = meta[meta.duplicated('KPI', keep=False)]
        for k, g in d.groupby('KPI'):
            log.issue('KPI ID twice in metadata', 'review', f'{len(g)} rows', len(g), k)
    if ck is not None:
        for k in sorted(sk - ck):
            log.issue('KPI ID not in the canonical list', 'review', 'retired, renumbered or new ID: check against the canonical KeyID list', 1, k)
    # a KPI ID used with different names inside the simulator: possibly two series under one ID
    if 'KPI name' in sim.columns:
        nm = sim.dropna(subset=['KPI name']).groupby('KPI')['KPI name'].agg(lambda s: sorted(set(map(str, s))))
        for k, ns in nm.items():
            if len(ns) > 1:
                log.issue('one KPI ID, several names (simulator)', 'review', '; '.join(ns[:3]), len(ns), k)
    rows = []
    for k in sorted(sk | hk | (mk or set())):
        rows.append({'KPI': k, 'in_simulator': k in sk, 'in_historical': k in hk,
                     'in_metadata': (k in mk) if mk is not None else np.nan,
                     'in_canonical_list': (k in ck) if ck is not None else np.nan})
    return pd.DataFrame(rows)


def clean_ids(df, which, log):
    d = df.copy()
    d['KPI_original'] = d['KPI']
    d['KPI'] = d['KPI'].map(clean_kpi_id)
    ch = d[d['KPI'] != d['KPI_original'].astype(str)]
    for (a, b), g in ch.groupby(['KPI_original', 'KPI']):
        log.map('KPI ID', which, str(a), b, len(g), 'spaces or trailing .0 removed, or _FEMALE/_MALE written in lower case')
    bad = d[~d['KPI'].str.fullmatch(r'\d+(_(female|male))?', case=False)]
    for k, g in bad.groupby('KPI'):
        log.issue('KPI ID not valid', 'review', f'{which} file: "{k}" (expected a number, or a number followed by _female or _male)', len(g), k)
    return d[d['KPI'] != '']


# --------------------------------------------------------------------------- scale and units
def scale_factors(sim, hist, confirmed, p, log):
    """Power-of-ten factor between index value and source value, per KPI. Confirmed factors (metadata) win."""
    latest = hist.dropna(subset=['h']).sort_values('year').groupby(['KPI', 'ISO'], as_index=False).tail(1)
    out = {}
    for kpi, s in sim.groupby('KPI'):
        if confirmed and kpi in confirmed:
            out[kpi] = (float(confirmed[kpi]), 'confirmed in metadata'); continue
        j = s.merge(latest[latest.KPI == kpi][['ISO', 'h']], on='ISO')
        j = j[(j.v != 0) & (j.h != 0) & j.v.notna() & j.h.notna()]
        f = 1.0
        if len(j) >= p['scale_min_n']:
            r = np.log10(np.abs(j.v / j.h))
            k = int(np.round(np.median(r)))
            if k != 0 and np.mean(np.abs(r - k) < np.log10(1 + p['scale_tol'])) >= p['scale_share']:
                f = 10.0 ** k
        out[kpi] = (f, 'detected' if f != 1 else 'none')
    for kpi, (f, how) in out.items():
        if f != 1:
            n = int((hist.KPI == kpi).sum())
            log.map('scale factor', 'historical', '1', f'{f:g}', n, f'index value = source value x {f:g} ({how})')
            if how == 'detected':
                log.issue('scale factor between files', 'review', f'index = source x {f:g}; applied in h_scaled; confirm in metadata', 1, kpi)
    return out


def match_share(sim, hist, p):
    """Share of countries whose index value is found in the historical file for some year, on h_scaled: exactly,
    after rounding both to the coarser precision of the two files, or within 1% (source revised since). A low share
    means the two files do not hold the same series for this KPI."""
    rows, detail = [], {}
    h = hist.dropna(subset=['h_scaled'])
    for kpi, s in sim.dropna(subset=['v']).groupby('KPI'):
        hk = h[h.KPI == kpi]
        j = s[['ISO', 'v']].merge(hk[['ISO', 'year', 'h_scaled']], on='ISO') if not hk.empty else pd.DataFrame()
        if j.empty:
            rows.append({'KPI': kpi, 'countries_comparable': 0, 'share_matched': np.nan}); continue
        ds = int(np.nanquantile(_decimals(s.v, p['max_decimals']), 0.9))
        dh = int(np.nanquantile(_decimals(hk.h_scaled, p['max_decimals']), 0.9))
        d = min(ds, dh)
        j['gap'] = np.where(j.v != 0, np.abs(j.h_scaled - j.v) / np.abs(j.v), np.where(j.h_scaled == 0, 0.0, np.inf))
        j['hit'] = np.isclose(j.h_scaled, j.v, rtol=0, atol=1e-9) | (np.round(j.h_scaled, d) == np.round(j.v, d)) | (j.gap <= p['rel_tol_any'])
        g = j.groupby('ISO').hit.any()
        rows.append({'KPI': kpi, 'countries_comparable': int(len(g)), 'share_matched': float(g.mean())})
        detail[kpi] = j
    return pd.DataFrame(rows, columns=['KPI', 'countries_comparable', 'share_matched']), detail


EXAMPLE_ISO = ['JOR', 'EGY', 'MAR', 'TUN', 'SAU', 'FRA', 'DEU', 'USA', 'BRA', 'IND']


def diagnose(kpi, j, sim_names, edition=None):
    """Plain-language reason why a KPI is not reconciled, with three country examples."""
    best = j.loc[j.groupby('ISO').gap.idxmin()]
    ymax = int(j.year.max())
    med = float(np.median(best.gap[np.isfinite(best.gap)])) if np.isfinite(best.gap).any() else np.inf
    r = (best.v / best.h_scaled).replace([np.inf, -np.inf], np.nan).dropna()
    rmed = float(r.median()) if len(r) else np.nan
    rspread = float((r.quantile(.75) - r.quantile(.25)) / abs(rmed)) if len(r) >= 5 and rmed else np.inf
    ex = best[best.ISO.isin(EXAMPLE_ISO)].head(3)
    if len(ex) < 3:
        ex = pd.concat([ex, best[~best.ISO.isin(ex.ISO)].head(3 - len(ex))])
    exs = '; '.join(f'{q.ISO}: index {q.v:.4g}, closest source value {q.h_scaled:.4g} ({int(q.year)})' for q in ex.itertuples())
    if edition is not None and ymax < int(edition) - 3:
        why = (f'The historical file stops in {ymax}, while the index edition is {edition}. '
               'The historical file is probably an older edition of the source: update it.')
        kind = 'historical file too old'
    elif np.isfinite(rspread) and rspread < 0.03 and abs(rmed - 1) > 0.03:
        why = (f'Index values are about {rmed:.3g} times the source values for most countries. '
               'The index and the historical file measure the same thing in different units or on a different base '
               '(for example per 100 vs per 1,000, or a share vs a percentage of another total). Confirm the conversion in the metadata.')
        kind = 'constant ratio (unit or base)'
    elif med < 0.05:
        why = (f'Index values are close to the source but not equal (typical gap {med:.1%}). '
               'The publisher used another release of the same series, revised since, or a slightly different definition '
               '(age group, sex, reference year). The historical file may need the release the publisher used.')
        kind = 'close but not equal (revision or definition)'
    else:
        why = (f'Index values are far from the source values (typical gap {med:.0%}). '
               'The historical file probably holds another series than the one the publisher used, or the publisher '
               'transformed the data (average of years, imputation, rescaling). Check the KPI name and source in the metadata.')
        kind = 'different series'
    return kind, f'{why} Examples: {exs}.'


# --------------------------------------------------------------------------- run
def run(sim, hist, meta=None, index_id=None, edition=None, canonical_kpis=None, confirmed_scale=None,
        codes=None, params=None, hist_edition=None, uce_meta=None, hist_previous=None):
    """Run all checks on one index and edition. See the module docstring for the contract."""
    p = {**PARAMS, **(params or {})}
    cc = codes or CountryCodes.from_reference()
    log = _Log()
    idx = None if index_id is None else str(index_id)

    sim, hist = sim.copy(), hist.copy()
    for d, col, which in ((sim, 'v', 'simulator'), (hist, 'h', 'historical')):
        num = pd.to_numeric(d[col], errors='coerce')
        bad = d[num.isna() & d[col].notna() & (d[col].astype(str).str.strip() != '')]
        if len(bad):
            vals = sorted(set(bad[col].astype(str)))[:5]
            log.issue('value not numeric', 'review', f'{which} file: {len(bad)} cells hold text such as {vals}; read as missing', len(bad))
        d[col] = num
    sim = clean_ids(sim, 'simulator', log)
    hist = clean_ids(hist, 'historical', log)
    if hist_previous is not None:
        hist_previous = reconcile_codes(clean_ids(hist_previous, 'previous historical', _Log()), 'previous historical', cc, idx, _Log())
    if meta is not None:
        meta = clean_ids(meta, 'metadata', log)

    sim = reconcile_codes(sim, 'simulator', cc, idx, log)
    hist = reconcile_codes(hist, 'historical', cc, idx, log)
    sim = duplicate_countries(sim, cc, log, idx)
    duplicate_rows(sim, hist, log)
    sim = sim.drop_duplicates(['ISO', 'KPI', 'v'])
    hist = hist.drop_duplicates(['ISO', 'KPI', 'year', 'h'])

    kp = kpi_traceability(sim, hist, meta, canonical_kpis, log)
    uce_ind = (uce_meta or {}).get('indicators')
    if uce_ind is not None:
        uk = set(uce_ind.KeyID.map(clean_kpi_id))
        for k in sorted(set(sim.KPI) - uk):
            log.issue('KPI not in the UCE metadata', 'review', 'the KPI has no row in the indicators sheet of the UCE / Generator metadata', 1, k)
        for k in sorted({x for x in uk if re.fullmatch(r'\d+(_(female|male))?', x)} - set(sim.KPI)):
            log.issue('KPI in the UCE metadata, not in the simulator', 'review', 'the UCE / Generator metadata lists this KPI; the simulator has no value for it', 1, k)

    fac = scale_factors(sim, hist, confirmed_scale, p, log)
    hist = hist.copy()
    hist['scale_factor'] = hist['KPI'].map(lambda k: fac.get(k, (1.0, 'none'))[0])
    hist['h_scaled'] = hist['h'] * hist['scale_factor']
    ms, det = match_share(sim, hist, p)
    kp = kp.merge(pd.DataFrame([{'KPI': k, 'scale_factor': f, 'scale_basis': b} for k, (f, b) in fac.items()]), on='KPI', how='left')
    kp = kp.merge(ms, on='KPI', how='left')
    kp['diagnosis'] = ''
    names = sim.dropna(subset=['KPI name']).groupby('KPI')['KPI name'].first() if 'KPI name' in sim.columns else pd.Series(dtype=str)
    for q in kp[(kp.countries_comparable >= p['scale_min_n']) & (kp.share_matched < p['match_min_share'])].itertuples():
        kind, text = diagnose(q.KPI, det[q.KPI], names, edition)
        kp.loc[kp.KPI == q.KPI, 'diagnosis'] = kind
        nm = f' ({names.get(q.KPI)})' if q.KPI in names.index else ''
        log.issue('KPI not reconciled', 'review',
                  f'{nm.strip(" ()") or "KPI"}: the index value is found in the historical file for {q.share_matched:.0%} of the {q.countries_comparable} '
                  f'countries that have both. Diagnosis: {kind}. {text}', 1, q.KPI)
    from . import crosschecks as X
    X.value_from_another_country(sim, hist, log, p)
    X.swapped_kpis(sim, hist, kp, log, p)
    X.unit_for_some_countries(sim, hist, fac, log, p)
    X.shifted_years(sim, hist, hist_previous, edition, log, p)
    if uce_meta is not None and uce_meta.get('country') is not None:
        X.publisher_country_list(sim, cc, uce_meta['country'], idx, log)
    # countries in the historical file but not in the index: not covered by the publisher (information only;
    # countries with index values but no history are a Data Quality Profile bucket, not a precheck item)
    in_index = set(sim.loc[sim.v.notna(), 'ISO'])
    for c in sorted(set(hist.ISO) - in_index):
        log.issue('country in historical file, not in the index', 'info',
                  ('ESCWA member. ' if c in ESCWA else '') + f'{c} has historical data but no index value: not covered by this edition', 1, iso=c)

    if edition is not None and hist_edition is not None and int(hist_edition) != int(edition):
        log.issue('simulator and historical file from different editions', 'review',
                  f'simulator file is edition {edition}, historical file is labelled {hist_edition}: check that both belong to the same edition', 1)
    if edition is not None and not hist.empty:
        late = hist[hist.year > int(edition)]
        if len(late):
            log.issue('source years after the index edition', 'info',
                      f'{len(late)} values dated after {edition}; they must not be used to call the index value old', len(late))

    present = set(sim.loc[sim.v.notna(), 'ISO'])
    cov = pd.DataFrame({'ISO': ESCWA, 'in_simulator': [c in present for c in ESCWA]})

    issues = pd.DataFrame(log.issues, columns=COLS_ISSUES)
    status = 'refuse' if (issues.severity == 'refuse').any() else ('review' if (issues.severity == 'review').any() else 'pass')
    return Result(status=status, sim=sim.reset_index(drop=True), hist=hist.reset_index(drop=True), issues=issues,
                  mappings=pd.DataFrame(log.maps, columns=COLS_MAP), kpis=kp, coverage=cov,
                  meta={'index_id': idx, 'edition': edition, 'params': p})
