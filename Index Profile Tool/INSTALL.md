# Installing and running

Nothing here depends on the machine it was written on. Three steps.

## 1 · Get Python 3.10 or newer

```bash
python3 --version
```

## 2 · Install

From the folder containing this file:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

That is enough to run everything. If you would rather have the `isf-` commands
on your path, install the package itself instead:

```bash
pip install -e .
```

## 3 · Point it at the index files

The one thing the package cannot guess. Set it to the folder holding the index
metadata and calculation workbooks:

```bash
export ISF_DATA_DIR=/path/to/index/files     # macOS, Linux
set ISF_DATA_DIR=C:\path\to\index\files      # Windows
```

There is deliberately no default. An engine that quietly reads whatever happens
to be at a fallback path would produce a plausible assessment of the wrong files.

Check it worked:

```bash
python -m isf.paths
```

That prints where it is pointed and lists what it found. If it cannot find the
folder it says so, and says what to do.

## Running

```bash
python -m isf.engine_core.selfcheck     # do the published scores still reproduce?
python -m isf.build_export              # engine   -> index_cards_export.xlsx
python -m isf.build_deck                # workbook -> index_flipcards.html
```

Output goes to `./output` beneath wherever you run the command. Override with
`ISF_OUTPUT_DIR` if you want it elsewhere.

## Running the checks

```bash
python -m isf.engine_core.calibration              # do the thresholds discriminate?
ISF_STRICT_TESTS=1 python -m pytest isf/tests.py   # the full suite
```

`ISF_STRICT_TESTS=1` matters. Without it, a missing workbook makes some tests
**skip** rather than fail, and the suite can report success while testing very
little. Set it in CI.

## If something goes wrong

| Message | What it means |
|---|---|
| `ISF_DATA_DIR is not set` | Step 3. |
| `The index data directory does not exist` | The variable is set but points somewhere else. |
| `No module named 'openpyxl'` | Step 2, or the virtual environment is not active. |
| `pycountry is not installed` | A warning, not an error — country codes will show as `AGO` instead of `Angola`. `pip install pycountry`. |
| `workbook not found` from `build_deck` | Run `python -m isf.build_export` first. |

## The notebook

`Index_Selection_Profile_Walkthrough.ipynb` explains the tool by running it. It
needs the same two things — the dependencies and `ISF_DATA_DIR` — plus one line
near the top pointing at this folder if you open the notebook from elsewhere.
