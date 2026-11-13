# DQP Batch 1 — Snippet 3 integration summary
**Date:** 13 November 2026
**Scope:** Snippet 3 — reproducible run stamp and non-overwriting outputs.
**Status:** Implemented in the script versions of the pipeline (`metadata_automation.py`, `metadata_snippet2.py`, `metadata_compare.py`) and tested. Not committed yet.

Snippet 3 is an infrastructure change only. No DQP classification logic changed: on EGDI 2024 (`index_9`), every sheet of all three output files (metadata, ISPAR input, country profiles) is identical, cell for cell, to the output from before Snippet 3, apart from the new `Run Info` sheet.

---

## 1. What was changed

### Files
| File | Change |
|---|---|
| `utils/run_stamp.py` | **New.** Run stamp helpers, based on `make_run_manifest` in `DQP_Batch1_Reference_Snippets_v2_2026-11-01.py`. |
| `utils/batch.py` | Shared batch runner. Fingerprints every index before the run starts, creates the run folder, passes each index's manifest to the pipeline and writes `manifest.json`. |
| `metadata_automation.py` | Adds a `Run Info` sheet to every output workbook and refuses to overwrite an existing file. |
| `metadata_snippet2.py` | Same as above. The Snippet 2 settings (A1 mode, UCE vintage, UCE bounds CSV) are part of the fingerprint. |
| `metadata_compare.py` | Same run folder and `Run Info` treatment. Reads the newest run folder of each input folder and records the run ID of every file it compares. |
| `utils/index_files.py` | Adds an edition per index (`edition()`), taken from the simulator file name, with `EDITION_OVERRIDES` for corrections. |

The notebooks are unchanged and do not have Snippet 3.

### `utils/run_stamp.py`
| Function | Purpose |
|---|---|
| `code_version(script)` | Git commit of the code (with `-dirty` when there are uncommitted changes) plus a SHA-256 of the `.py` files actually used. |
| `file_input(role, path)` | Identity of one input file: role, name, size and SHA-256 of its content. |
| `make_run_manifest(...)` | Run record for one index: run ID, timestamp, index, edition, code version, inputs, options and the input fingerprint. |
| `new_run_folder`, `ensure_new` | Create a new run folder / check an output file does not exist. Both raise an error instead of overwriting. |
| `run_info_df`, `append_run_info` | Build and write the `Run Info` sheet. |
| `read_run_id` | Read the run ID back from a workbook (used by the compare script). |
| `write_manifest_json` | Write `manifest.json` for the run folder. |

### What is recorded for each index
| Item | Example |
|---|---|
| Code version | `36dcd71+src-7bbef93e` (git commit + hash of the code files) |
| Index and edition | `index_9`, `EGDI_2024` |
| Input files | historical, simulator; plus UCE bounds CSV (Snippet 2, UCE mode) and profile template (when country profiles are written). Each with name, size and SHA-256. |
| Options that change results | `escwa_only`, `data_source` (`excel` or `db:<env>`); Snippet 2 adds `a1_logic` and `uce_vintage` |
| Input fingerprint | SHA-256 of code + inputs + options. Same for identical runs; changes when anything changes. |
| Run ID | `DQP_index_9_EGDI_2024_20261113T092937Z_4cce7b72` (index, edition, UTC time, fingerprint) |

### How the outputs change
- **Run folders.** Each run writes into a new subfolder named `<local date-time>_<batch fingerprint>`, e.g. `20261113-172937_f6951526`. File names inside are unchanged. A rerun creates a new folder, so earlier outputs are never replaced.
- **`manifest.json`** in each run folder: every index with its run ID, inputs, options, output files and status (`ok`, `failed`, `skipped`). It is written even if the run fails part way.
- **`Run Info` sheet** added at the end of every workbook, so the provenance stays with the file when it is moved or emailed. All other sheets are unchanged.
- **Overwrite guard.** Writing to an existing file or run folder stops with an error.

