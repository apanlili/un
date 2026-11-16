"""Checks that compare values across countries, KPIs, years and reference files. Each rule is deterministic and
stated in plain words in its docstring, so that a person can verify any flag by hand.

All functions take the cleaned tables of checks.run (sim: ISO, KPI, v; hist: ISO, KPI, year, h, h_scaled) and a log.
"""
import re
import numpy as np
import pandas as pd


def _dec(x, maxd=6):
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    for d in range(maxd + 1):
        hit = ok & np.isnan(out) & (np.abs(x * 10 ** d - np.round(x * 10 ** d)) < 1e-6)
        out[hit] = d
    out[ok & np.isnan(out)] = maxd
    return out


def _categorical(v, p):
    v = pd.Series(v).dropna()
    return len(v) == 0 or (bool(np.all(np.abs(v - np.round(v)) < 1e-9)) and v.nunique() <= p['cat_max_levels'])


def _found(v, series, d, tol=0.01):
    """v found in a country's source series: exact, equal after rounding to d decimals, or within tol (relative)."""
    s = np.asarray(series, dtype=float)
    if not len(s) or not np.isfinite(v):
        return False
    if np.any(np.round(s, d) == round(v, d)):
        return True
    return v != 0 and np.any(np.abs(s - v) <= tol * abs(v))


def _modal_year(s, hk, d):
    """Most frequent year at which countries' index values equal their own source values (exact or rounded)."""
    j = s[['ISO', 'v']].merge(hk[['ISO', 'year', 'h_scaled']], on='ISO')
    j = j[np.round(j.h_scaled, d) == np.round(j.v, d)]
    if j.empty:
        return None
    return int(j.groupby('ISO').year.max().mode().iloc[0])


def _sig(v):
    """Number of significant digits of a value as written (0.0225 -> 3, 7.9 -> 2)."""
    t = f'{abs(v):.10g}'.replace('.', '').lstrip('0')
    return len(t.rstrip('0')) if '.' in f'{abs(v):.10g}' else len(t)


def _simple_fraction(v):
    """Values such as 33.3333 (1/3), 1.875 (15/8) or 46.25 recur across countries by construction (scores on small
    integer scales), so an equality between two countries proves nothing."""
    return any(abs(v * k - round(v * k)) < 1e-3 for k in (1, 2, 3, 4, 6, 8))


def value_from_another_country(sim, hist, log, p):
    """Rule: country A's index value is not found in A's own source series (any year, exact, rounded or within 1%),
    but equals exactly (after rounding to the index precision) the source value of ONE other country B, at the year
    most countries are on. A is then flagged when the evidence cannot be chance:
      - the value has at least 4 significant digits and is not a simple fraction (1/3, 15/8 ...), or
      - the same pair (A takes B's value) occurs in at least two KPIs of the index.
    Rows shifted: when at least 5 countries, and at least half of the countries not found in their own series, carry
    the value of the country next to them in the file, the KPI is flagged once as 'rows shifted'."""
    h = hist.dropna(subset=['h_scaled'])
    order = {c: i for i, c in enumerate(sim.drop_duplicates('ISO').ISO)}
    all_cand = []
    for kpi, s in sim.dropna(subset=['v']).groupby('KPI'):
        hk = h[h.KPI == kpi]
        if hk.empty or _categorical(s.v, p):
            continue
        d = int(np.nanquantile(_dec(s.v), 0.9))
        if d < 1:
            continue
        by_c = {c: g.h_scaled.values for c, g in hk.groupby('ISO')}
        own = {r.ISO: _found(r.v, by_c.get(r.ISO, []), d) for r in s.itertuples()}
        ym = _modal_year(s, hk, d)
        if ym is None:
            continue
        at = hk[hk.year == ym]
        index = {}
        for c, x in zip(at.ISO, np.round(at.h_scaled, d)):
            index.setdefault(x, set()).add(c)
        vals = dict(zip(s.ISO, s.v))
        cand = []
        for a_, v in vals.items():
            if own.get(a_) or a_ not in by_c:
                continue
            others = index.get(round(v, d), set()) - {a_}
            if len(others) == 1:
                b_ = next(iter(others))
                cand.append((kpi, a_, b_, v, ym, bool(own.get(b_))))
        not_own = sum(1 for c in vals if c in by_c and not own.get(c))
        neigh = [x for x in cand if abs(order.get(x[1], -9) - order.get(x[2], 99)) == 1]
        if len(neigh) >= 5 and len(neigh) >= 0.5 * not_own:
            log.issue('rows shifted', 'review',
                      f'{len(neigh)} countries carry the source value of the country next to them in the file '
                      f'(e.g. {", ".join(f"{x[1]} has the value of {x[2]}" for x in neigh[:3])}): the rows of this KPI are probably shifted.',
                      len(neigh), kpi)
            continue
        all_cand += cand
    pair_n = {}
    for x in all_cand:
        pair_n[(x[1], x[2])] = pair_n.get((x[1], x[2]), 0) + 1
    for kpi, a_, b_, v, ym, b_ok in all_cand:
        strong = (_sig(v) >= 4 and not _simple_fraction(v) and b_ok) or pair_n[(a_, b_)] >= 2
        if strong:
            also = f' The same happens in {pair_n[(a_, b_)] - 1} other KPI(s) of this index.' if pair_n[(a_, b_)] >= 2 else ''
            log.issue('value matches another country', 'review',
                      f'{a_}: index value {v:g} is not in the source series of {a_} but equals the source value of {b_} for {ym}.{also} '
                      f'Check whether the value of {a_} was copied from the row of {b_}.', 1, kpi, a_)


