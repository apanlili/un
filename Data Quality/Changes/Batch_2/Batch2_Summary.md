# DQP Batch 2 — integration summary
**Date:** 15 November 2026
**Scope:** the three Batch 2 changes in `DQP_Batch2_Instructions_for_Alfonso_2026-11-11.md` (this folder): roadmap issues 8, 10 and 11.
**Status:** Integrated and tested on the four regression cases and on all 24 indices (no errors; buckets identical to Batch 1). Not committed yet.

Batch 2 is built on top of Batch 1: all Batch 1 changes are kept. Matching rules, buckets, KPI identifiers and outlier detection are unchanged — bucket counts are identical to Batch 1 on every index tested.

---

## Overview

| Snippet | What it does | Where it shows |
|---|---|---|
| 1. Country-code audit (issue 8) | For every country code: in both files, simulator only or historical only; checked against the ISPAR country reference (valid, alias with its canonical code, or unknown) | `Country code audit` sheet, metadata workbook |
| 2. Percentages (issue 10) | Every user-facing `%` / `_pct` column on a 0–100 scale; exported matching ratio labelled as a ratio, with a 0–100 percentage next to it | Metadata and country profile workbooks |
| 3. Country Profile Coverage (issue 11) | One status per requested country, `AVAILABLE` or `NOT_COVERED_BY_INDEX_EDITION`; country sheets only for available countries | `Country Profile Coverage` sheet in the metadata, ISPAR input and country profile workbooks |

### Files
| File | Contents |
|---|---|
| `Metadata Automation v1.2.ipynb` (was `Metadata Automation - Batch 2.ipynb`), `metadata_batch2.py` | Batch 2 pipeline, **version 1.2** (copy of Batch 1 v1.1 plus the Batch 2 changes). Notebook and script give identical outputs (checked on EGDI 2024). |
| `utils/formatting_functions.py`, `utils/excel_functions.py` | Batch 2 functions, based on `DQP_Batch2_Reference_Snippets_2026-11-11.py`, in a section headed "Batch 2 ... moved here from 'batch2'" at the end of each file (originally `utils/batch2.py`). They are new functions; existing functions are unchanged, so v1.0 and v1.1 outputs do not change. |
| `utils/excel_functions.py` | Skip-message fix in the country-sheet writer (shared; affects only the error path). |
| `metadata_compare.py` | Reads each workbook's version from `Run Info` so v1.1 (fractions) and v1.2 (0–100) country percentages are compared on the same scale. |
| `Archive/Metadata Automation v1.0.ipynb` / `Archive/metadata_v1.0.py` (v1.0), `Archive/Metadata Automation v1.1.ipynb` / `Archive/metadata_v1.1.py` (v1.1) | Unchanged (archived 16 November). |

### How to run
```
python metadata_batch2.py --index index_1024 --all-outputs            # one index, all three workbooks
python metadata_batch2.py --countries SOM --profile                   # coverage / profile for Somalia only
python metadata_batch2.py --country-reference path/to/other.xlsx      # another country reference workbook
python metadata_batch2.py --no-iso-fix                               # audit only: keep the country codes as in the files
python metadata_batch2.py --no-country-reference                      # audit without the reference (NOT_CHECKED, no correction)
```
Notebook settings (Setup cell): `requested_countries` (None = ESCWA members, or e.g. `['SOM']`), `use_country_reference`, `fix_iso` and `country_reference_file`.

---

## 1. Country-code audit (issue 8)

### Change
Right after the simulator and historical data are read, the pipeline lists every country code found in either file:

| Column | Meaning |
|---|---|
| `ISO`, `Country` | Code as it appears in the files, and its name |
| `in_simulator`, `in_historical` | Present in each file |
| `presence_status` | `BOTH`, `SIMULATOR_ONLY` or `HISTORICAL_ONLY` |
| `canonical_iso_status` | `VALID` (a canonical code), `ALIAS` (a publisher alias, old code or country name that maps to a canonical code) or `UNKNOWN`; `NOT_CHECKED` with `--no-country-reference` |
| `canonical_code` | The canonical code (e.g. `KSV` → `XKX`, `PES` → `PSE`, `LIECHTENSTEIN` → `LIE`) |
| `presence_after_mapping` | `BOTH` / `SIMULATOR_ONLY` / `HISTORICAL_ONLY` once both files' codes are mapped to canonical codes |

The table is saved as the `Country code audit` sheet and summarised in the console, including the aliases found and the counts after mapping.

**Country reference.** One workbook, `Data/Reference Data/Country_Reference.xlsx`, built from the 23 October 2026 snapshots shipped with the pre-check package (`dqp_precheck_v0.3`, in this folder):

