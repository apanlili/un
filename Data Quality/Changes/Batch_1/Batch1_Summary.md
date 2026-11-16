# DQP Batch 1 — integration summary
**Date:** 15 November 2026
**Scope:** the three Batch 1 changes in `DQP_Batch1_Instructions_for_Alfonso_v2_2026-11-01.md` (this folder).
**Status:** All three snippets integrated and tested. Committed in `d106bb7`; the Snippet 3 file naming and versioning were simplified after that commit (section 3).

This document replaces the separate `Snippet1_Summary.md`, `Snippet2_Summary.md` and `Snippet3_Summary.md` (available in git history).

---

## Overview

| Snippet | What it does | Changes buckets? | Where it is |
|---|---|---|---|
| 1. Negative and zero values | Relative difference divides by `abs(report value)` | Yes, only for negative report values | Shared `utils/formatting_functions.py`, so every pipeline |
| 2. Authoritative cap/floor | A1 decided from UCE bounds before A/B, for KPIs on a reviewed list | Yes, for reviewed KPIs (EGDI 2024 271, 274, 280) | Batch 1 notebook and script only |
| 3. Run stamp, no overwriting | Adds the run date to every output file name, a version number, and a `Run Info` sheet to every workbook | No | Scripts and notebooks |

### Files
| File | Contents |
|---|---|
| `Archive/Metadata Automation v1.0.ipynb` (was `Metadata Automation.ipynb`), `Archive/metadata_v1.0.py` (was `metadata_automation.py`) | Original pipeline, version 1.0. Snippets 1 (shared utils) and 3. |
| `Archive/Metadata Automation v1.1.ipynb` (was `Metadata Automation - Batch 1.ipynb`), `Archive/metadata_v1.1.py` (was `metadata_batch1.py`) | Batch 1 pipeline, version 1.1 (renamed from `... - Snippet 2` / `metadata_snippet2.py`). Snippets 1, 2 and 3. Outputs are named like the original's and kept apart by output folder and version. |
| `metadata_compare.py` | Compares original vs Batch 1 outputs for every index, merged into one workbook. Has Snippet 3. |
| `utils/bound_rules.py` | Snippet 2: UCE bounds, reviewed A1 list, A1 test, beyond-bound flag. |
| `utils/run_stamp.py` | Snippet 3: run record, fingerprint, `Run Info` sheet, overwrite guard. |
| `utils/runner.py` (was `utils/batch.py`), `utils/index_files.py` | Shared command line and batch loop; index → file, UCE vintage and edition mapping. |

---

## 1. Snippet 1 — negative and zero values in approximate matching

### Change
`get_match_data` in `utils/formatting_functions.py` (commit `3388822`, 7 November):

| Case | Before | After |
|---|---|---|
| Negative report value | `difference / report` is negative, so it always passes `<= 1%` | `difference / abs(report)`, a true relative difference |
| Exact match, including `0 == 0` | Exact | Unchanged |
| Non-exact report value of 0 | No percentage, no approximate match | Unchanged |

The zero handling already matched the instructions; only the sign handling is new. No absolute tolerance for zero values was added (the instructions require a separate per-KPI review). Records that no longer match go wherever the normal bucket logic sends them.

### Test: GII 2026 (`index_7_2026`)
Latest-year approximate matches with a negative report value:

| | Instructions | Result |
|---|---|---|
| Passed under the signed rule | 203 | 203 |
| Genuinely within 1% | 16 | 16 |
| False matches removed | 187 | 187 |

Full pipeline, before vs after:

| Bucket | Before | After | Change |
|---|---|---|---|
| A | 9,410 | 9,223 | −187 |
| B | 211 | 275 | +64 |
| C | 268 | 391 | +123 |
| D, E, F, G | 1,225 | 1,225 | 0 |