def swapped_kpis(sim, hist, kp, log, p):
    """Rule: for a KPI whose index values are found in its own historical series for fewer than half of the
    countries, test the historical series of every other KPI of the index. If another KPI's series contains the
    index values for at least half of the countries, the series is loaded under the wrong ID. The result says:
      - "swapped" when A's values are under B and B's values under A;
      - "shifted" when three KPIs or more each find their values under the next (or previous) KeyID, in the same
        direction (series moved by one ID);
      - otherwise, that the series loaded under A is probably the wrong one."""
    h = hist.dropna(subset=['h_scaled'])
    weak = kp[(kp.countries_comparable >= p['scale_min_n']) & (kp.share_matched < p['match_min_share'])].KPI.tolist()
    if not weak:
        return
    series = {k: {c: g.h_scaled.values for c, g in hk.groupby('ISO')} for k, hk in h.groupby('KPI')}
    def _key(k):
        m = re.match(r'(\d+)(.*)', str(k))
        return (int(m.group(1)), m.group(2)) if m else (10 ** 12, str(k))
    order = sorted(set(hist.KPI.tolist()), key=_key)          # KPIs in KeyID order
    pos = {k: i for i, k in enumerate(order)}
    found = {}
    for a in weak:
        s = sim[(sim.KPI == a) & sim.v.notna()]
        if s.empty:
            continue
        d = int(np.nanquantile(_dec(s.v), 0.9))
        best = (0, None, 0)
        for b, by_c in series.items():
            if b == a:
                continue
            comp = [(r.v, by_c[r.ISO]) for r in s.itertuples() if r.ISO in by_c]
            if len(comp) < p['scale_min_n']:
                continue
            share = np.mean([_found(v, ser, d, 0) for v, ser in comp])
            if share > best[0]:
                best = (share, b, len(comp))
        if best[1] is not None and best[0] >= p['match_min_share']:
            found[a] = best
    steps = [pos[b] - pos[a] for a, (_, b, _) in found.items() if a in pos and b in pos]
    shift = None
    if len(steps) >= 3:
        st = pd.Series(steps).mode().iloc[0]
        if abs(st) == 1 and (pd.Series(steps) == st).sum() >= 3:
            shift = st
    for a, (share, b, n) in found.items():
        txt = f'The index values of KPI {a} are found in the historical series of KPI {b} for {share:.0%} of {n} countries. '
        if found.get(b, (0, None))[1] == a:
            txt += 'The reverse is also true: the two IDs are probably swapped.'
        elif shift is not None and a in pos and b in pos and pos[b] - pos[a] == shift:
            txt += ('Several KPIs show the same pattern with the next KeyID: the series are probably '
                    'shifted by one KeyID in the historical file (one series missing or repeated).')
        else:
            txt += f'The series loaded under KPI {a} is probably the wrong one.'
        log.issue('KPI values match another KPI', 'review', txt, 1, a)