| Sheet | Content |
|---|---|
| `About` | Source, snapshot date, how to update |
| `PUBLISHER_ALIASES` | Code used in a publisher file → canonical code (KSV → XKX, PES → PSE ...) |
| `CANONICAL_ENTITIES` | The 253 valid codes |
| `CODE_HISTORY` | Old codes → current code |
| `COUNTRY_NAMES` | Country name → code, for names written in the code column |

The first three sheets have the same names and layout as the Google Sheet "ISPAR Geographic Reference & Publisher Mappings", so a new export can replace them. The workbook is read by `utils/country_codes.py`, the part of the pre-check's `ispar_reference/countries.py` the DQP needs (same mapping, checked against the original); the alias rules themselves stay in the workbook. The `dqp_precheck_v0.3` folder is kept here for reference only; the pipeline does not import it. Another file can be given with `--country-reference` (notebook: `country_reference_file`). The `Run Info` sheet lists the file used.

**ISO correction (after the audit).** Every `ALIAS` code is then replaced by its canonical code in both the simulator and historical data, before matching; `iso_corrected` in the audit marks the codes changed. The audit itself records the codes as they are in the files.
- Codes outside the reference (`UNKNOWN`, e.g. `ATG.1`, `IRN.1`, `ANT` in ICT) are kept as they are and flagged in the console.
- Hard flag: if a correction would give a country two rows for the same KPI (and year), because the file holds both the alias and the canonical code, the index stops with an error listing the rows. None of the 8 indices tested (the 7 below and EGDI 2024) has such a case.
- Switch off with `--no-iso-fix` (notebook: `fix_iso = False`) to reproduce the earlier v1.2 results. Only the country-code steps of the pre-check are used; its other checks (`run()`) are not.

Effect on the indices with alias codes (same rows; buckets change only for the corrected countries):

| Index | Corrections | Bucket change |
|---|---|---|
| WPS 2025 (`index_1022`) | KSV→XKX, PES→PSE | Palestine: 6 records E → 1 A, 1 B, 4 C |
| DARE (`index_10`) | PES→PSE, TZN→TZA | Palestine and Tanzania: 21 records each E → A |
| WJP (`index_1052`) | KSV→XKX | Kosovo: 44 records E → A |
| WPF 2026 (`index_1036`) | KSV→XKX, LIECHTENSTEIN→LIE | Liechtenstein: 5 records E → 1 A, 4 C |
| GCYB (`index_3`) | LAO PDR→LAO | Laos: 20 records E → 10 A, 10 C |
| ICT (`index_5`) | WBG→PSE | No bucket change (both files used WBG); Palestine now `AVAILABLE` in the coverage table and gets a profile sheet |
| FII 2025 (`index_1024`) | KSV→XKX | None (Kosovo has no historical data) |

### Result against the regression cases
| Index | Expected (both / simulator only / historical only) | DQP result | |
|---|---|---|---|
| FII 2025 (`index_1024`) | 138 / 1 (XKX) / 47 | 138 / 1 (KSV) / 47 | Match; Kosovo is coded `KSV` in our files, `XKX` after the pre-check |
| EGDI 2024 (`index_9`) | 192 / 1 (SWZ) / 0 | 192 / 1 (SWZ) / 0 | Match |
| GII 2026 (`index_7_2026`) | 139 / 0 / 0 | 139 / 0 / 0 | Match |
| WPS 2025 (`index_1022`) | 175 / 6 / 1 (GNQ) | 174 / 7 / 2 | Differs by one alias (below) |

**WPS 2025 — one-sided difference caused by an alias.** The WPS historical file codes Palestine as `PES`; the simulator file uses `PSE`. The pre-check maps `PES → PSE`, so the expected result counts Palestine in both files. Our files are not pre-checked, so the audit shows `PSE` as simulator-only and `PES` as historical-only. With the country reference, the audit marks `PES` as an `ALIAS` of `PSE`, and the counts after mapping are exactly 175 / 6 / 1.

This is also a data finding: because the codes differ, Palestine's WPS records never find their historical data in the DQP (in every version, 1.0–1.2). This is the kind of difference the audit is meant to make visible.

WPS 2025 audit, non-matching rows (example for the review):

| ISO | Country | in_simulator | in_historical | presence_status |
|---|---|---|---|---|
| FSM | Federated States of Micronesia | True | False | SIMULATOR_ONLY |
| GNQ | | False | True | HISTORICAL_ONLY |
| GRD | Grenada | True | False | SIMULATOR_ONLY |
| KIR | Kiribati | True | False | SIMULATOR_ONLY |
| KSV | Kosovo | True | False | SIMULATOR_ONLY |
| MHL | Marshall Islands | True | False | SIMULATOR_ONLY |
| PES | | False | True | HISTORICAL_ONLY |
| PLW | Palau | True | False | SIMULATOR_ONLY |
| PSE | Palestine | True | False | SIMULATOR_ONLY |

