# DQP Batch 1 — overview
**Updated:** 15 November 2026 · Details and test results: `Batch1_Summary.md` (this folder)

## What Batch 1 is
Three changes to the Metadata Automation (DQP) pipeline, from `DQP_Batch1_Instructions_for_Alfonso_v2_2026-11-01.md`:

| Snippet | Change | Effect on buckets |
|---|---|---|
| 1 | Approximate matching divides by `abs(report value)`, so negative values no longer match falsely | Yes: GII 2026 loses the 187 false A matches named in the instructions (→ 64 B, 123 C) |
| 2 | A1 (capped) is decided from the UCE bounds before A/B, only for KPIs on a reviewed list (EGDI 2024: 271, 274, 280) | Yes: EGDI 2024 gains 43 A1 records (106 in total); no other index changes |
| 3 | Run date in every output file name, a version number, and a `Run Info` sheet in every workbook | No |

## What is in the repo (`Data Quality/`)
| File | Purpose |
|---|---|
| `Metadata Automation.ipynb`, `metadata_automation.py` | Original pipeline, **version 1.0** (Snippets 1 and 3) |
| `Metadata Automation - Batch 1.ipynb`, `metadata_batch1.py` | Batch 1 pipeline, **version 1.1** (Snippets 1, 2 and 3) |
| `metadata_compare.py` | Compares v1.0 and v1.1 outputs for every index in one workbook |
| `utils/bound_rules.py` | UCE bounds, reviewed A1 list, A1 test |
| `utils/run_stamp.py` | Version, dated file names, `Run Info` sheet |
| `utils/index_files.py` | Index → historical/simulator file, UCE vintage, edition |
| `Changes/Batch_1/` | Handoff files, `Batch1_Summary.md`, this file |

Notebook and script give identical outputs (checked on EGDI 2024).

## How to run
```
python metadata_batch1.py                      # all indices, metadata file only
python metadata_batch1.py --index index_9 --all-outputs
python metadata_batch1.py --no-date            # old file names, overwrite
python metadata_batch1.py --gdrive             # read from / write to the shared Drive
python metadata_compare.py                     # v1.0 vs v1.1
```
Notebooks: set `index_name`, `use_gdrive` and `use_date_in_filename` in the Setup cell.

## Inputs and outputs
- **Inputs:** `Data/Historical`, `Data/Simulator Data`, and reference files in `Data/Reference Data`: UCE bounds CSV, diagnosis template, `metadata_SDG_2026.xlsx`. The data folder is local, or the shared Drive's `Metadata Automation/Data` with `--gdrive` / `use_gdrive`.
- **Outputs:** `Metadata_Automation_<index>_<date>.xlsx`, `Profile_Input_ISPAR_<index>_<date>.xlsx`, `Profile_ESCWA_<index>_<date>.xlsx`; a second run the same day adds `_2`. Each has a `Run Info` sheet: run time, run ID, version, index, edition, script, and the input files with their modified dates.
- **ISPAR input on the Drive:** `Metadata Automation/Country Profiles (ISPAR Input)/` holds **v1.1 (Batch 1) only**.

## Outstanding issues

**To do now**
1. Commit the changes made since `d106bb7`: dated names, versions, Snippet 3 in the notebooks, `Reference Data` paths, `Run Info` layout.
2. Fresh full run of all 24 indices (v1.0, v1.1, comparison), then upload code and outputs to the shared Drive. This is a Batch 1 deliverable.
3. Check `Simulator Data/raw_EGDI_2024.xlsx`: its modified date changed from 12 Aug to 12 Nov during 15 Nov. Confirm the replacement was intended before the fresh run.

**Not done from the instructions**
4. **UCE metadata read directly** (`load_uce_bound_rules`): the CSV extract is used instead, as allowed until the UCE team confirms a stable metadata location.
5. **Calculation-stage A1:** EGDI 280 and GGI 36 are flagged in `uce_beyond_bound` only.
6. **Bounded comparison/calculation value columns:** not produced; raw values are kept.
7. **Test cases not run:** GGI 2026 KeyID 36 (no GGI simulator file) and EPI 2024 KeyID 1606 (no Environmental Performance Index 2024 files).
8. **UCE vintage unconfirmed:** HDI, PHDI and GHI (calculation-stage bounds only, so no A1 effect).

**Deliberate deviations (to agree in the review)**
9. File name carries the run date only, not the reference's `{edition}_{run_id}`.
10. `Run Info` does not show the input fingerprint or file content hashes; they are computed but hidden. The instructions ask for "exact input identities" and a "stable input fingerprint".
11. The code version is a hand-set number (1.0 / 1.1) and must be raised whenever the code changes.
12. A1 is tested against the latest historical value. The EGDI fixture's Philippines 271 case (reference-year logic) is excluded, because older vintage data is not available. 7 further EGDI A1 records rest on the same question.

**Data to confirm**
13. Editions with no year: GHI, HDI, PPHDI, WBL 1.0, DARE. Also `index_1052`: historical file is WPJ 2026, simulator file is WJP 2025. Set in `EDITION_OVERRIDES`.
14. `index_12` edition `EPI_2024` is E-participation; it clashes with the UCE code for the Environmental Performance Index.

**Housekeeping**
15. v1.0 and v1.1 outputs now share file names; keep them in separate output folders (v1.0 runs never go to the ISPAR input folder).
16. Notebooks keep their own copies of the index → file, UCE vintage and ESCWA lists; the scripts use `utils/index_files.py`. Keep them in sync, or make the notebooks import them.
17. Notebooks still load `metadata_SDG_2026.xlsx` (unused) and always require `.env`.
18. Duplicate reference files: the old local copies (`Data/Reference templates/`, `Data/metadata_SDG_2026.xlsx`) and a second Drive copy in `Metadata Automation/Reference Data/` are no longer read.
19. Database runs (`--from-db`) record the environment only; the data read is not fingerprinted.

## Open questions for the review
- EGDI 280: calculation-stage cap or report-value cap?
- Which KPIs go on the reviewed A1 list next (GGI truncation caps, FII 2025, GII 2025/2026)?
- When the latest value is within 1% of the cap (KEN 271, LVA 274), is A1 preferred over A?
- Should an exact A match beyond a calculation bound move to A1?
- Agree items 9–11 above.