def unit_for_some_countries(sim, hist, fac, log, p):
    """Rule: in a KPI with no global power-of-ten factor, a country whose index value equals its source value times
    100 or divided by 100 (within 0.5%, within one year of the year most countries are on) while most countries match without factor: the unit of
    that country's value differs (share vs percentage)."""
    h = hist.dropna(subset=['h'])
    for kpi, s in sim.dropna(subset=['v']).groupby('KPI'):
        if fac.get(kpi, (1.0,))[0] != 1.0:
            continue
        hk = h[h.KPI == kpi]
        if hk.empty or _categorical(s.v, p):
            continue
        j = s[['ISO', 'v']].merge(hk[['ISO', 'year', 'h']], on='ISO')
        j = j[(j.v != 0) & (j.h != 0)]
        if j.empty:
            continue
        j['r'] = j.v / j.h
        plain = j.groupby('ISO').r.apply(lambda r: bool(np.any(np.abs(r - 1) <= 0.01))).mean()
        if plain < 0.5:
            continue
        for c, g in j.groupby('ISO'):
            if np.any(np.abs(g.r - 1) <= 0.01):
                continue
            ym = j.loc[np.abs(j.r - 1) <= 0.01].groupby('ISO').year.max().mode()
            ym = int(ym.iloc[0]) if len(ym) else None
            gg = g if ym is None else g[(g.year - ym).abs() <= 1]
            for f in (100.0, 0.01):
                hit = gg[np.abs(gg.r / f - 1) <= 0.005]
                if len(hit):
                    q = hit.iloc[0]
                    log.issue('unit differs for one country', 'review',
                              f'{c}: index value {q.v:g} = source value {q.h:g} ({int(q.year)}) x {f:g}, while most countries match '
                              f'without factor: share and percentage mixed for this country.', 1, kpi, c)
                    break


def shifted_years(sim, hist, hist_previous, edition, log, p):
    """Two rules.
    (1) Within one edition: the year at which the index values are found in the source, taken as the most frequent
        year across countries, cannot be later than the edition year (and is usually one or more years before). A
        modal matched year equal to or after the edition year suggests the historical file's year labels are shifted
        forward.
    (2) Against the previous historical file (when given): for countries whose source values appear in both files,
        if the same values carry year Y in the previous file and Y+k in the current one for most countries (k the
        same, not 0), the year labels moved by k between the two files."""
    h = hist.dropna(subset=['h_scaled'])
    if edition is not None:
        for kpi, s in sim.dropna(subset=['v']).groupby('KPI'):
            hk = h[h.KPI == kpi]
            if hk.empty:
                continue
            d = int(np.nanquantile(_dec(s.v), 0.9))
            j = s[['ISO', 'v']].merge(hk[['ISO', 'year', 'h_scaled']], on='ISO')
            if j.empty:
                continue
            j = j[np.round(j.h_scaled, d) == np.round(j.v, d)]
            if len(j) < p['scale_min_n']:
                continue
            yr = int(j.groupby('ISO').year.max().mode().iloc[0])
            if yr > int(edition):
                log.issue('year labels possibly shifted', 'review',
                          f'The index values are found in the source mostly at year {yr}, after the edition year ({edition}). '
                          f'An edition cannot use data dated after it: check the year labels of the historical file.', 1, kpi)
    if hist_previous is not None and len(hist_previous):
        prev = hist_previous.dropna(subset=['h'])
        for kpi, hk in h.groupby('KPI'):
            pk = prev[prev.KPI == kpi]
            if pk.empty or _categorical(hk.h, p):
                continue
            m = hk[['ISO', 'year', 'h']].merge(pk[['ISO', 'year', 'h']], on=['ISO', 'h'], suffixes=('', '_prev'))
            m = m[m.h != 0]
            if len(m) < 3 * p['scale_min_n']:
                continue
            k = (m.year - m.year_prev)
            top = k.mode().iloc[0]
            share = (k == top).mean()
            if top != 0 and share >= 0.6:
                log.issue('year labels shifted between historical files', 'review',
                          f'{share:.0%} of the values found in both files carry year Y in the previous historical file and Y{top:+d} '
                          f'in this one (e.g. {m.iloc[0].ISO}: {m.iloc[0].h:g} labelled {int(m.iloc[0].year_prev)} then {int(m.iloc[0].year)}).', 1, kpi)


def publisher_country_list(sim, cc, uce_countries, index_id, log):
    """Rule: the countries in the simulator must be the countries of the publisher's ranking for this edition, as
    listed in the UCE / Generator metadata (sheet country). Reported both ways: in the publisher list but missing from
    the simulator (lost at ingestion), in the simulator but not in the publisher list."""
    pub = {cc.canonical(str(c), index_id=index_id) for c in uce_countries if isinstance(c, str) and c.strip()}
    simc = set(sim.loc[sim.v.notna(), 'ISO'])
    for c in sorted(pub - simc):
        log.issue('country ranked by the publisher, missing from the simulator', 'review',
                  f'{c} is in the publisher country list of the metadata but has no value in the simulator', 1, iso=c)
    for c in sorted(simc - pub):
        log.issue('country in the simulator, not in the publisher list', 'review',
                  f'{c} has values in the simulator but is not in the publisher country list of the metadata', 1, iso=c)