---

## 2. Percentages (issue 10)

### Change
| Table | Before | After |
|---|---|---|
| `Summary Stats by KPI`, `Summary Stats by Country` (`_pct` columns) | Fractions (0.96) | 0–100 (96.13) |
| Country profile: `<index> - KPI Quality (All Countries)` (`(%)` columns) | Fractions | 0–100 |
| Metadata sheet: `value_difference_percentage_inferred` | Ratio under a percentage name (0.0061) | `value_difference_ratio_inferred` (0.0061) + `value_difference_pct_inferred` (0.61) |

Tables that were already 0–100 (`Summary Stats`, `KPI Data Summary`, the country overview tables) are unchanged. The matching calculation still uses the ratio internally. Each run prints a check that every `%` value is within 0–100 and every row of bucket percentages sums to about 100.

### Before / after (maximum value in a `%` column; first-row sum)
| Index | Before (v1.1) | After (v1.2) | Expected | Row sum before → after |
|---|---|---|---|---|
| WPS 2025 | 0.96 | 96.13 | 96.13 | 1.00 → 99.99 |
| FII 2025 | 0.99 | 99.28 | 99.28 | 1.01 → 100.00 |
| EGDI 2024 | 0.99 | 99.48 | 99.48 | 1.01 → 100.00 |
| GII 2026 | 1.00 | 100.00 | 100.00 | 1.00 → 100.00 |

Bucket counts are unchanged on all four indices.

---

## 3. Country Profile Coverage (issue 11)

### Change
Before any output is written, each requested country (default: the 22 ESCWA members) gets one status:

| Column | Meaning |
|---|---|
| `ISO`, `Country` | Requested country |
| `profile_status` | `AVAILABLE` if the index edition has records for it, otherwise `NOT_COVERED_BY_INDEX_EDITION` |

The table is saved as `Country Profile Coverage` in the metadata workbook, the ISPAR input workbook and the country profile workbook. Country profile sheets are written only for `AVAILABLE` countries, so no empty or broken profile is produced. The writer's skip message now uses `country_iso` (it referred to an undefined `country`).

### Result
| Index | Somalia | Expected | Not covered (of 22 ESCWA members) | Country sheets |
|---|---|---|---|---|
| WPS 2025 | AVAILABLE | AVAILABLE | — | 22 |
| EGDI 2024 | AVAILABLE | AVAILABLE | PSE | 21 |
| FII 2025 | **NOT_COVERED_BY_INDEX_EDITION** | NOT_COVERED | COM, DJI, SOM, SDN, SYR, YEM | 16 |
| GII 2026 | **NOT_COVERED_BY_INDEX_EDITION** | NOT_COVERED | COM, DJI, IRQ, LBY, PSE, SOM, SDN, SYR, YEM | 13 |

---

## 4. All-index test (24 indices)

Version 1.2 was run on all 24 indices with all three outputs, alongside version 1.1 (Batch 1) as the baseline, and the two were compared with `metadata_compare.py`.

| Check | Result |
|---|---|
| Runs completed | 24 / 24 (v1.2 and v1.1), no errors |
| Bucket counts v1.1 vs v1.2 | Identical on all 24 indices (A+A1 share and every bucket change = 0.00) |
| `%` checks (`Summary Stats by KPI` / `by Country`) | 48 / 48 passed: all values within 0–100, rows sum to ~100 |
| Country profile sheets | Exactly the `AVAILABLE` countries on all 24 indices |
| Country percentages in the comparison | Same scale for v1.1 and v1.2; differences ≤ 0.66 points come from v1.1 storing fractions rounded to 2 decimals |

### Audit findings across the 24 indices
Most one-sided differences are genuine coverage differences (small states missing from one file). Six indices also show **code mismatches** — the same country coded differently in the two files, so its records never meet in the DQP:

| Index | Simulator code | Historical code | Country |
|---|---|---|---|
| WPS 2025 (`index_1022`) | `PSE` | `PES` | Palestine |
| DARE (`index_10`) | `PSE`, `TZA` | `PES`, `TZN` | Palestine, Tanzania |
| WJP (`index_1052`) | `KSV` | `XKX` | Kosovo |
| WPF 2026 (`index_1036`) | `LIE` | `LIECHTENSTEIN` (name in the ISO column) | Liechtenstein |
| GCYB (`index_3`) | `LAO` | `LAO PDR` (name in the ISO column) | Laos |
| ICT (`index_5`) | — | `ATG.1` (a duplicated Antigua and Barbuda column in the historical file) | Antigua and Barbuda |

