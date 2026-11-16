# dqp_precheck 0.3 — checks before the Data Quality Profile matching

23 October 2026. Prepared by the Computational Economics Unit.

## What it checks

The checks run on one index and edition, before matching and bucket classification. Nothing is changed silently. Every automatic change is listed in `mappings`, and the original code or ID stays in `ISO_original` and `KPI_original`.

| Area | Check | What happens |
| --- | --- | --- |
| Country codes | Publisher or old ISO code (KSV, WBG, PES, ZAR, ROM, TMP, CTU; CSS in RSF files only) | Converted to the canonical code of the Geographic Reference sheet, logged |
| | Country name written in the code column (Liechtenstein, Lao PDR) | Converted by name, logged |
| | Aggregate or empty column (ZZA.VHHD, Unnamed: 68) | Dropped, listed for information |
| | Second column for the same country (ATG.1) | Set aside, to review |
| | Unknown code | Reported, never guessed |
| | One code written for two entities (CYP for Cyprus and Northern Cyprus) | One line per entity: Cyprus kept as CYP, Northern Cyprus moved to XNC. Flagged for correction at ingestion, not refused; refused only when no separate code exists |
| | Country in the historical file but not in the index (not covered by the publisher) | Listed for information, ESCWA members marked. A country with index values but no historical data is not listed here: it is bucket E of the Data Quality Profile |
| | Publisher list (country sheet of the UCE metadata) against the simulator, both directions | Reported: country ranked by the publisher but missing from the simulator; country in the simulator but not in the publisher list |
| File layout | Historical file with ISO codes in row 2, extra identifier columns (category), header spellings (KeyId, Year), a female and a male series under one KeyID | Read correctly, each change listed as an item to correct in the file |
| Rows and values | Duplicate rows in the simulator (same value / different values) | One kept / refused |
| | Two values for the same country, KPI and year in the historical file | One line per country and year, with both values and series names |
| | Text in a value cell (.., n/a) | Reported, read as missing |
| KPI traceability | KPI ID format: a number, or a number followed by _female or _male; trailing .0 removed | Cleaned and logged, or reported |
| | KPI missing from the historical file, the metadata file, the UCE indicators sheet or the canonical KeyID list; KPI in metadata but not in the simulator; ID twice in metadata; one ID with several names | Reported |
| | KPI not reconciled: index values found in the historical file for fewer than half of the countries | Reported, with a diagnosis (historical file too old, constant ratio, close but not equal, different series) and three examples |
| Values across countries, KPIs and years (rules in `crosschecks.py`) | A country's value pasted on another country's row: A's index value is not in A's own source series, but equals exactly the source value of one other country B at the year most countries are on. Flagged when the value has 4 significant digits or more and is not a simple fraction (1/3, 15/8...), or when the same pair A, B occurs in two KPIs or more | To review, with both values |
| | Rows shifted: at least 5 countries, and at least half of the countries not found in their own series, carry the value of the country next to them in the file | To review |
| | Two KPIs swapped: for a KPI not reconciled, the index values are found in another KPI's series for at least half of the countries; "probably swapped" when it works both ways; "shifted by one KeyID" when three KPIs or more each find their values under the next KeyID | To review |
| | Unit for one country: the value is 100 times (or a hundredth of) the source value, at the year most countries are on (±1 year, 0.5% tolerance), while the other countries match without factor | To review |
| | Year labels shifted: the year the publisher used, as found in the historical file, is later than the edition; or, against the previous historical file, at least 60% of the shared values moved by the same number of years | To review |
| Units and editions | Power-of-ten factor between the files | Applied in `h_scaled` only, logged, to confirm in metadata; a factor confirmed in metadata is used as given |
| | Simulator and historical file labelled with different editions | Reported |
| | Source years after the index edition | Reported (they cannot make an index value old) |

Not covered, on purpose:
- caps and goalposts: the Data Quality Profile handles them from the goalposts in the metadata;
- a country with index values but no historical data: bucket E of the profile, information for member states;
- a check of the raw scale against `output_scale` in the UCE metadata. `output_scale` is the scale of the written score (written score = internal score × output_scale + output_offset; 100 for every KPI of the SDG Index), not a factor between source and index values. The factor between the files is detected from the data and must still be confirmed: it needs its own column in the metadata.

All rules are deterministic: no model, no learning. Each flag can be checked by hand from the two values shown.

## How your code calls it

