# DQP MVP1 — Batch 1 integration instructions for Alfonso
**Date:** 1 November 2026  
**Deadline for integrated code and test outputs:** Tuesday 3 November 2026, 12:00  
**Scope:** three contained changes only. Broader matching logic, Bucket D and explicit database vintage selection are not part of this batch.

## Files in the handoff

1. `DQP_Batch1_Reference_Snippets_v2_2026-11-01.py`  
   Reference implementation for the three changes plus a small UCE metadata adapter.

2. `DQP_Batch1_Full_Portfolio_Regression_2026-11-01.py`  
   Re-runnable acceptance suite.

3. `DQP_Batch1_Full_Portfolio_Results_2026-11-01.json`  
   Frozen results from the full run.

4. `DQP_MVP1_Batch1_Test_Matrix_v2_2026-11-01.xlsx`  
   Human-readable acceptance matrix.

5. `DQP_UCE_Bounds_Extract_v41_2026-11-01.csv`  
   **Derived convenience extract only.** It is generated from UCE standardized metadata and is not a second source of truth.

6. `EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx`  
   Regression fixture for the known EGDI A1 ordering case.

## Acceptance universe already tested

The reference changes were tested on **all 29 index/vintage candidates produced by the Simulator Generator** and on **25 additional older UCE vintages in the same index families**: 54 vintages in total.

The final reproducible run exercised:

- 398,706 raw numeric observations;
- 3,348 negative observations;
- 49,268 zero observations;
- 1,766 metadata-defined bound rules;
- 7,778 real observations beyond a metadata-defined bound;
- zero test failures.

The older vintages are regression protection. They are not extra implementation deliverables for you.

---

# Snippet 1 — negative and zero values in approximate matching

## Problem

The current DQP percentage difference divides by the signed report value. When the report value is negative, the ratio is negative and can pass a `<= 1%` condition even when the true absolute relative difference is much larger.

## Reference correction

- denominator = `abs(report value)`;
- exact equality remains exact, including `0 == 0`;
- a non-exact report value of zero does **not** receive a percentage-based approximate match unless a separately reviewed absolute tolerance is later defined for that KPI.

This fixes only the sign/zero defect. It does **not** close the broader roadmap issue on chance matches to older years.

## Required use case: GII 2026

Use the supplied GII 2026 case as a before/after regression test.

In the current DQP output:

- 203 negative observations are labelled approximate matches;
- 187 of them are false solely because the denominator is signed;
- only 16 are genuinely within 1% on an absolute-relative basis;
- false cases are concentrated in KPI 117 (57), KPI 118 (60) and KPI 119 (70).

After integration, the 187 sign-driven false approximate matches must no longer pass the 1% numerical test. What bucket they ultimately enter is determined by the normal downstream DQP logic; this snippet does not invent a new classification rule.

---

# Snippet 2 — apply authoritative cap/floor evidence before final A/B/C classification

## Source of truth

The automated Python index-calculation work (UCE / Simulator Generator) produces standardized metadata files for each index vintage. These metadata files are the intended canonical source for calculation bounds and normalization rules.

**Do not create a second manually maintained cap/floor list in DQP.**

For this Batch 1 test:

- the supplied CSV is a flat, generated extract for convenience and review;
- the reference code includes `load_uce_bound_rules(...)` / `extract_uce_bound_rules(...)` so DQP can read the standardized metadata directly;
- the UCE root is passed as a parameter rather than hard-coded.

The UCE/Generator team is being asked to confirm one stable downstream metadata location/manifest. Until that is frozen, use the supplied extract for testing and keep the adapter path configurable.

## Important distinction

A UCE goalpost/cap/floor proves a **calculation treatment**. It does **not** automatically prove that the DQP record should be labelled A1.

Therefore:

1. preserve the historical/raw value;
2. apply the authoritative bound in the correct comparison/calculation space;
3. use A1 only where the DQP interpretation of that bound has been reviewed.

## Core EGDI regression

Use `EGDI_A1_Reconciliation_Explained_2026-10-26.xlsx`.

- KeyID 271 — upper cap 120;
- KeyID 274 — upper cap 120;
- KeyID 280 — upper cap 100 before the z-score.

The current ordering can allow an ordinary A/B/C match to be assigned before the cap evidence is considered. The reference logic tests the authoritative bound first while preserving the raw evidence.

## Three additional cross-index cases

Please also test the integration on these deliberately different cases from the standardized UCE metadata:

1. **GGI 2026 — KeyID 36, Healthy life expectancy**  
   `truncate`, upper cap **1.06**; 29 current raw observations are above the cap.

2. **SDI 2026 — KeyID 1414, Mobile broadband subscriptions per 100 population**  
   upper goalpost **100**; 71 current raw observations are above it.

3. **EPI 2024 — KeyID 1606, adjusted emissions growth rate for sulfur dioxide**  
   lower goalpost **-0.03943723**; 63 current raw observations are below it.  
   This is useful because it combines a negative-valued KPI with a lower-bound rule.

These examples are integration tests, not a direction to turn every bounded observation into A1.

---

# Snippet 3 — reproducible run stamp and non-overwriting outputs

Every DQP output should carry enough information to reproduce the run:

- code version;
- index and edition;
- exact input identities;
- run timestamp / run ID;
- stable input fingerprint.

A later run must create a new output filename rather than silently overwrite an earlier file.

This is an infrastructure change only; it does not change DQP classification.

---

# What to deliver by Tuesday 3 November, 12:00

Please:

- integrate the three changes cleanly into your current 26 October code;
- upload the updated code and the resulting test outputs to the shared Metadata Automation Drive area;
- run the supplied use cases, including the GII 2026 negative-value case and the EGDI + three additional bound cases.

We will have a short review meeting after the upload. During the meeting, please show:

1. the before/after result of the regression cases; and
2. any place where you intentionally changed the reference logic, with the reason.

You do not need to reproduce the reference file structure exactly. A documented function/helper or a clearly labelled separate cell is fine if it fits your code better.

## Not in this batch

- redesign of the general 1% / older-year matching rule;
- Bucket D redesign;
- explicit database vintage selection (MVP2);
- explanation agent;
- post-DQP score/rank materiality.
