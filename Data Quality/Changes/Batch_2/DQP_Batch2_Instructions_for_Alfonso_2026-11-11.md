# DQP MVP1 — Batch 2 integration instructions for Alfonso
**Prepared:** 6 November 2026; revised 11 November 2026 (this version replaces the 6 November package)  
**Baseline:** your current DQP code, including the Batch 1 changes you have integrated.  
**Scope:** roadmap issues 8, 10 and 11 only.

Batch 2 deliberately does **not** change the general historical matching rule (issue 3) or Bucket D (issue 7), which need separate methodological closure. It also leaves KPI identifiers and the outlier routine unchanged.

## Files

1. `DQP_Batch2_Reference_Snippets_2026-11-11.py`
2. `DQP_Batch2_Regression_2026-11-11.py`
3. `DQP_Batch2_Full_Results_2026-11-11.json`
4. `DQP_MVP1_Batch2_Test_Matrix_2026-11-11.xlsx`

The universal pre-check remains upstream of your DQP code. Where the pre-check already solves identity/mapping, consume its result rather than reimplementing the same logic.

---

# Snippet 1 — save country-code checks in both directions
**Roadmap issue 8**

## Problem

Country-code discrepancies can disappear silently when files are merged. The current notebook checks some KPI coverage, but it does not save a persistent country-presence audit showing:

- countries in both simulator and historical source;
- countries only in the simulator;
- countries only in the historical source;
- any country code that remains outside the canonical reference after the pre-check.

## Division of responsibility

The **universal pre-check** remains responsible for canonicalisation and approved aliases (for example PES→PSE or TZN→TZA). Do not duplicate those alias rules inside the DQP.

Your DQP should receive the canonical ISO values and **save the audit evidence**.

## Reference output

The reference function creates one row per canonical ISO:

- `ISO`
- `in_simulator`
- `in_historical`
- `presence_status = BOTH / SIMULATOR_ONLY / HISTORICAL_ONLY`
- `canonical_iso_status`

Please save this table with the DQP output, e.g. a sheet named `Country code audit`.

## Real regression cases

Using the same upstream pre-check logic:

- **WPS 2025:** 175 countries in both; 6 simulator-only; 1 historical-only (`GNQ`).
- **FII 2025:** 138 in both; 1 simulator-only (`XKX`); 47 historical-only.
- **EGDI 2024:** 192 in both; 1 simulator-only (`SWZ`); none historical-only.
- **GII 2026:** 139 in both; no difference in either direction.

These are not automatically errors. The purpose is to make the coverage difference visible and auditable.

## Acceptance

1. aliases already approved by the pre-check do not reappear as false missing countries;
2. both directions are saved, not merely printed;
3. a code not resolved by the canonical reference remains a review item rather than being silently dropped.

---

# Snippet 2 — percentages must mean percentages
**Roadmap issue 10**

## Problem

The current grouped profile function labels columns `(...) (%)` but stores fractions.

Example from current outputs:

- WPS 2025: current maximum in a column labelled `%` = `0.96`; corrected display = `96.13`.
- FII 2025: `0.99` → `99.28`.
- EGDI 2024: `0.99` → `99.48`.
- GII 2026: `1.00` → `100.00`.

This is purely a presentation/semantic bug.

## Reference correction

For user-facing summary/profile tables:

- a column labelled `%` is always on a **0–100** scale;
- grouped bucket percentages should sum to approximately **100%** (allowing rounding);
- the internal relative-difference ratio used for matching may remain a ratio internally.

For the exported metadata workbook, avoid showing a ratio under a percentage label:

- rename the exported internal ratio to `value_difference_ratio_inferred`;
- add `value_difference_pct_inferred = ratio × 100`.

This export change does not alter the matching calculation.

## Acceptance

Across the supplied tests:

1. every user-facing `%` value is between 0 and 100;
2. grouped bucket percentages sum to ~100%;
3. `0.0061` internal ratio is exported as `0.61%`, not as a column misleadingly labelled `0.0061%`;
4. bucket counts are unchanged.

---

# Snippet 3 — explicit country coverage
**Roadmap issue 11**

## Problem

When a country profile is requested for a country that the index edition does not cover, the current code produces an empty or broken country profile instead of stating that the country is not covered.

## Reference correction

Before writing country profiles, create a coverage table for the requested countries, with one status per country:

- `AVAILABLE`
- `NOT_COVERED_BY_INDEX_EDITION`

Generate country sheets only for `AVAILABLE`. Save the coverage table with the DQP output.

Known examples:

- **GII 2026:** Somalia is not covered.
- **FII 2025:** Somalia is not covered.
- **WPS 2025:** Somalia is covered.
- **EGDI 2024:** Somalia is covered.

For an unavailable country, the output should explicitly say `NOT_COVERED_BY_INDEX_EDITION`; it should not create an empty or broken country profile.

There is also a small latent bug in the current writer: the skip message refers to an undefined variable `country`; it should use `country_iso`.

## Out of scope

Outlier detection stays in the DQP run as it is. Batch 2 does not change the outlier routine, the `outlier_detected` column or the `Outliers data` sheet.

## Acceptance

1. every requested country gets exactly one coverage status;
2. unavailable countries are not sent to the country-sheet writer;
3. a request for Somalia in GII/FII is handled cleanly as not covered, while WPS/EGDI remain available;
4. the skip message runs without error;
5. bucket results are unchanged.

---

# Regression scope already completed

The reference Batch-2 functions were tested against the same portfolio standard used for Batch 1:

- all **29** current Generator candidates;
- **25** additional older UCE vintages in the same index families;
- **54** structured index/vintage tests in total;
- zero reference-test failures.

The four real DQP country-code cases above were also rerun directly from the current simulator/historical pairs. GII 2026 and EGDI 2024 were rerun on 11 November 2026 on the corrected historical files (GII 2026 historical file of 9 November, EGDI 2024 historical file of 11 November), with the same results.

---

# What to show at the Batch-2 review

Please upload the updated code and test outputs to the shared folder.

At the short review, please show:

1. one saved `Country code audit` output, including a case with a one-sided coverage difference;
2. one before/after profile percentage table;
3. GII or FII Somalia returning `NOT_COVERED_BY_INDEX_EDITION`;
4. any intentional deviation from the reference logic and why.

You are free to integrate the functions in the structure that best fits your code. The reference snippets define the expected behaviour, not the exact notebook layout.