```python
import sys; sys.path.insert(0, '<folder holding the packages>')
from dqp_precheck import run

from dqp_precheck.readers import read_simulator, read_historical, read_uce_metadata
sim = read_simulator('raw_WPF_2026.xlsx'); hist = read_historical('historical_data_index_1036_WPF_2026.xlsx')
r = run(sim, hist, meta=meta, index_id='1036', edition=2026,
        uce_meta=read_uce_metadata('metadata_WPF_2026.xlsx'),   # publisher list and KeyIDs, when the file exists
        hist_previous=None,           # previous historical file of the index, long table, when available
        canonical_kpis=None,          # canonical KeyID list for the index, when available
        confirmed_scale=None)         # {KPI: factor} confirmed in the metadata, when available
if r.status == 'refuse':
    raise SystemExit(r.issues[r.issues.severity == 'refuse'])
sim, hist = r.sim, r.hist            # use these for matching; compare v with h_scaled
```

Inputs are long tables:

| Table | Columns | Content |
| --- | --- | --- |
| sim | ISO, KPI, v (+ Country, KPI name) | the simulator file |
| hist | ISO, KPI, year, h | the historical file |
| meta | KPI | the metadata file, optional |

Outputs, in a `Result`:

| Field | Content |
| --- | --- |
| `status` | `refuse` (fix the file and run again), `review` (usable, items listed for a person) or `pass` |
| `sim`, `hist` | cleaned copies |
| `issues` | one row per problem: check, severity, KPI, ISO, n, detail |
| `mappings` | every automatic change |
| `kpis` | per KPI: where it appears, scale factor, share of countries found |
| `coverage` | the 22 ESCWA members, present or absent (information only: coverage is the publisher's decision) |

`readers.py` reads the raw_ simulator, the historical file and the UCE metadata as they are on Drive. `run_precheck.py jobs.csv out_dir` runs all indices listed in a jobs file.

## Tests

`python -m dqp_precheck.tests` runs 30 known-answer tests. Each test uses a problem met in the ISPAR files or planted in the training files, plus one test that clean data raise nothing. All 30 pass.

On 34 index editions (25 October). For NRI, AI Readiness, TTDI and the Global Development Index, which have no raw_ file, the simulator file was converted from the calculation workbook with `convert_workbooks.py`. ODIN and the Public Administration Index are not run (no historical values, no simulator file).
- Historical files come in two layouts: in 17 files the ISO codes are in row 2, not row 1. The profile code reads row 1 as codes and finds no match at all in those files (everything in bucket E). The reader now detects the layout and says so.
- Global Gender Gap Index 2026: the simulator writes 26_FEMALE, and the historical file puts the female and male series under the same KeyID (26), the sex written only in the series name. The profile code matches 2% of the values; after the precheck cleaning, 60% (the rest are ratios computed by the publisher, with no source series).
- Women, Business and the Law 2.0: 22 KPIs are 100 times the source. Matched 80% before cleaning, 99% after.
- World Press Freedom Index 2026: in the historical file now on Drive, the five series sit one KeyID too low (Political missing, Safety repeated). The profile code classifies many of these values as "old" through approximate matches with the wrong series.
- No file is refused. Cyprus and Northern Cyprus (WPF): one line each, flagged.

## Files and links

| What | Where |
| --- | --- |
| Geographic Reference sheet (country codes, aliases, code history) | [ISPAR Geographic Reference & Publisher Mappings](https://docs.google.com/spreadsheets/d/14h3wBxybtJOIESW9TVlh3TilrJLnLMUszZSobQEFioI/edit) |
| Snapshots of that sheet, used when it cannot be read | `reference/*_snapshot_2026-10-23.csv` |
| Index metadata files | [Metadata_KPI_simulators](https://drive.google.com/drive/folders/121u9zLioF3Gv5MP3Kzf51YR5J16ABziz) |
| Your pipeline folder | [Metadata Automation](https://drive.google.com/drive/folders/1EF1mJ3XCB7MRkguOnc3_QEEduJMTbu75) |
| Note to the Generator on country codes (file corrections) | [UCE_note_to_Generator_country_codes_2026-10-19.md](https://drive.google.com/file/d/1uOruz1Bn2jG2a4YIW6ivnMNaVXhTqdiV/view) |

`ispar_reference` holds the country-code logic shared with `dqp_whatif`, the score and rank module used after your code. Read the codes from the sheet with `CountryCodes.from_reference('<sheet exported as .xlsx>')`; without an argument, the snapshots are used.

## What we ask

- Call `run()` before your matching, and do not copy its code into the notebook. When we change a check, you update the package and nothing else.
- Use `h_scaled` for matching, and keep `h` in your outputs.
- Send us any problem that `run()` misses, with the file where you met it. We add it as a test.
