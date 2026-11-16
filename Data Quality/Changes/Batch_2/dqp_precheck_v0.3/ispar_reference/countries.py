"""Country codes: publishers and files do not all use ISO 3166-1 alpha-3, and some codes changed over time.

The authority is the Google Sheet "ISPAR Geographic Reference & Publisher Mappings" (Drive, owner: Nathalie):
  * CANONICAL_ENTITIES: the canonical codes (ISO 3166-1 alpha-3, plus the approved non-ISO codes XKX, XOE, XNC, CHI);
  * PUBLISHER_ALIASES: for each publisher, index and vintage, the code (or name) the publisher's file uses and the
    canonical code it stands for.

Load it with CountryCodes.from_reference(path): path is the sheet exported as .xlsx (File > Download > Microsoft
Excel), or the PUBLISHER_ALIASES sheet exported as .csv (then the canonical codes come from the snapshot shipped
in reference/). Snapshots of the three sheets taken on 23 October 2026 are in reference/ and are used by default.

The sheet is a general reconciliation table used across indices (README, "Scope of aliases", 17 October 2026).
Rules applied:
  * every alias code (ZAR, ROM, TMP, WBG, KSV, KOS, CSS, CTU, PES, TZN) maps to its canonical code in every file;
  * official code changes over time (sheet CODE_HISTORY: BUR, ZAR, TMP, ROM ...) map to the current code when the
    country has a single successor; splits (USSR, Czechoslovakia, Serbia and Montenegro ...) are not mapped;
  * a row whose observed code is itself a canonical code (CYP written for Northern Cyprus in the WPF 2025 and 2026
    files) is not an alias: it records a duplicate code in a publisher file. Duplicates are not resolved here: a file
    in which one code appears twice is refused (Workspace), and the file is corrected at ingestion (Northern Cyprus
    = XNC), as the identity gate of the sheet's README requires;
  * a file that gives names only is matched by the names listed in the sheet;
  * never invent a code: an unknown code is returned unchanged and reported by resolve() as absent.
"""
import csv
import re
from pathlib import Path

REF_DIR = Path(__file__).resolve().parent.parent / 'reference'
ALIASES_SNAPSHOT = REF_DIR / 'PUBLISHER_ALIASES_snapshot_2026-10-23.csv'
CANONICAL_SNAPSHOT = REF_DIR / 'CANONICAL_ENTITIES_codes_snapshot_2026-10-23.csv'
HISTORY_SNAPSHOT = REF_DIR / 'CODE_HISTORY_snapshot_2026-10-23.csv'

# Used only when no reference is available (same content as the sheet on 16 October 2026, plus codes met in files)
FALLBACK_ALIASES = {'ZAR': 'COD', 'ROM': 'ROU', 'TMP': 'TLS', 'WBG': 'PSE', 'KSV': 'XKX', 'KOS': 'XKX',
                    'CSS': 'XOE', 'CTU': 'XNC', 'PES': 'PSE', 'TZN': 'TZA'}
# Codes not yet in the reference sheet (none since 17 October 2026: PES, TZN and KOS were added)
NOT_YET_LISTED = {}
NON_ISO = {'XKX': 'Kosovo', 'XNC': 'Northern Cyprus', 'XOE': 'OECS', 'CHI': 'Channel Islands'}


def _norm_name(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def _read_rows(path, sheet=None):
    path = Path(path)
    if path.suffix.lower() in ('.xlsx', '.xlsm'):
        import pandas as pd
        d = pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False)
        return d.to_dict('records')
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