All 187 records have a negative report value and are on the KPIs the instructions name: 119 (70), 118 (60) and 117 (57), the exact split given. 64 find a genuine older-year match (B); 123 have none (C). The 97 non-exact zero-report observations get no percentage match.

---

## 2. Snippet 2 — authoritative cap/floor before A/B/C

### Source of truth
- Bounds come from `DQP_UCE_Bounds_Extract_v41_2026-11-01.csv`, kept in the local data folder under `Reference Data/` (a copy of the handoff file in this folder), generated from UCE standardized metadata. DQP keeps no cap/floor list of its own.
- The CSV path is a setting (`UCE_BOUNDS_CSV` in the notebook, `--uce-csv` in the script).
- Bounds are selected by UCE vintage (`UCE_VINTAGES`, e.g. `index_9` → `EGDI_2024`), because bound values differ between editions for 104 KPIs.

### Rule
A record is A1 when all of these hold:
1. The KPI's bound is applied to the report value (`RAW_PRETRANSFORM_CLIP` or `RAW_TRUNCATE`). Calculation-stage bounds (`SCORE_*`) never produce A1.
2. The KPI is on the **reviewed A1 list** for that vintage (`REVIEWED_A1_KPIS` in `utils/bound_rules.py`), currently `EGDI_2024`: 271, 274, 280. KPIs are added only after their DQP interpretation is reviewed.
3. `data_report` sits on the cap (or floor) and the most recent historical value is beyond it.

A1 is tested before A/B is final and takes precedence; any A/B match it replaces is recorded in `A1_overrode_A_B`. Every record beyond any UCE bound, of any type, is flagged in `uce_beyond_bound` without changing its bucket. Raw values (`data_report`, `most_recent_data`) are never altered.

The legacy A1 logic (cap inferred from the simulator data) is kept and runs with `USE_UCE_BOUNDS = False` / `--legacy-a1`.

New output columns: `uce_floor`, `uce_cap`, `uce_semantics`, `uce_a1_eligible`, `uce_beyond_bound`, `A1_overrode_A_B`.

### Test: EGDI 2024 (`index_9`)
| Mode | A | A1 | B | C | D | E |
|---|---|---|---|---|---|---|
| Legacy (inferred cap) | 2,032 | 63 | 463 | 251 | 32 | 54 |
| UCE bounds | 2,030 | **106** | 422 | 251 | 32 | 54 |

43 records moved to A1, all on KPIs 271 and 274 (cap 120), each with `data_report` = 120 and a 2023 value above 120. They were previously B exact (18), B approx (23) or A approx (2: KEN 271, LVA 274) — the ordering issue described in the instructions. KPI 280 (cap 100) produces no A1: its report values are not capped, so the 19 records above 100 stay exact A matches and are flagged.

### Reconciliation against `EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx`
| Fixture's earlier bucket | Count | Now |
|---|---|---|
| A1 | 62 | A1 |
| B | 36 | A1 |
| A (Kenya 271) | 1 | A1 |
| C (Philippines 271) | 1 | C — excluded by decision |

- 99 of 100 cases match the fixture's corrected result.
- Philippines 271 would need reference-year logic (2022 value 146 is above the cap; latest 2023 value 117.3 is not). Excluded: the older vintage data needed to infer the reference year is not available.
- 7 A1 records are outside the fixture's 100 cases (ISL, SEN, UKR, GBR on 271; AUT, LVA, KOR on 274). They meet the A1 rule on their 2023 value; the fixture leaves them out because their 2022 value is not above 120. Same reference-year question as Philippines, set aside with it.

### Other indices
- **All 24 indices compared** (`metadata_compare.py`, original vs Batch 1). Before the reviewed list, only EGDI 2024, FII 2025 and GII 2025/2026 changed. The reviewed list reverts the 5 FII/GII A1 records, so only EGDI changes:

