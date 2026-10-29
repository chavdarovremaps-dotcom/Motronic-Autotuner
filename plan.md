# Motronic Autotuner: working plan and handoff

State of the Python port as of 2026-09-23 (evening), kept so work can resume without
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
| ME1.5.5 Opel data | `C:\Users\chavd\OneDrive\Desktop\_Files\opel astra g 2.0 z20let 630cc td04 19t\` (Z20LET, SW 1037360526; `logs\` with one vehicle-logger CSV from 2026-10-15, WinOLS bins, id files; no WinOLS CSV export yet) |
| ME7.6.2 Opel data | `C:\Users\chavd\OneDrive\Desktop\_Files\astra h 2.0 hybrid\` (three vehicle-logger CSVs from 2026-10-14, a WinOLS bin; no WinOLS CSV export yet) |

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
- WinOLS import keeps rpm on the rows of every map whose y axis key says
  rpm. The rpm axis is recognised from its values (increasing, 300 to at
  least 2000) and only in doubt from the export's AxisX / AxisY name and
  unit fields; WinOLS has exported KFURL both ways (032HJ: value lists
  swapped against the names; 362287: rpm on the columns, names empty).
- Maps are stored as the XDF reads them: rows are the y axis. MS43 VE and
  ignition maps have RPM on one axis and MAP or load on the other as the
  XDF says; MG1 timing and fuel scalar maps are load rows by RPM columns.
- MHD logs are converted to bar, Celsius and km/h on read; channel names
  lose their unit brackets.
- Presets carry a `family` key; a preset without one is Bosch ME7. Saved
  presets keep MATLAB spellings (`ALIGN_TIMESTAMPS`, `CWLDIMX`, ...).
- Excel blocks go on sheets by area: Boost, Ignition, Fueling, Airflow. The
  comparison tools read every sheet.
- MG1 compressor feed-forward gates: boost request above 0.5 bar and
  throttle above 70 % (both parameters), |deviation| at most 0.05 bar, no
  gear change within 0.5 s, optional rpm floor (0 = off). The pedal is not
  a condition. A missing
  deviation channel is derived as target minus boost at ingest.
- Automatic axes (ME7 set, 2026-10-29), each behind a tick in Boost &
  Wastegate, default off. KFLDRL / KFLDIMX rpm axis: the spool point is
  the lowest 50-rpm bin whose median relative boost reaches 90 % (parameter)
  of the peak, on WOT rows with duty within 5 % of the highest duty; the
  axis is spool - 1000 .. spool - 250, spool, + 250 .. + 1250, then 500
  steps snapped to multiples of 500 (3300 gives 2300 .. 4550, 5000 .. 7500).
  KFVPDKSD ratio axis: 0.95, 1.0, then even steps to 1.2 x the base-WG peak
  ratio; rows under 1.2 keep the imported map's values at the same rpm.
  Both axes are written as one-row blocks on the Boost sheet.
- KFPBRK / KFPBRKNW (ME7 set, 2026-10-27): per row the factor that makes
  the fitted line hit the logged pressure, f = (rl / KFURL + KFPRG) / ps,
  averaged on the factory grid (rpm by load); VVT off rows feed KFPBRK, VVT
  on rows KFPBRKNW. The value is the full map entry (the logged pressure
  already contains the file's factor), cells without data keep the factory
  value, rows with ps at the 2560 hPa ceiling are dropped. Parameters:
  "Fit KFURL / KFPRG on loads up to" (0 = all loads, today's fit; 80 gives
  the factory structure with the factor at 1 below) and "KFPBRK factor acts
  on" (pressure, the reading of the function frame used here, or load).
  A check table gives the model's pressure error per RPM bin before and
  after. Open: confirm from the FR where the factor enters and that the
  lookup load is rl_w.
- Behaviour changes made on purpose versus MATLAB: the Percent trim mode
  works; the warmup hot threshold and the KFZW VVT split follow the fields
  instead of being fixed at 80 and 18.

## Families

| Family | Maps in | Logs | Generators | Verified |
| --- | --- | --- | --- | --- |
| Bosch ME7 | WinOLS CSV export | ME7-Logger (raw files with preamble, or stripped), TunerPro | boost, handover, warmup, fuel, ignition, manifold model incl. KFPBRK / KFPBRKNW | identical to MATLAB on real logs (KFPBRK is new, unit tests) |
| Siemens MS43 (MS4X) | XDF + bin | TunerPro RT (ON/OFF flags) | closed-loop VE (trims or wideband, paste-ready corrected tables), knock removal on ip_iga_ron98_pl__n__maf | unit tests; VANOS limp-home warning on import |
| Bosch ME1.5.5 Opel (vehicle logs) | WinOLS CSV export (ME7 map names until an export proves otherwise) | vehicle logger, same shape and RAM names as ME7.6.2 | the ME7 six via `families/opel_vehicle.py`; knock from wkrm or worst cylinder (dwkrz_0_A..3_A); overrun rows dropped; zero-WGDC and modelled-ps_w warnings | unit tests; ingest run on the one Astra G log, no maps yet |
| Bosch ME7.6.2 Opel (vehicle logs) | WinOLS CSV export (ME7 map names until an export proves otherwise) | vehicle logger: RAM names, German descriptions, units row, time in ms | the ME7 six on Opel names (nmot, rl_w, wped, pvdkds_w, ps_w, ldtvm, tevfa_w, frm_w, fra_w, tmot, wkrm); overrun rows dropped; modelled-ps_w warning | unit tests; ingest run on the three Astra logs, no maps yet |
| Bosch MG1CS201 (MHD) | XDF + bin | MHD | timing knock removal on main 1/2 and cold 1/2 (average or worst cylinder), Fuel scalar 1 from STFT + LTFT without fuel-cut and shift rows, compressor feed-forward + P chain check; rows near gear changes ignored | unit tests; run on the reference log and on the 2026-09-23 stage 3 logs |

Not started: MED9 (ME7 set plus KFLDHBN, KFVPDKSE with an extra tab), the
OP-COM log source for ME1.5.5 and ME7.6.2, ME3.8, MED17.

ME1.5.5 notes (2026-10-15): the shared Opel declaration lives in
`families/opel_vehicle.py`; ME1.5.5 and ME7.6.2 differ only in the
per-cylinder knock channel names. The Astra G log (TD04-19T, 630 cc
injectors) has ldtvm at zero throughout, so boost maps from it are
meaningless until the wastegate is driven (ask whether the "v2 0wgdc"
file is deliberate); ps_w behaves like a sensor there (never above
pvdkds_w); real knock: wkrm to -4.5 deg, cylinder 1 to -6 deg, 400 of
1116 rows. The ME7.6.2 doubts (wped vs wdk1 for WOT, tevfa_w as te axis,
map names) apply to both.

ME7.6.2 notes (2026-10-14): the Astra logs show rl_w, ml_w and ps_w
inflated on overrun (HFM measures the blow-off flow with the throttle
shut), hence the overrun filter (pedal below 2 % above 1200 rpm, both
parameters). ps_w sits above pvdkds_w in part of the rows, so it is a
modelled value and KFURL / KFPRG from it only reproduce the file; the app
warns on import. wkrm is logged with a negative sign for retard (-0.0 in
the files); dwkrz[0..3] per cylinder exist and are not used yet. pu is not
logged, so CWLDIMX cannot be used until it is. Open: confirm wped (pedal)
rather than wdk1 (throttle) for the WOT split, tevfa_w as the FKKVS te axis,
and the WinOLS map names of the ME7.6.2 file.

## MG1CS201 boost: where we are

Stage 1 done: compressor characteristic corrected by the steady after-P-D
minus base effort on setpoint ratio by MAF req. WGDC; steady P and I per
gear reported; P chain check reproduces the logged P term (0.97
correlation and 0.97 ratio with "Boost deviation RAM"; the filtered "Boost
deviation" gave 0.92 and 0.79 on the reference log).

2026-09-23 stage 3 logs (`...\bmw g05 40i turbosystems\Tune for 95 on Map 1\`,
three MHD logs plus the running bin, PRGID 00005D55465A09, same boost tables
as the reference bin): boost within 0.05 bar of target in single-gear
pulls, spool overshoot 0.03 bar, steady duty 76 to 83 %, I within 0.6 %,
feed-forward error under 0.8 kW. The only big deviations are the shift
spikes in the charge pipe. Verdict: OEM tables control the stage 3 turbo
fine at 1.45 to 1.55 bar; no P edits, rev 1 from the reference log not
needed. Results Excel: `MG1CS201_Tuning_Maps_2026-09-23.xlsx` in that
folder (fuel scalar +5 to +10 % over loads 60 to 200; 29 timing cells pulled
0.5 to 2 deg, the worst at load 90 to 100 around 2000 to 2250 rpm).

Stage 2 next: per-pull boost response report. For each wide-open pull find
the target step, then rise time to 90 percent, overshoot, settling time,
oscillation amplitude and period, steady P and I. Plot target, boost, WGDC
and the P, D, I terms per pull in a new GUI tab; write the numbers to the
Excel. First data: the B58 Turbosystems stage 3 logs the user records on
2026-09-23 and the four G05 40i logs from 2026-09-08.

v3 logs (same day, `...\Tune for 95 on Map 1\v3\`, v3.bin with the
user's rebuilt compressor table): 54 cells corrected, mid ratios 0.5 to
0.85 kW too high, top ratios 0.7 to 1.07 kW too low; 3rd gear runs 0.05
to 0.11 bar under target at high rpm with duty at 80 % and I at 0. P and
D left alone until the compressor table is pasted and relogged. Min
samples per cell for the feed-forward now defaults to 1. Stage 2 must cut
each pull where the target starts dropping, since the "overshoots" seen
so far are lifts and shifts.

Stage 3 after that: guided scaling of the P correction and P factor tables
from the stage 2 numbers, with the factor shown and editable.

The MHD custom WGDC override path (WGDC Base / P-Factor / D-Factor Custom)
is not implemented; the user runs OEM logic and will ask if needed. In the
reference bin those tables are unprogrammed filler.

## Open items

- [ ] Boost stage 2 and 3 as above (stage 3 only if targets rise).
- [ ] Which timing map is active: the logged "Timing Cyl. 1" minus its
      correction does not line up with any of the four maps within a degree
      (residual scatter 16 deg), so the final timing carries corrections the
      maps alone do not explain. Keep pulling all four until a better
      channel (base timing before corrections) is found in MHD.
- [ ] MHD channel checklist lives in docs/mg1cs201_boost_pid.md, relog
      protocol section.
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