Example layout after two runs with the same code, inputs and options:
```
Metadata Automation - script/
    20261113-172937_f6951526/
        Metadata_Automation_index_9.xlsx
        Metadata_Automation_index_12.xlsx
        manifest.json
    20261113-173018_f6951526/      <- same fingerprint suffix: identical rerun
        ...
```

---

## 2. Test results
Tested on copies of the scripts, with outputs written to a scratch folder (inputs read from the normal data folders).

| Check | Result |
|---|---|
| Same inputs run twice (`index_9`, `index_12`, all three outputs) | Same input fingerprint, different run IDs, both run folders kept |
| Same input files copied to a different folder | Same fingerprint (content-based, not path-based) |
| One cell changed in the historical file | New fingerprint |
| Snippet 2 UCE mode vs `--legacy-a1` on the same files | New fingerprint |
| Write to an existing output file / run folder | Blocked (`FileExistsError`) |
| Outputs vs before Snippet 3 (`index_9`: metadata, ISPAR input, country profiles) | Identical except the new `Run Info` sheet; all 16 outlier plots kept |
| Compare script on run folders | Picks the newest run folder of each input and records each input's run ID |
| Repo version, uncommitted | Code version shown as `36dcd71-dirty+src-…` with a warning, as intended |

This matches the Snippet 3 check in `DQP_Batch1_Full_Portfolio_Regression_2026-11-01.py` (same fingerprint, different run ID).

---

## 3. Differences from the reference and what was not done

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | New output filename per run (`Metadata_Automation_{index}_{edition}_{run_id}.xlsx`) | **Deviation** | A new run folder per run instead; file names stay unchanged. The reference name repeats index and edition (~90 characters). Folders keep names short, group the files of one batch, and let the compare script pair files by index. Nothing is overwritten either way. |
| 2 | Fingerprint covers index, edition, code version and inputs | **Extended** | Also covers the options that change results. Without this, a UCE run and a `--legacy-a1` run on the same files would have the same fingerprint. |
| 3 | Code version | **Extended** | Git commit alone does not identify uncommitted code. A hash of the `.py` files is added and used in the fingerprint. |
| 4 | Drive inputs (`drive_inputs`: file ID, modified time) | **Not done** | Inputs are read from local or synced folders and hashed as files. |
| 5 | Database runs (`--from-db`) | **Partly done** | The database environment is recorded (`data_source: db:<env>`), but the data read from the database is not fingerprinted, so these runs are not reproducible from the stamp alone. |
| 6 | Notebooks | **Not done** | Snippet 3 is only in the `.py` scripts. |
| 7 | Edition for every index | **Partly done** | Taken from the simulator file name. Needs confirming: GHI, HDI, PPHDI, WBL 1.0 and DARE have no year; `index_1052` historical file says WPJ 2026 but the simulator file is WJP 2025; `index_12` comes out as `EPI_2024` (E-participation), which clashes with the UCE code for the Environmental Performance Index. Fix in `EDITION_OVERRIDES`. |
| 8 | Upload code and test outputs to the shared Metadata Automation Drive area | **Not done** | |

### Notes
- Outputs written before Snippet 3 sit directly in the output folders, not in run folders, and have no `Run Info` sheet. They are not touched. The compare script uses the newest run folder when one exists; to compare older files, point `--dir1` / `--dir2` at them.
- Run folder names use local time; run IDs and timestamps inside use UTC.

---

## 4. Open questions for review
1. **Run folders vs file names:** is a new run folder per run acceptable in place of a new file name per output?
2. **Fingerprint scope:** agree that run options (A1 mode, ESCWA-only, data source) belong in the fingerprint?
3. **Editions:** confirm the editions for GHI, HDI, PPHDI, WBL 1.0, DARE and `index_1052`, and a naming convention that avoids clashes with UCE vintage codes (e.g. E-participation vs EPI).
4. **Database runs:** should the stamp also fingerprint the data read from the database, or is recording the environment enough for MVP1?
