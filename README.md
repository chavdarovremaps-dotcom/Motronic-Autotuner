# Motronic Autotuner

ECU data logs in, corrected calibration maps out. Reads logger CSVs and a
WinOLS export, fits corrected maps onto the binary's own axes, and writes
them to one Excel sheet laid out cell for cell like WinOLS.

The Python port lives in `motronic_autotuner/`. The original MATLAB app and
scripts stay in `Scripts/` as the reference.

## Setup

Python 3.12 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Run

```bash
python -m motronic_autotuner.apps.me7     # Bosch ME7, maps from a WinOLS export
python -m motronic_autotuner.apps.ms43    # Siemens MS43 (MS4X firmware), maps from XDF + bin
```

Workflow, tab by tab:

1. **ECU Profile**: load a profile JSON or start from the defaults, check the
   logger column names, then import the maps to pull in axes and factory
   values: a WinOLS CSV export for Bosch families, the TunerPro XDF plus the
   car's binary for MS43. Click a map row to view it.
2. **Data Ingestion & Filtering**: pick the folder of raw logs, adjust the
   parameters, and import. Logs are transient-filtered, time-aligned and
   split into Full, WOT, Warmup and Hot.
3. **Calculate**: run every generator, inspect each map, and save the Excel file.

Profiles saved here keep the MATLAB key spellings, so the MATLAB app can still
open them.

## Layout

| Package | Holds |
| --- | --- |
| `core/` | splatting, log ingestion, WinOLS parser, XDF + bin reader, preset JSON, Excel export |
| `generators/` | the math per calibration area: boost, handover, warmup, fuel, ignition, manifold, closed-loop VE |
| `families/` | one module per ECU family: defaults, target maps, log sources, generator list |
| `gui/` | PySide6 window and the three standard tabs, built from the family declaration |
| `apps/` | one entry script per executable |
| `tools/` | `compare_matlab.py` checks a run against an Excel file the MATLAB app produced |

## Tests

```bash
pytest
```

To compare with a MATLAB result on a real log folder:

```bash
python tools/compare_matlab.py "<log folder>" "<log folder>/ME_Tuning_Maps.xlsx" --detail
```
