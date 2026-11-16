"""Read the ISPAR input files directly into the long tables used by checks.run.

Simulator file (raw_<INDEX>_<YEAR>.xlsx, the layout read by the Data Quality Profile code):
  row 1: Country, ISO, [Region, Sub-region, Income Type, ...], then one column per KPI ID
  row 2: KPI names under the KPI ID columns
  rows 3+: one row per country
Historical file (historical data_index_<ID>_..., M&J layout):
  row 1: ISO codes above the country columns
  row 2: KeyID, Series name, year, then country names
  rows 3+: one row per KPI and year
UCE / Generator metadata (metadata_<INDEX>_<YEAR>.xlsx): sheets indicators, structure, country.
"""
import re
import pandas as pd

ID_COLS = {'country', 'iso', 'region', 'sub-region', 'subregion', 'income type', 'income group', 'group', 'rank', 'score'}


def read_simulator(path, sheet=0):
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    head, names = raw.iloc[0].tolist(), raw.iloc[1].tolist()
    body = raw.iloc[2:].reset_index(drop=True)
    ci = next(i for i, h in enumerate(head) if str(h).strip().lower() == 'country')
    ii = next(i for i, h in enumerate(head) if str(h).strip().lower() == 'iso')
    rows = []
    for j, h in enumerate(head):
        if h is None or (isinstance(h, float) and pd.isna(h)) or str(h).strip().lower() in ID_COLS:
            continue
        for c, iso, v in zip(body[ci], body[ii], body[j]):
            if (isinstance(iso, float) and pd.isna(iso)) and (isinstance(c, float) and pd.isna(c)):
                continue
            rows.append({'ISO': iso, 'Country': c, 'KPI': h, 'KPI name': names[j], 'v': v})
    return pd.DataFrame(rows)


ISO3 = re.compile(r'^[A-Z]{3}$')


def _is_code(v):
    return isinstance(v, str) and bool(ISO3.match(v.strip()))


def normalise_historical_grid(raw):
    """Bring a historical file (read with header=None) to one layout: row 1 = ISO codes, row 2 = KeyID, Series name,
    year, country names; then one row per KPI and year. Returns (grid, notes). Each change is stated in notes:
      - rows 1 and 2 swapped when the codes are in row 2 (both layouts exist on Drive);
      - identifier columns other than KeyID, Series name and year (e.g. 'category') removed;
      - header spellings unified (KeyId, Year, 'year ');
      - when one KeyID holds both a female and a male series, the sex being written only in the series name ('- Female',
        ', male', '_female'), _female or _male is added to the KeyID. Separate numeric KeyIDs are left as they are."""
    g = raw.copy().reset_index(drop=True)
    notes = []
    lower = [str(h).strip().lower() for h in g.iloc[1].tolist()]
    ki = next(i for i, h in enumerate(lower) if h in ('keyid', 'kpi id', 'kpi_id'))
    ni = next((i for i, h in enumerate(lower) if h.startswith('series')), None)
    yi = next(i for i, h in enumerate(lower) if h == 'year')
    idc = {ki, yi} | ({ni} if ni is not None else set())
    first = max(idc) + 1
    extra = [j for j in range(first) if j not in idc]
    if extra:
        notes.append(f'identifier column(s) {", ".join(repr(g.iat[1, j]) for j in extra)} removed (not used: the layout is KeyID, Series name, year)')
    cols = [ki] + ([ni] if ni is not None else []) + [yi] + list(range(first, g.shape[1]))
    g = g.iloc[:, cols].copy(); g.columns = range(g.shape[1])
    nid = 3 if ni is not None else 2
    r0 = g.iloc[0, nid:].tolist(); r1 = g.iloc[1, nid:].tolist()
    if sum(map(_is_code, r1)) > sum(map(_is_code, r0)):
        g.iloc[0, nid:], g.iloc[1, nid:] = r1, r0
        notes.append('ISO codes were in row 2 and country names in row 1; rows swapped (codes must be in row 1)')
    want = ['KeyID', 'Series name', 'year'] if ni is not None else ['KeyID', 'year']
    if [str(x).strip() for x in g.iloc[1, :nid]] != want:
        notes.append(f'header {[g.iat[1, j] for j in range(nid)]} written as {want}')
    for j, w in enumerate(want):
        g.iat[1, j] = w; g.iat[0, j] = None
    if ni is not None:
        sex = {}
        for r in range(2, len(g)):
            w = {x.lower() for x in re.findall(r'(?:\b|_)(female|male)\b', str(g.iat[r, 1]), re.I)}
            sex[r] = w.pop() if len(w) == 1 else None
        by_id = {}
        for r in range(2, len(g)):
            by_id.setdefault(str(g.iat[r, 0]).strip(), []).append(r)
        n_fix = 0
        for k, rows in by_id.items():
            got = {sex[r] for r in rows}
            if got == {'female', 'male'} and not re.search(r'_(female|male)$', k, re.I):   # both sexes under one ID
                kk = k[:-2] if k.endswith('.0') else k
                for r in rows:
                    g.iat[r, 0] = f'{kk}_{sex[r]}'; n_fix += 1
        if n_fix:
            notes.append(f'{n_fix} rows: a female and a male series under the same KeyID (sex written only in the series '
                         f'name); _female or _male added to the KeyID')
    return g, notes


def read_historical(path, sheet=0, notes=None):
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    g, nt = normalise_historical_grid(raw)
    if notes is not None:
        notes.extend(nt)
    isos = g.iloc[0].tolist()
    nid = 3 if str(g.iat[1, 1]).strip() == 'Series name' else 2
    body = g.iloc[2:].reset_index(drop=True)
    rows = []
    for j in range(nid, g.shape[1]):
        iso = isos[j]
        if iso is None or (isinstance(iso, float) and pd.isna(iso)):
            iso = g.iat[1, j]                  # no code above: the name stands in the code row
        names = body[1] if nid == 3 else [None] * len(body)
        for k, nm, y, h in zip(body[0], names, body[nid - 1], body[j]):
            if h is None or (isinstance(h, float) and pd.isna(h)) or str(h).strip() == '':
                continue
            rows.append({'ISO': iso, 'KPI': k, 'KPI name': nm, 'year': pd.to_numeric(y, errors='coerce'), 'h': h})
    return pd.DataFrame(rows)


def write_historical_layout(path, out):
    """Write a copy of a historical file in the single layout (for code that reads row 1 as ISO codes)."""
    raw = pd.read_excel(path, header=None, dtype=object)
    g, notes = normalise_historical_grid(raw)
    g.to_excel(out, header=False, index=False)
    return notes


def read_uce_metadata(path):
    x = pd.ExcelFile(path)
    out = {}
    if 'indicators' in x.sheet_names:
        out['indicators'] = pd.read_excel(x, 'indicators')
    if 'country' in x.sheet_names:
        c = pd.read_excel(x, 'country')
        col = next((k for k in c.columns if str(k).strip().upper() == 'ISO'), None)
        out['country'] = c[col].dropna().astype(str).tolist() if col else None
    return out


def edition_from_name(name):
    m = re.findall(r'(20\d\d)', re.sub(r'^\d{8}_', '', str(name)))
    return int(m[-1]) if m else None
