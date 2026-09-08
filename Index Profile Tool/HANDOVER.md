# Handover — Index Selection Profile

For whoever picks this up. Everything needed to run it, extend it, and know what
not to trust yet.

## What this is

A tool that assesses whether a development index is fit to be *adopted* — put in
a plan, given a target, reported against for years. That is a different question
from whether the index is well built, which the composite-indicators literature
already answers.

It never produces an overall suitability score. A decision is weighed, not
averaged, and a single number would hide the trade-offs the choice turns on.

## Start here

```bash
pip install -r requirements.txt
export ISF_DATA_DIR=/path/to/index/files
./verify_install.sh
```

`verify_install.sh` checks Python, the dependencies, the data folder, whether the
published scores still reproduce, then builds both outputs. If anything is
wrong it says which step and why.

Then open `Index_Selection_Profile_Walkthrough.ipynb`. It explains the tool by
running it, and every cell already has its output in it, so it can be read
before it is run. Two variables at the top are the only things to set.

## The three things to know

**1 · The workbook is the seam.** The engine produces
`index_cards_export.xlsx`; everything downstream reads that and nothing
downstream needs the engine. That is why the card deck can be shared without
handing over the instrument, and why the wording can be edited in Excel without
touching Python.

```
engine ──build_export──▶ index_cards_export.xlsx ──build_deck──▶ index_flipcards.html
                              ▲
                       edit the wording here
```

**2 · The self-check is the correctness claim.** For every index with a verified
structure, the engine re-reads the publisher's own file and recomputes *their*
published headline score. If it cannot, the command exits non-zero and names the
index. Run it after any change:

```bash
python -m isf.engine_core.selfcheck
```

Current state: 16 reproduce, 1 resolution-only, 0 fail.

**3 · Five criteria are read, not computed.** Responsiveness, faithfulness,
weighting, stability and comparability come from reading each publisher's
methodology. Each carries a citation, but no outside reviewer has checked them.
This is the largest open item in the project and no amount of code will close it.

## Adding an index

One line in `REGISTRY` in `isf/engine_core/corpus.py`:

```python
"WJP Rule of Law": ("Rule_of_Law_metadata.xlsx", "Rule_of_Law_calc.xlsx"),
```

Re-run `python -m isf.build_export`. The country-level and construction findings
compute at once; the five read-from-methodology criteria show `awaiting` until
somebody reads the documentation. The tool will not invent them.

Add a `VERIFIED_STRUCTURES` entry only once the self-check reproduces the
published score. That entry is a claim the guard checks on every run, so it
should not be made before it is true.

`DATA_FILES.md` lists every file the engine currently reads, its role, its
checksum, and which files in the folder are unused and why.

## What needs fixing in the data, not the code

Three problems, all found by comparing the metadata against the publishers' own
files. None is a code fault and none can be fixed here.

**GovTech is missing seven indicators.** The publisher's 2022 sheet has 201
indicator columns; the metadata has 194 rows per country — identically for all 22
countries, in adjacent columns. That pattern points to one block skipped during
transcription rather than seven separate omissions. `govtech_gap_diagnosis.md`
names which seven. This matters for Somalia specifically, since the MoPIED
documents already quote 201.

**Network Readiness Index has no countries.** The `Arab Countries` column is
empty for all 52 rows, so NRI contributes nothing at country level.

**Three indices have no files at all.** WJP Rule of Law, BTI, and any GovTech
edition newer than 2022 are not in the shared folder.

## Where things are

| File | What it holds |
|---|---|
| `isf/engine_core/rulebook.py` | The criteria, thresholds, purposes. **Read this first.** |
| `isf/engine_core/corpus.py` | Which indices, and the cited evidence behind each reviewed grade |
| `isf/engine_core/selfcheck.py` | The reproduction guard |
| `isf/engine_core/goalpost.py` | The saturation signal — the framework's distinctive finding |
| `isf/wording.py` | Default card text |
| `isf/build_export.py` | Engine → workbook |
| `isf/build_deck.py` | Workbook → deck |
| `isf/paths.py` | Where files come from and go to |
| `legacy_cells/` | The original notebook code, kept for provenance. Not run. |

## Running the tests

```bash
ISF_STRICT_TESTS=1 python -m pytest isf/tests.py
```

`ISF_STRICT_TESTS=1` matters: without it a missing workbook makes some tests
**skip** rather than fail, and the suite can report success while testing very
little. Set it in CI.

127 tests. Several rebuild the whole assessment, so on a machine with limited
memory the full run can exhaust itself part-way; if that happens run it in
groups, as documented at the top of `tests.py`. Every group passes
independently.

## What the tool does not do

Stated plainly, because a tool that hides its limits is worse than one that has
none.

- The five read-from-methodology criteria have never been independently verified.
- A publisher *changing its method* is not detected. The self-check catches a
  moved column; nothing catches a rewritten methodology. That is a scheduled
  human task, and it is how the four methodology breaks in the current corpus
  were found.
- Country-level findings cover the Arab states, because the metadata is a
  regional slice. Calculation findings cover each index's full country set.
- It has never been used in a live selection decision. Its presentation, and
  possibly its structure, should be expected to change once it has.
