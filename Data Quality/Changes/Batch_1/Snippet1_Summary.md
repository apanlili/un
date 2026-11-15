# DQP Batch 1 — Snippet 1 integration summary
**Date:** 15 November 2026
**Scope:** Snippet 1 — negative and zero values in approximate matching.
**Status:** Integrated in commit `3388822` (7 November 2026) and tested on the GII 2026 regression case. Applies to every pipeline (original and Batch 1, notebooks and scripts), because the change is in the shared `utils/formatting_functions.py`.

---

## 1. What was changed

### File
| File | Change |
|---|---|
| `utils/formatting_functions.py`, `get_match_data` | The relative difference divides by `abs(data_report)` instead of the signed `data_report`. |

### Rule
| Case | Before | After |
|---|---|---|
| Negative report value | `value_difference / data_report` is negative, so it always passes `<= 1%` | `value_difference / abs(data_report)`, a true absolute relative difference |
| Exact match, including `0 == 0` | Exact (percentage 0) | Unchanged |
| Non-exact report value of 0 | No percentage (division by zero → NaN), no approximate match | Unchanged |

The zero handling already matched the instructions before this change; only the sign handling is new. No absolute tolerance for zero values was added: the instructions leave that to a separate review per KPI.

What happens to a record that no longer matches is decided by the normal downstream bucket logic. Snippet 1 adds no classification rule.

---

## 2. Test result: GII 2026 (`index_7_2026`)

### Matching level (latest-year approximate matches with a negative report value)
| | Instructions | Result |
|---|---|---|
| Approximate matches under the signed rule | 203 | 203 |
| Genuinely within 1% (absolute relative difference) | 16 | 16 |
| False matches removed | 187 | 187 |

Across all historical years (not only the latest), the signed rule passed all 6,263 non-exact observations with a negative report value; the corrected rule passes 136.

The 97 non-exact observations with a report value of 0 get no percentage-based approximate match.

### Bucket level (full pipeline run, before vs after)
| Bucket | Before | After | Change |
|---|---|---|---|
| A | 9,410 | 9,223 | −187 |
| B | 211 | 275 | +64 |
| C | 268 | 391 | +123 |
| D, E, F, G | 1,225 | 1,225 | 0 |

Exactly 187 records change bucket, all with a negative report value, all on the KPIs named in the instructions:

| KPI | Records moved out of A | Instructions |
|---|---|---|
| 119 | 70 | 70 |
| 118 | 60 | 60 |
| 117 | 57 | 57 |

64 of them find a genuine older-year match (B); 123 have no match within 1% and become C. Row counts are unchanged and no other record moves.

---

## 3. What was not done
| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Absolute tolerance for zero-valued KPIs | **Not in scope** | The instructions require a separate review per KPI before any absolute tolerance is defined. |
| 2 | Broader 1% / older-year matching rule (chance matches to older years) | **Not in scope** | Excluded from Batch 1 by the instructions. |
| 3 | Before/after on indices other than GII 2026 | **Not done** | Only GII 2026 was measured. Any index with negative report values is affected. |