| Index | KPI | Before the list | After |
|---|---|---|---|
| FII 2025 (`index_1024`) | 1145 | A1 | A |
| GII 2025 (`index_7_2025`) | 130 | A1 | B |
| GII 2025 (`index_7_2025`) | 1908 | A1 | A |
| GII 2025 (`index_7_2025`) | 185 | A1 | C |
| GII 2026 (`index_7_2026`) | 1245 | A1 | C |

- **SDI 2026, KeyID 1414:** 169 records, all A. 71 above the goalpost of 100 are flagged (matches the instructions' 71); the bound is calculation-stage, so no A1.

---

## 3. Snippet 3 — reproducible run stamp and non-overwriting outputs

The ask: *"Every DQP output should carry enough information to reproduce the run: code version; index and edition; exact input identities; run timestamp / run ID; stable input fingerprint. A later run must create a new output filename rather than silently overwrite an earlier file."* No result changes.

### What changes
| | Before | After |
|---|---|---|
| File name | `Metadata_Automation_index_9.xlsx` | `Metadata_Automation_index_9_20261115.xlsx` (run date added; a second run the same day gets `_2`, then `_3`) |
| Location | Output folder | Same output folder |
| Rerun | Overwrites the previous file | New file; earlier files are kept. Writing over an existing file is blocked. |
| Workbook contents | Results | Same results plus a `Run Info` sheet at the end |

The same applies to the ISPAR input, country profile and comparison workbooks. `metadata_compare.py` ignores the date when pairing files and uses the newest file for each index.

**`--no-date`** (also `--flat`) in the scripts, or `use_date_in_filename = False` in the notebooks, saves without the date, under the old names, overwriting earlier files. The `Run Info` sheet is still added.

The notebooks use the same `utils/run_stamp.py`: on `index_9`, each notebook's three outputs are identical to its script's, sheet for sheet, with the same input fingerprint.

### Versioning
Each script and notebook carries an internal version (`VERSION`): the original pipeline is **1.0**, Batch 1 is **1.1**, the comparison script is 1.0. It is recorded in `Run Info` and in the run ID, and is the code version asked for by the instructions. Raise it whenever the code changes.

### `Run Info` sheet
| Field | Example |
|---|---|
| Run time | 2026-11-15 16:58:08+08:00 |
| Run ID | `index_12_v1.1_20261115-165808` (index, version, run time) |
| Version | 1.1 |
| Index, Edition | index_12, EPI_2024 |
| Script | metadata_batch1.py |
| Input files | Name and last modified date of the historical, simulator and UCE bounds files (and the profile template when used) |

The comparison workbook's `Run Info` lists the run, the two folders, and each compared file with the run ID from its own `Run Info` (so its version is visible).

### Differences from the reference
- File name: the reference uses `Metadata_Automation_{index}_{edition}_{run_id}.xlsx`. Here only the run date is added, to keep names short; the edition, version and run ID are in `Run Info`.
- `Run Info` lists input files by name and modified date only; the input fingerprint and file content hashes are computed but not shown (by decision).
- Code version: an internal version number per script instead of a code hash.
- The fingerprint also covers settings that change results (A1 mode, ESCWA-only, data source), not only input files.

### Tests
| Check | Result |
|---|---|
| Same index run twice on one day | `..._20261115.xlsx` and `..._20261115_2.xlsx`; both kept |
| Same inputs and settings | Same fingerprint; different run IDs |
| One cell changed in an input file, or `--legacy-a1` | New fingerprint |
| Outputs vs before Snippet 3 (`index_9`, all three files) | Identical apart from `Run Info`; all 16 outlier plots kept |
| `--no-date` run twice | Old file name, overwritten in place; `Run Info` present |
| Compare with several runs in a folder | Newest file per index used; each file's run ID and version shown |

---

## 4. Status against the instructions

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Snippet 1: `abs()` denominator, exact `0 == 0`, no % match for a zero report | **Done** | |
| 2 | Snippet 1: GII 2026 regression (187 false matches) | **Done** | Exact match to the instructions. |
| 3 | Snippet 2: authoritative bound before A/B, raw evidence preserved | **Done** | |
| 4 | Snippet 2: A1 only where the bound's DQP interpretation is reviewed | **Done** | Reviewed list, EGDI 2024 only. |
| 5 | Snippet 2: read UCE metadata directly (`load_uce_bound_rules`) | **Not done** | CSV extract used, as allowed until the UCE team confirms a stable metadata location. |
| 6 | Snippet 2: calculation-stage A1 (`a1_from_calculation_bound`) | **Not done** | EGDI 280 and GGI 36 are flagged only. |
| 7 | Snippet 2: bounded comparison/calculation value columns | **Partly done** | Raw values kept; no bounded value columns. |
| 8 | Snippet 2: EGDI regression and fixture | **Done** | 99/100; Philippines excluded by decision. |
| 9 | Snippet 2: SDI 2026 KeyID 1414 | **Done** | |
| 10 | Snippet 2: GGI 2026 KeyID 36 | **Not run** | No GGI 2026 simulator file (the "gender gap 2026" file in Simulator Data is a copy of the historical file). Would be flagged only. |
| 11 | Snippet 2: EPI 2024 KeyID 1606 | **Not run** | No Environmental Performance Index 2024 files (`raw_EPI_2024.xlsx` is E-participation). |
| 12 | Snippet 2: vintage for every index | **Partly done** | HDI, PHDI and GHI unconfirmed (calculation-stage bounds only, so no A1 effect). |
| 13 | Snippet 3: code version, index/edition, inputs, run ID, fingerprint | **Done, deviation** | Code version = internal version number (1.0 original, 1.1 Batch 1). Input files are listed by name and modified date. The input fingerprint (SHA-256 of version, settings and file contents) and per-file content hashes are still computed but, by decision, not shown on the `Run Info` sheet. |
| 14 | Snippet 3: a later run creates a new output file name | **Done** | Run date added to every file name (`_2`, `_3` for same-day reruns); `--no-date` restores the old names. |
| 15 | Snippet 3: Drive inputs, database runs | **Partly done** | Drive files are read as local/synced files. Database runs record the environment only; the data read is not fingerprinted. |
| 16 | Snippet 3 in the notebooks | **Done** | Same helpers as the scripts; outputs identical on `index_9`. |
| 17 | Editions | **Partly done** | From simulator file names. To confirm: GHI, HDI, PPHDI, WBL 1.0, DARE (no year); `index_1052` (historical WPJ 2026 vs simulator WJP 2025); `index_12` `EPI_2024` clashes with the UCE EPI code. Set in `EDITION_OVERRIDES`. |
| 18 | Upload code and test outputs to the shared Drive area | **Not done** | |

---

## 5. Open questions for review
1. **EGDI 280:** the test matrix calls it a calculation-stage cap, but the regression runner maps `RAW_PRETRANSFORM_CLIP` to report value. Which is correct?
2. **Reviewed A1 list:** which KPIs should be reviewed next — the GGI truncation caps (14 per vintage), FII 2025 (7), GII 2025/2026 (23 each)?
3. **A vs A1:** when the latest value is within 1% of the cap (KEN 271, LVA 274), is A1 preferred over A?
4. **Calculation-stage A1:** should an exact A match whose raw value is beyond a calculation bound move to A1?
5. **UCE location:** where will the stable metadata location be, so the CSV extract can be replaced by a direct read?
6. **Versioning:** agree on an internal version number (1.0 original, 1.1 Batch 1) as the code version, raised by hand when the code changes?
7. **Fingerprint scope:** agree that settings (A1 mode, ESCWA-only, data source) belong in the fingerprint?
8. **Editions:** confirm the editions listed in item 17 and a naming convention that avoids clashes with UCE vintage codes.
9. **Database runs:** fingerprint the data read from the database, or is recording the environment enough for MVP1?
