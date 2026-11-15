# DQP Batch 1 — Snippet 2 integration summary
**Date:** 11 November 2026
**Scope:** Snippet 2 — apply authoritative cap/floor evidence before final A/B/C classification.
> **Renamed 15 November 2026:** `Metadata Automation - Snippet 2.ipynb` → `Metadata Automation - Batch 1.ipynb`, `metadata_snippet2.py` → `metadata_batch1.py`, output suffix `_snippet2` → `_batch1`, and the handoff files moved to `Changes/Batch_1/`. Output file names quoted below from earlier runs keep their original `_snippet2` names.

**Status:** Integrated and tested on EGDI 2024 (`index_9`). Updated 15 November 2026: reviewed A1 list applied, SDI 2026 KeyID 1414 checked, EGDI reconciled against the fixture (sections 3 and 5).

---

## 1. What was changed

### Files
| File | Change |
|---|---|
| `Metadata Automation - Batch 1.ipynb` (was `Metadata Automation - Snippet 2.ipynb`) | New copy of `Metadata Automation.ipynb` with the Snippet 2 changes. The original notebook is unchanged. |
| `utils/bound_rules.py` | New helper module. Existing utils files are unchanged. |

### Source of truth
- Caps/floors are read from `Changes/Batch_1/DQP_UCE_Bounds_Extract_v41_2026-11-01.csv`, the extract generated from UCE standardized metadata. DQP keeps no cap/floor list of its own.
- The CSV path is a setting (`UCE_BOUNDS_CSV`), not hard-coded into the logic.
- Bounds are selected by UCE vintage through `uce_vintage_dict` (e.g. `index_9` → `EGDI_2024`), because bound values change between editions for 104 KPIs.

### `utils/bound_rules.py`
| Function | Purpose |
|---|---|
| `load_uce_bounds(csv_path, vintage)` | Loads one vintage and returns one row per KPI: `uce_floor`, `uce_cap`, `uce_semantics`, `uce_a1_eligible`. Drops the duplicate rows in the extract (EPI_2024 KPIs 3214–3218) and converts `KeyID` to text. |
| `uce_a1_mask(df)` | A1 evidence: `data_report` sits on the UCE cap (or floor) **and** `most_recent_data` is beyond it. Only for A1-eligible semantics. |
| `uce_beyond_bound(df)` | Information flag: `most_recent_data` is beyond any UCE bound (all semantics). |
| `empty_uce_bounds()` | Empty table used when UCE bounds are switched off. |

A1-eligible semantics: `RAW_PRETRANSFORM_CLIP` and `RAW_TRUNCATE`, the report-value bounds, following the stage mapping in `DQP_Batch1_Full_Portfolio_Regression_2026-11-01.py` line 217. `SCORE_*` (calculation-stage) bounds are flagged only, never turned into A1.

**Reviewed A1 list (`REVIEWED_A1_KPIS`, added 15 November).** A KPI produces A1 only if its semantics is A1-eligible **and** it is on the reviewed list for that vintage. The list currently holds `EGDI_2024` KPIs 271, 274 and 280. All other UCE bounds are still loaded and flagged in `uce_beyond_bound`; KPIs are added to the list only after their DQP interpretation has been reviewed.

### Notebook changes (`Metadata Automation - Batch 1.ipynb`)
| Cell | Change |
|---|---|
| Imports | `from utils.bound_rules import *` |
| Setup | New settings: `USE_UCE_BOUNDS` (on/off switch), `UCE_BOUNDS_CSV`, `uce_vintage_dict`, `output_suffix = '_batch1'` (was `'_snippet2'`). |
| Reference tables | Loads the UCE bounds for the current index. The legacy `get_simulator_data_cap` still runs, so `possible_cap` stays available for comparison. |
| Recreate metadata | Merges the UCE bounds and adds `uce_beyond_bound`. The A1 block now runs in two modes: **UCE mode**, where A1 is evaluated independently of A/B, takes precedence and clears any A/B match on the same record (recorded in `A1_overrode_A_B`); and **legacy mode**, where the original A1 code runs unchanged under `else:` when `USE_UCE_BOUNDS = False`. The commented-out "one bucket per row" check now prints its result. |
| Output columns | Adds `uce_floor`, `uce_cap`, `uce_semantics`, `uce_a1_eligible`, `uce_beyond_bound`, `A1_overrode_A_B`. |
| Output files | All three output files get the `_batch1` suffix (was `_snippet2`), so the original outputs are never overwritten. |

