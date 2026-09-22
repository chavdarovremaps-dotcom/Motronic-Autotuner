# Motronic Autotuner: working plan and handoff

State of the Python port as of 2026-09-23, kept so work can resume without
re-reading the history. Update this file when a stage lands or a decision
changes. The tuning theory for MG1CS201 lives in `docs/mg1cs201_boost_pid.md`;
the design overview is the Claude doc "Motronic Autotuner Overview".

## Where things are

| Thing | Location |
| --- | --- |
| Repo, branch | `D:\Repos\Motronic-Autotuner`, branch `Migration-to-Python`, pushed to origin |
| Python env | `.venv` (Python 3.14, pandas 3); run with `.venv\Scripts\python -m motronic_autotuner.apps.<me7 \| ms43 \| mg1>` |
| Tests | `.venv\Scripts\python -m pytest` (53 tests) |
| MATLAB originals | `Scripts/` (reference only) |
| ME7 golden data | `Scripts/Comparison/` (gitignored): 032HJ preset + prepared logs; MATLAB and Python Excel identical for all 11 maps |
| MS43 data | `C:\Users\chavd\OneDrive\Desktop\_Files\bmw e36 ms43 2.5\` (bin, `long.csv`, `logs_for_calib\`); XDF and ADX in `D:\Repos\BMW-XDFs\MS43\` |
| MG1CS201 reference | `Scripts/MG1CS201/` (XDF 00005D55465A09, `map2 activated.bin`, one MHD log); more MHD logs and bins in `...\_Files\bmw g05 40i turbosystems\` |
| B58/S58 definitions | `D:\Repos\BMW-XDFs\` (MHD+ XDFs with original bins per PRGID) |

## Architecture in one paragraph

One package, one plugin per ECU family, one executable per family. `core/`
is family-neutral: splatting (bilinear, 1D, trilinear), log ingestion with
transient filter and Full/WOT/Warmup/Hot split, WinOLS export parser, XDF
plus bin reader, MHD log reader, preset JSON (MATLAB key spellings kept),
Excel export. `generators/` hold the math and return `CalibrationMap`
objects. `families/*.py` declare defaults, parameters, target maps, log
sources, generators and post-processing; the PySide6 GUI in `gui/` builds
its three tabs from that declaration. Adding a map or a correction to a
family means one `TargetMap` line and one generator wrapper.

## Conventions that must not drift

- A positive fuel error means add fuel. Trims feed the corrected table as
  base times one plus error. Wideband error is measured over target minus
  one, so lean is positive.
- Knock removal averages the retard magnitude per cell over all samples in
  the cell, rounds up to whole map steps, and ignores averages under a
  floor (0.1 degree default) because bilinear weighting leaks slivers into
  neighbouring cells.
- Maps are stored as the XDF reads them: rows are the y axis. MS43 VE and
  ignition maps have RPM on one axis and MAP or load on the other as the
  XDF says; MG1 timing and fuel scalar maps are load rows by RPM columns.
- MHD logs are converted to bar, Celsius and km/h on read; channel names
  lose their unit brackets.
- Presets carry a `family` key; a preset without one is Bosch ME7. Saved
  presets keep MATLAB spellings (`ALIGN_TIMESTAMPS`, `CWLDIMX`, ...).
- Excel blocks go on sheets by area: Boost, Ignition, Fueling, Airflow. The
  comparison tools read every sheet.
- Behaviour changes made on purpose versus MATLAB: the Percent trim mode
  works; the warmup hot threshold and the KFZW VVT split follow the fields
  instead of being fixed at 80 and 18.

## Families

| Family | Maps in | Logs | Generators | Verified |
| --- | --- | --- | --- | --- |
| Bosch ME7 | WinOLS CSV export | ME7-Logger, TunerPro | boost, handover, warmup, fuel, ignition, manifold model | identical to MATLAB on real logs |
| Siemens MS43 (MS4X) | XDF + bin | TunerPro RT (ON/OFF flags) | closed-loop VE (trims or wideband, paste-ready corrected tables), knock removal on ip_iga_ron98_pl__n__maf | unit tests; VANOS limp-home warning on import |
| Bosch MG1CS201 (MHD) | XDF + bin | MHD | timing knock removal on main 1/2 and cold 1/2 (average or worst cylinder), Fuel scalar 1 from STFT, compressor feed-forward + P chain check | unit tests; run on one reference log |

Not started: MED9 (ME7 set plus KFLDHBN, KFVPDKSE with an extra tab), ME7.6
and ME1.5 Opel (two log sources each: OP-COM or vehicle logger), ME3.8,
MED17.

## MG1CS201 boost: where we are

Stage 1 done: compressor characteristic corrected by the steady after-P-D
minus base effort on setpoint ratio by MAF req. WGDC; steady P and I per
gear reported; P chain check reproduces the logged P term (0.92
correlation, 0.79 of logged on the reference log, likely a filtered
deviation).

Stage 2 next: per-pull boost response report. For each wide-open pull find
the target step, then rise time to 90 percent, overshoot, settling time,
oscillation amplitude and period, steady P and I. Plot target, boost, WGDC
and the P, D, I terms per pull in a new GUI tab; write the numbers to the
Excel. First data: the B58 Turbosystems stage 3 logs the user records on
2026-09-23 and the four G05 40i logs from 2026-09-08.

Stage 3 after that: guided scaling of the P correction and P factor tables
from the stage 2 numbers, with the factor shown and editable.

The MHD custom WGDC override path (WGDC Base / P-Factor / D-Factor Custom)
is not implemented; the user runs OEM logic and will ask if needed. In the
reference bin those tables are unprogrammed filler.

## Open items

- [ ] Boost stage 2 and 3 as above.
- [ ] MS43: compare against the MATLAB helper on a clean log (the 2026-09-22
      log had VANOS limp home ON throughout). Axes to paste into the helper:
      rpm 192 448 704 992 1504 2016 2496 3008 3488 4000 4512 4992 5500 6016 6200 6496;
      map 5 10 15 20.001 25.001 30.001 35.001 40.001 45.001 50.002 60.002 70.002 80.003 92.996 110.004 129.996.
- [ ] ME7 warmup maps never compared on real logs (no warm-up rows in the golden set).
- [ ] PyInstaller builds, one exe per family.
- [ ] MED9 family, then the Opel two-source families.

## How to verify a change

- `pytest` for the math, readers and families.
- ME7: `tools/compare_matlab.py <folder> <matlab.xlsx>` or, with both apps
  run on the same preset and logs, `tools/compare_excel.py a.xlsx b.xlsx`.
- MS43 and MG1: run the app or the family's `import_maps`, `ingest`,
  `run_all` on the reference data and read the messages; the Excel is the
  deliverable.