Kosovo is also `KSV` in the FII 2025 and WPS 2025 simulator files, where the pre-check uses `XKX`. These are exactly the cases the universal pre-check resolves; the audit now makes them visible.

### Coverage across the 24 indices (22 ESCWA members requested)
| Countries not covered | Indices |
|---|---|
| None | WPS 2025, WPF 2026, HDI, GDI, WBL 2.0, WBL 1.0, GCYB |
| 1–3 | EGDI, E-participation, GovTech (PSE); SDI (LBY, PSE); PHDI (COM); BTI (COM, PSE); LNOB (LBY, SYR); ICT (PSE, SDN, YEM) |
| 5–7 | GHI, EPI 2026, FII 2025, DARE |
| 9–12 | IIAG, Open Data Policies, WJP, GII 2025, GII 2026 |

---

## 5. Status against the instructions

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Audit saved in both directions, not only printed | **Done** | `Country code audit` sheet |
| 2 | Aliases approved by the pre-check do not reappear as false missing countries | **Done** | Aliases are marked `ALIAS` in the audit and corrected to the canonical code before matching. |
| 3 | Codes outside the canonical reference are kept as review items | **Done** | `UNKNOWN` against the ISPAR reference, e.g. `ATG.1`, `IRN.1` (duplicated columns) and `ANT` (Netherlands Antilles, split) in ICT. |
| 4 | Every user-facing `%` is 0–100 and grouped buckets sum to ~100 | **Done** | |
| 5 | Ratio exported as `value_difference_ratio_inferred` plus `value_difference_pct_inferred` | **Done** | |
| 6 | Bucket counts unchanged | **Done** | Identical to v1.1 on every index tested |
| 7 | One coverage status per requested country; unavailable countries not sent to the writer | **Done** | |
| 8 | Somalia: NOT_COVERED in GII 2026 / FII 2025, AVAILABLE in WPS 2025 / EGDI 2024 | **Done** | |
| 9 | Skip message uses `country_iso` | **Done** | |
| 10 | Outlier detection unchanged | **Done** | |
| 11 | Upload code and test outputs to the shared folder | **Not done** | |

### Intentional changes from the reference
1. **Coverage table also in the metadata and ISPAR input workbooks**, not only before the country profiles, so it is saved even when profiles are not produced, and ISPAR can tell "not covered by this index" from "missing".
2. **Audit adds a `Country` column** (name) to the reference table.
3. **Audit uses the ISPAR country reference** (from `dqp_precheck_v0.3`) and adds `canonical_code`, the `ALIAS` status and `presence_after_mapping` to the reference table, so alias mismatches are visible without the pre-check having run on our files.
4. **ISPAR input saved without the run date** (by decision): `Profile_Input_ISPAR_<index>.xlsx` keeps a fixed name and is replaced on each run, so ISPAR always reads one file per index. The metadata and country profile workbooks keep the date and are never overwritten.
5. **No `Run Info` sheet in the ISPAR input workbook** (by decision): the ISPAR file holds only `Profile_counts`, `Older data table` and `Country Profile Coverage`. The run details (version, run ID, input files) are in the `Run Info` sheet of the metadata and country profile workbooks from the same run, which share the file date.
6. **Exact-match check:** the shared check expects fractions, so Batch 2 passes it fractions; its printed results are unchanged.
7. **Country codes corrected in the DQP** (by decision, still version 1.2): alias codes are replaced by their canonical code before matching, using the pre-check's reference data (`Country_Reference.xlsx`) and its code lookup (`utils/country_codes.py`). This changes buckets for the corrected countries only (table in section 1). The instructions leave canonicalisation to the universal pre-check; this does it inside the DQP until the pre-check runs on our files.

---

## 6. Open questions for the team
1. `Country_Reference.xlsx` holds the 23 October 2026 snapshots of the Geographic Reference shipped with `dqp_precheck_v0.3`. Is there a newer version of the Google Sheet we should export into it?
2. Six indices have country-code mismatches between their simulator and historical files (section 4: `PES`/`PSE`, `TZN`/`TZA`, `KSV`/`XKX`, names in the ISO column, a duplicated column). Should these be corrected upstream (pre-check or source files) before the next run?
3. Which historical files are current for EGDI 2024 (the corrected 11 November file is not in our folder) and GII 2026 (`20261019_..._GII_2026.xlsx` or `... v2.xlsx`; simulator `raw_GII_2026.xlsx` or a numbered copy)?