Downstream cells (summary statistics, country profiles, ISPAR input) are unchanged. They read the same `A1_cap_adjusted_match` and A/B columns as before.

---

## 2. Test result: EGDI 2024 (`index_9`)

Both modes ran end to end. Row count was unchanged (2,895 rows) and every row is in exactly one bucket.

| Mode | A | A1 | B | C | D | E |
|---|---|---|---|---|---|---|
| Legacy (inferred cap) | 2,032 | 63 | 463 | 251 | 32 | 54 |
| UCE bounds | 2,030 | **106** | 422 | 251 | 32 | 54 |

**43 records moved to A1**, all on KPIs 271 and 274 (cap 120). Each has `data_report = 120` and a 2023 historical value above 120.

| Previous bucket | KPI 271 | KPI 274 | Previous match |
|---|---|---|---|
| B exact | 15 | 3 | An older year that happened to equal 120 (1–14 years earlier). |
| B approx | 17 | 6 | An older year at 119 or 121, within 1% (up to 20 years earlier). |
| A approx | 1 (KEN) | 1 (LVA) | The latest value is within 1% of 120. |

This is the EGDI ordering issue described in the instructions: an ordinary A/B match was assigned before the cap evidence was considered.

The 5 records with `data_report = 120` that are not A1 are all correct:
- San Marino 271 has a latest value of exactly 120, so it stays A.
- Philippines 271 (117.3), Kyrgyzstan 274 (92.1) and Libya 274 (118) have latest values below the cap.
- Eswatini 271 has no historical data.

**KPI 280 (cap 100):** no A1, and 187 records stay in A. The 19 records with a historical value above 100 have uncapped report values (e.g. AUS 121.45) and are exact A matches. They are flagged in `uce_beyond_bound`. This KPI is a calculation-stage case (see section 3).

Output files for the before/after review are in `Desktop/UN/Data/Metadata Automation Outputs/`:
- `Metadata_Automation_index_9_snippet2.xlsx` (UCE mode)
- `Metadata_Automation_index_9_snippet2_legacy.xlsx` (legacy mode)

---

## 3. Status against the Snippet 2 ask

| # | Snippet 2 ask | Status | Notes |
|---|---|---|---|
| 1 | Read standardized UCE metadata directly via `load_uce_bound_rules(uce_root, …)` | **Not done** | The supplied CSV extract is used. The instructions allow this until the UCE/Generator team confirms a stable metadata location. The UCE package is not available locally. |
| 2 | Calculation-stage A1 (`a1_from_calculation_bound`): raw value is a timely, accurate match **and** beyond a calculation bound | **Not done** | Affects EGDI 280 and GGI 36, whose report values are not stored capped. These records are flagged in `uce_beyond_bound` but stay in A/B/C. |
| 3 | Separate `raw_value` / `comparison_value` / `calculation_value` columns (`apply_authoritative_bound`) | **Partly done** | The raw values (`data_report`, `most_recent_data`) are kept unchanged, and the bound is used only for the A1 test. No bounded comparison/calculation value columns are produced. |
| 4 | "Use A1 only where the DQP interpretation of that bound has been reviewed" (`dqp_a1_eligible`) | **Done (15 Nov)** | Reviewed A1 list `REVIEWED_A1_KPIS` in `utils/bound_rules.py` (EGDI 2024: 271, 274, 280). See section 5. |
| 5 | Cross-index test: GGI 2026, KeyID 36 | **Not run** | GGI is not in `data_files_dict`, and no GGI 2026 simulator file is available (the 'gender gap 2026' file in the Simulator Data folder is a copy of the historical file). With the reviewed A1 list, KeyID 36 would be flagged only. |
| 6 | Cross-index test: SDI 2026, KeyID 1414 | **Done (15 Nov)** | As expected: 169 records, all A; 71 flagged in `uce_beyond_bound` (cap 100, `SCORE_CLIP_AT_GOALPOST_EQUIVALENT`); no A1. Matches the instructions' 71 observations above the goalpost. |
| 7 | Cross-index test: EPI 2024, KeyID 1606 | **Not run** | No Environmental Performance Index 2024 files are available (`raw_EPI_2024.xlsx` is E-participation, `index_12`). The notebook has `index_1034` (EPI 2026); in EPI 2026 the 1606 bounds differ (−0.084 / 0.084). Snippet 1 (negative values) is in place. |
| 8 | Cross-check against `EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx` | **Done (15 Nov)** | 99 of the fixture's 100 cases are A1, as the fixture expects. Philippines 271 is excluded by decision (reference-year logic). See section 5. |
| 9 | Vintage mapping for all indexes | **Partly done** | Every mapped vintage was checked against its simulator file: all bound KPIs are present, except `BTI_Q13F` (BTI 2026, a derived KPI) and 1328 (GII 2026). HDI, PHDI and GHI are set to `None` because their raw-file edition is unconfirmed. Their bounds are all calculation-stage, so mapping them would only add `uce_beyond_bound` flags, never A1. HDI and GHI bounds are identical across editions; PHDI bounds differ. |
| 10 | Before/after on other indexes | **Done** | All 24 indices compared with `metadata_compare.py` (original vs Snippet 2): only EGDI 2024, FII 2025 and GII 2025/2026 changed. With the reviewed A1 list, the FII/GII A1 records revert (section 5), so only EGDI changes. |
| 11 | Upload code and test outputs to the shared Metadata Automation Drive area | **Not done** | |
| 12 | Snippets 1 and 3 | **Separate** | See `Snippet1_Summary.md` and `Snippet3_Summary.md`. |