class CountryCodes:
    def __init__(self, alias_rows=None, canonical=None, extra_aliases=None):
        self.canonical_codes = set(canonical or [])
        self.aliases = {}           # code -> canonical, valid everywhere
        self.duplicates = []        # rows recording a canonical code used for another entity (not aliases)
        self.scoped = {}            # (index_id, code) -> canonical: aliases valid only in one publisher's files
        self.names = {}             # normalised name -> canonical (files without codes)
        self.scoped_names = {}      # (index_id, normalised name) -> canonical: names valid only in one publisher's files
        self.rows = alias_rows or []
        if not alias_rows:
            self.aliases.update(FALLBACK_ALIASES)
        for r in self.rows:
            can = (r.get('canonical_code') or '').strip().upper()
            if not can:
                continue
            name = (r.get('publisher_entity_name') or '').strip()
            if name:
                if str(r.get('alias_scope', '')).strip().lower() == 'publisher':
                    self.scoped_names[(str(r.get('index_id', '')).strip(), _norm_name(name))] = can
                else:
                    self.names[_norm_name(name)] = can
            obs = (r.get('simulator_identifier_observed') or '').strip()
            for code in [c.strip().upper() for c in obs.split('/')]:
                if not re.fullmatch(r'[A-Z]{3}', code) or code == can:
                    continue
                if str(r.get('alias_scope', '')).strip().lower() == 'publisher':
                    self.scoped[(str(r.get('index_id', '')).strip(), code)] = can
                    continue
                if code in self.canonical_codes:
                    self.duplicates.append({'code': code, 'canonical': can, 'index_id': r.get('index_id'), 'vintage': r.get('vintage'),
                                            'entity': name})
                else:
                    self.aliases[code] = can
        if extra_aliases:
            self.aliases.update({k.upper(): v.upper() for k, v in extra_aliases.items()})

    # ---------------------------------------------------------------- loading
    @classmethod
    def from_reference(cls, path=None, canonical_path=None):
        """path: the Geographic Reference sheet as .xlsx, or PUBLISHER_ALIASES as .csv. None = shipped snapshots."""
        path = Path(path) if path else ALIASES_SNAPSHOT
        if path.suffix.lower() in ('.xlsx', '.xlsm'):
            rows = _read_rows(path, 'PUBLISHER_ALIASES')
            canon = [r['canonical_code'].strip().upper() for r in _read_rows(path, 'CANONICAL_ENTITIES') if r.get('canonical_code')]
            try:
                hist = _read_rows(path, 'CODE_HISTORY')
            except Exception:
                hist = []
        else:
            rows = _read_rows(path)
            canon = [r['canonical_code'].strip().upper() for r in _read_rows(canonical_path or CANONICAL_SNAPSHOT)]
            hist = _read_rows(HISTORY_SNAPSHOT) if HISTORY_SNAPSHOT.exists() else []
        # code changes over time: an old code maps to its current code when there is one successor (renamed or recoded)
        extra = dict(NOT_YET_LISTED)
        olds = [(h.get('old_code') or '').strip().upper() for h in hist]
        for h in hist:
            old, new = (h.get('old_code') or '').strip().upper(), (h.get('current_code') or '').strip().upper()
            if str(h.get('scope', 'all')).strip().lower() == 'publisher' or olds.count(old) > 1:
                continue            # publisher-scoped (CSS) or a split: never a general alias
            if re.fullmatch(r'[A-Z]{3}', old) and re.fullmatch(r'[A-Z]{3}', new) and old not in canon:
                extra[old] = new
        extra.pop('YUG', None)      # Serbia and Montenegro itself split: no single current code
        return cls(rows, canon, extra_aliases=extra)

    @classmethod
    def from_file(cls, path):
        """Simple two-column CSV (code, iso) added on top of the shipped reference."""
        al = {}
        for row in _read_rows(path):
            c, i = (row.get('code') or '').strip(), (row.get('iso') or '').strip()
            if c and i:
                al[c] = i
        base = cls.from_reference()
        base.aliases.update({k.upper(): v.upper() for k, v in al.items()})
        return base

    # ---------------------------------------------------------------- use
    def canonical(self, code, name=None, index_id=None):
        c = '' if code is None else str(code).strip().upper()
        if not c and name:
            if index_id is not None and (str(index_id), _norm_name(name)) in self.scoped_names:
                return self.scoped_names[(str(index_id), _norm_name(name))]
            return self.names.get(_norm_name(name), '')
        if index_id is not None and (str(index_id), c) in self.scoped:
            return self.scoped[(str(index_id), c)]
        return self.aliases.get(c, c)

    @staticmethod
    def duplicated(codes):
        """Codes that appear more than once in a file (to be corrected at ingestion before any comparison)."""
        s = [str(c).strip().upper() for c in codes if c is not None and str(c).strip()]
        return sorted({c for c in s if s.count(c) > 1})

    def is_known(self, code):
        return (not self.canonical_codes) or self.canonical(code) in self.canonical_codes

    def resolve(self, code, available):
        """The code used in `available` (e.g. the engine's data) for the country `code`, or None if absent."""
        target = self.canonical(code)
        for a in available:
            if self.canonical(a) == target:
                return a
        return None

    def table(self):
        """Alias table as rows (for reports)."""
        out = [{'code': k, 'canonical': v, 'scope': 'all files' if k not in NOT_YET_LISTED else 'all files; not in the reference sheet (to confirm)'}
               for k, v in sorted(self.aliases.items())]
        out += [{'code': d['code'], 'canonical': d['canonical'],
                 'scope': f"not an alias: duplicate code in index {d['index_id']} vintage {d['vintage']} ({d['entity']}); fixed in the file"}
                for d in self.duplicates]
        return out
