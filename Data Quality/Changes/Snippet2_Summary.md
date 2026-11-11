# DQP Batch 1 — Snippet 2 integration summary
**Date:** 11 November 2026
**Scope:** Snippet 2 — apply authoritative cap/floor evidence before final A/B/C classification.
**Status:** Minimal integration done and tested on EGDI 2024 (`index_9`). Not committed.

---

## 1. What was changed

### Files
| File | Change |
|---|---|
| `Metadata Automation - Snippet 2.ipynb` | New copy of `Metadata Automation.ipynb` with the Snippet 2 changes. The original notebook is unchanged. |
| `utils/bound_rules.py` | New helper module. Existing utils files are unchanged. |

### Source of truth
- Caps/floors are read from `Changes/DQP_UCE_Bounds_Extract_v41_2026-11-01.csv`, the extract generated from UCE standardized metadata. DQP keeps no cap/floor list of its own.
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

### Notebook changes (`Metadata Automation - Snippet 2.ipynb`)
| Cell | Change |
|---|---|
| Imports | `from utils.bound_rules import *` |
| Setup | New settings: `USE_UCE_BOUNDS` (on/off switch), `UCE_BOUNDS_CSV`, `uce_vintage_dict`, `output_suffix = '_snippet2'`. |
| Reference tables | Loads the UCE bounds for the current index. The legacy `get_simulator_data_cap` still runs, so `possible_cap` stays available for comparison. |
| Recreate metadata | Merges the UCE bounds and adds `uce_beyond_bound`. The A1 block now runs in two modes: **UCE mode**, where A1 is evaluated independently of A/B, takes precedence and clears any A/B match on the same record (recorded in `A1_overrode_A_B`); and **legacy mode**, where the original A1 code runs unchanged under `else:` when `USE_UCE_BOUNDS = False`. The commented-out "one bucket per row" check now prints its result. |
| Output columns | Adds `uce_floor`, `uce_cap`, `uce_semantics`, `uce_a1_eligible`, `uce_beyond_bound`, `A1_overrode_A_B`. |
| Output files | All three output files get the `_snippet2` suffix, so the original outputs are never overwritten. |

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

## 3. What was not done (against the Snippet 2 ask)

| # | Snippet 2 ask | Status | Notes |
|---|---|---|---|
| 1 | Read standardized UCE metadata directly via `load_uce_bound_rules(uce_root, …)` | **Not done** | The supplied CSV extract is used. The instructions allow this until the UCE/Generator team confirms a stable metadata location. The UCE package is not available locally. |
| 2 | Calculation-stage A1 (`a1_from_calculation_bound`): raw value is a timely, accurate match **and** beyond a calculation bound | **Not done** | Affects EGDI 280 and GGI 36, whose report values are not stored capped. These records are flagged in `uce_beyond_bound` but stay in A/B/C. |
| 3 | Separate `raw_value` / `comparison_value` / `calculation_value` columns (`apply_authoritative_bound`) | **Partly done** | The raw values (`data_report`, `most_recent_data`) are kept unchanged, and the bound is used only for the A1 test. No bounded comparison/calculation value columns are produced. |
| 4 | "Use A1 only where the DQP interpretation of that bound has been reviewed" (`dqp_a1_eligible`) | **Deviation** | Eligibility is set by bound type (`RAW_PRETRANSFORM_CLIP`, `RAW_TRUNCATE`), not by a reviewed list. Only the EGDI caps have a reviewed interpretation, but GGI truncation caps (14 KPIs) and GII/FII observed-range caps (48 KPIs) are also A1-eligible. A1 still requires the report value to sit exactly on the bound with the historical value beyond it, so a bound existing is not enough on its own. No effect on EGDI. |
| 5 | Cross-index test: GGI 2026, KeyID 36 | **Not run** | GGI is not in `data_files_dict`. It would also need item 2 to produce A1. |
| 6 | Cross-index test: SDI 2026, KeyID 1414 | **Not run** | `index_1032` → `SDI_2026` is mapped. Expected result: records flagged in `uce_beyond_bound`, no A1 (calculation-stage bound). |
| 7 | Cross-index test: EPI 2024, KeyID 1606 | **Not run** | Not in `data_files_dict`. The notebook has `index_1034` (EPI 2026); in EPI 2026 the 1606 bounds differ (−0.084 / 0.084). Also depends on Snippet 1 for negative values. |
| 8 | Cross-check against `EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx` | **Not done** | The EGDI result was reviewed manually (section 2) but not reconciled record by record against the fixture. |
| 9 | Vintage mapping for all indexes | **Partly done** | Every mapped vintage was checked against its simulator file: all bound KPIs are present, except `BTI_Q13F` (BTI 2026, a derived KPI) and 1328 (GII 2026). HDI, PHDI and GHI are set to `None` because their raw-file edition is unconfirmed. Their bounds are all calculation-stage, so mapping them would only add `uce_beyond_bound` flags, never A1. HDI and GHI bounds are identical across editions; PHDI bounds differ. |
| 10 | Before/after on other indexes | **Not done** | For indexes where the legacy inferred cap produced A1 on KPIs without a UCE bound, those records will drop out of A1 (most likely into C). Not yet measured. |
| 11 | Upload code and test outputs to the shared Metadata Automation Drive area | **Not done** | |
| 12 | Snippets 1 and 3 | **Out of scope here** | Not part of this change. |

### Proposed fix for item 4 (not yet applied)
Limit A1 to a reviewed allow-list instead of eligibility by bound type:

- Add a reviewed list in `utils/bound_rules.py`, starting with `EGDI_2024` KPIs 271, 274 and 280.
- Only those KPIs can produce A1. All other UCE bounds are still loaded and flagged in `uce_beyond_bound`, but never become A1.
- New KPIs are added to the list only after their interpretation has been reviewed.
- Impact: a few lines in `bound_rules.py`, no change to the EGDI 2024 result, and full compliance with "use A1 only where the DQP interpretation of that bound has been reviewed".

---

## 4. Open questions for review
1. **EGDI 280:** the test matrix calls it a calculation-stage cap, but the regression runner maps `RAW_PRETRANSFORM_CLIP` to report value. Which is correct?
2. **A1 eligibility:** confirm which bound types or KPIs may produce A1. Is it only fixed published caps (EGDI 271/274 and GGI), or also the GII/FII observed-range caps?
3. **A vs A1:** when the latest value is within 1% of the cap (KEN 271, LVA 274), is A1 the preferred label over A?
4. **Calculation-stage A1:** if a record is an exact A match and its raw value is beyond a calculation bound, should it move to A1?
5. **UCE location:** where will the stable metadata location/manifest be, so the CSV extract can be replaced by a direct read?