---

## 4. Open questions for review
1. **EGDI 280:** the test matrix calls it a calculation-stage cap, but the regression runner maps `RAW_PRETRANSFORM_CLIP` to report value. Which is correct?
2. **Reviewed A1 list:** only EGDI 2024 (271, 274, 280) is on the list. Which KPIs should be reviewed next: the GGI truncation caps (14 KPIs per vintage) and the observed-range caps of FII 2025 (7 KPIs) and GII 2025/2026 (23 KPIs each)?
3. **A vs A1:** when the latest value is within 1% of the cap (KEN 271, LVA 274), is A1 the preferred label over A?
4. **Calculation-stage A1:** if a record is an exact A match and its raw value is beyond a calculation bound, should it move to A1?
5. **UCE location:** where will the stable metadata location/manifest be, so the CSV extract can be replaced by a direct read?

---

## 5. Updates (15 November 2026)

### Reviewed A1 list applied
`utils/bound_rules.py` now has `REVIEWED_A1_KPIS`. `uce_a1_eligible` is 1 only when the bound semantics is report-value (`RAW_PRETRANSFORM_CLIP`, `RAW_TRUNCATE`) **and** the KPI is on the reviewed list for that vintage. The A1 test itself is unchanged.

Before the list, these KPIs in the mapped vintages were A1-eligible: EGDI 2024 (3), FII 2025 (7), GII 2025 (23) and GII 2026 (23). Now only the 3 EGDI KPIs are. Effect on the outputs (rerun of the four affected indices):

| Index | KPI | Before | After |
|---|---|---|---|
| EGDI 2024 (`index_9`) | 271, 274 | 106 A1 | No change |
| FII 2025 (`index_1024`) | 1145 | A1 | A |
| GII 2025 (`index_7_2025`) | 130 | A1 | B |
| GII 2025 (`index_7_2025`) | 1908 | A1 | A |
| GII 2025 (`index_7_2025`) | 185 | A1 | C |
| GII 2026 (`index_7_2026`) | 1245 | A1 | C |

No other record changed bucket; row counts are unchanged.

### SDI 2026, KeyID 1414
169 records, all in A. 71 have a most recent historical value above the goalpost of 100 and are flagged in `uce_beyond_bound`. The bound is calculation-stage (`SCORE_CLIP_AT_GOALPOST_EQUIVALENT`), so no A1 is assigned, as intended.

### EGDI reconciliation against the fixture
`EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx`, 100 supported cases (73 KPI 271, 27 KPI 274):

| Fixture's earlier bucket | Count | Now |
|---|---|---|
| A1 | 62 | A1 |
| B | 36 | A1 |
| A (Kenya 271) | 1 | A1 |
| C (Philippines 271) | 1 | C — excluded by decision |

- **99 of 100 match** the fixture's corrected cap-first result.
- **Philippines 271** needs reference-year logic (the 2022 value, 146, is above the cap; the latest 2023 value, 117.3, is not). This is excluded: the older vintage data needed to infer the reference year is not available.
- **7 further A1 records are outside the fixture's 100 cases:** ISL, SEN, UKR, GBR (271) and AUT, LVA, KOR (274). Each has `data_report` = 120 and a 2023 value above 120, so they meet the A1 rule. The fixture leaves them out because their 2022 value is not above 120 (120 for ISL, UKR, GBR, AUT, KOR; 118 for SEN, LVA). This is the same latest-year vs reference-year question as Philippines and is set aside with it.

