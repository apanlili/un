"""
Country codes: alias and old codes -> canonical code, from the country reference workbook.

Stripped from dqp_precheck v0.3 (ispar_reference/countries.py, CountryCodes; Computational Economics Unit,
23 October 2026; full package in Changes/Batch_2/dqp_precheck_v0.3). Only what the Batch 2 country-code
audit and ISO correction need: reading the workbook, the alias / code-history / name mapping, and canonical().

Workbook (<data-root>/Reference Data/Country_Reference.xlsx), same sheets as the Google Sheet
'ISPAR Geographic Reference & Publisher Mappings' plus COUNTRY_NAMES:
  PUBLISHER_ALIASES  : simulator_identifier_observed / publisher_entity_name -> canonical_code (alias_scope 'all' or
                       'publisher' = valid only in that index's files)
  CANONICAL_ENTITIES : canonical_code (ISO 3166-1 alpha-3 plus the approved non-ISO codes XKX, XOE, XNC, CHI)
  CODE_HISTORY       : old_code -> current_code (only when the old code has a single successor; splits not mapped)
  COUNTRY_NAMES      : ISO, Country (for files that write a country name in the code column)

Rules (as in dqp_precheck):
  * an alias code maps to its canonical code in every file, or only in its publisher's files (alias_scope 'publisher');
  * a row whose observed code is itself a canonical code (CYP written for Northern Cyprus) is not an alias;
  * an unknown code is returned unchanged: never guessed.
"""
import re
from pathlib import Path

import pandas as pd

COUNTRY_REFERENCE_NAME = 'Country_Reference.xlsx'          # in <data-root>/Reference Data/
_CODE = re.compile(r'[A-Z]{3}')


def _norm_name(s) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def _sheet(path, name, required=True) -> list[dict]:
    try:
        return pd.read_excel(path, sheet_name=name, dtype=str, keep_default_na=False).to_dict('records')
    except ValueError:                       # sheet not in the workbook
        if required:
            raise ValueError(f'{Path(path).name}: sheet {name} not found')
        return []


class CountryCodes:
    def __init__(self, alias_rows, canonical, history_rows=(), name_rows=()):
        self.canonical_codes = {str(c).strip().upper() for c in canonical if str(c).strip()}
        self.aliases = {}            # code -> canonical, valid in every file
        self.scoped = {}             # (index_id, code) -> canonical, valid only in that publisher's files
        self.names = {}              # normalised name -> canonical
        self.scoped_names = {}       # (index_id, normalised name) -> canonical
        for r in alias_rows:
            can = (r.get('canonical_code') or '').strip().upper()
            if not can:
                continue
            publisher_only = str(r.get('alias_scope', '')).strip().lower() == 'publisher'
            idx = str(r.get('index_id', '')).strip()
            name = (r.get('publisher_entity_name') or '').strip()
            if name:
                if publisher_only:
                    self.scoped_names[(idx, _norm_name(name))] = can
                else:
                    self.names[_norm_name(name)] = can
            for code in [c.strip().upper() for c in (r.get('simulator_identifier_observed') or '').split('/')]:
                if not _CODE.fullmatch(code) or code == can:
                    continue
                if publisher_only:
                    self.scoped[(idx, code)] = can
                elif code not in self.canonical_codes:     # a canonical code written for another entity is not an alias
                    self.aliases[code] = can
        # code changes over time: old code -> current code when there is a single successor
        olds = [(h.get('old_code') or '').strip().upper() for h in history_rows]
        for h in history_rows:
            old, new = (h.get('old_code') or '').strip().upper(), (h.get('current_code') or '').strip().upper()
            if str(h.get('scope', 'all')).strip().lower() == 'publisher' or olds.count(old) > 1 or old == 'YUG':
                continue                                   # publisher-scoped, or a split (YUG itself split again)
            if _CODE.fullmatch(old) and _CODE.fullmatch(new) and old not in self.canonical_codes:
                self.aliases[old] = new
        # country names from COUNTRY_NAMES, after the names listed in PUBLISHER_ALIASES
        self.country_names = {_norm_name(r['Country']): str(r['ISO']).strip().upper()
                              for r in name_rows if r.get('ISO') and r.get('Country')}

    @classmethod
    def from_workbook(cls, path):
        """Read the country reference workbook (see the module docstring for the sheets)."""
        return cls(alias_rows=_sheet(path, 'PUBLISHER_ALIASES'),
                   canonical=[r['canonical_code'] for r in _sheet(path, 'CANONICAL_ENTITIES')],
                   history_rows=_sheet(path, 'CODE_HISTORY', required=False),
                   name_rows=_sheet(path, 'COUNTRY_NAMES', required=False))

    def canonical(self, code, index_id=None) -> str:
        """Canonical code for a code as written in a file; unknown codes are returned unchanged."""
        c = '' if code is None else str(code).strip().upper()
        if index_id is not None and (str(index_id), c) in self.scoped:
            return self.scoped[(str(index_id), c)]
        return self.aliases.get(c, c)

    def by_name(self, name, index_id=None) -> str:
        """Canonical code for a country name ('' if not found): PUBLISHER_ALIASES names first, then COUNTRY_NAMES."""
        n = _norm_name(name)
        if not n:
            return ''
        if index_id is not None and (str(index_id), n) in self.scoped_names:
            return self.scoped_names[(str(index_id), n)]
        return self.names.get(n) or self.country_names.get(n, '')
