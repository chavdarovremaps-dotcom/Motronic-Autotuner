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
- WinOLS import: an ``eZweiInv`` (inverted) map's value list runs along
  the x list first in newer exports (360288, 362287) and along the y list
  first in older ones (032HJ, 018J), told apart by whether the axis called
  rpm holds rpm values; ``Columns`` / ``Rows`` do not describe the value
  order. Profiles saved before 2026-10-29 hold scrambled or transposed
  KFURL / KFPRG / KFVPDKSD base maps: re-import the export.
- WinOLS import, 2026-11-04: an axis the export names or units as rpm
  (Motordrehzahl, U/min, Upm, 1/min) counts as rpm from 0 rpm upwards. The
  300 rpm floor holds only for unnamed axes. Before this, the ME7.6.2
  KFPRGE and KFVPDKSE (rpm from 0) were read in the wrong value order, and
  "Upm" was not known as a unit. That also fixes inverted maps with an
  Upm axis in the 032BJ and 362287 exports: KFKHFM and KFFWLW were read
  down the y list. The 032BJ "KFKHFM x expected / measured" block from
  2026-11-02 used the scrambled KFKHFM; its error and VE tables did not.
  The reference exports in Scripts/ExportsFromWinols read exactly as
  before.
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
- ME7 wastegate logs: the user forces the N75 output to fixed duties
  (0, 10, 20 ... 95 %) while logging, so ldtvm, the modulated duty the
  valve receives, is the duty source for KFLDRL and is quantised, while
  ldtv (the PID output) sits at 95 % and means nothing in such logs.
  Never use the duty as a condition for anything (spool, steady state).
- KFLDRL (ME7 and the Opel families, 2026-11-02), on by default:
  - Each rpm row is interpolated between the duty levels logged at that rpm.
    The levels are rounded to whole percent and need at least 3 samples.
  - Boost is made to rise with duty by an isotonic fit, so a stray point is
    pooled with its neighbours.
  - A column within a quarter step above a row's top boost takes the top
    duty.
  - This replaces the splat's flat treads, where one forced level filled two
    columns with the same duty.
  - Then the finish, after the user's hand edits on the Seat Leon 1.8T
    (366426):
    - Column 0 is 0 %.
    - Rows rise with the target.
    - Holes are linear in boost.
    - Spooled rows reach 90 % (the spool share) of the highest boost of any
      row. Their unreached targets get the highest duty logged in those rows.
    - The row just below the first spooled row takes that row's duties.
    - Rows further down get 95 %, with the first unreached cell bridged at
      the spool-side row's highest duty.
  - On the Leon this is within 1.6 % duty of the hand map from 2750 rpm up.
    The spool row lands one row later than the hand map (2750 instead of
    2500), because the splat had credited 2950 rpm samples to 2750.
  - The splat and the old fill stay selectable.
  - The PID duty-ratio mode only uses cells with log weight.
- Settings panel: ParamSpec has section, unit, tip and enabled_when.
  - A family that names sections gets one tab per section, scrolling on its
    own.
  - ME7 and the Opel families have General, Boost and Airflow tabs.
  - Labels are short, and the long explanation is in the tooltip.
  - The safety_margin field is gone from the form: it was never applied,
    not even in MATLAB.
- MAF check (ME7, 2026-11-02), information only: ml_w against the airflow
  at a reference VE (90 %, parameter) from pvdks_w (not ps_w, which is the
  ECU's MAF-based model), tanslin (after the intercooler on the 1.8T) and
  the displacement (1781 cc), ideal gas law, rows with wdkba >= 95 %, rows
  with the pressure or airflow at a sensor ceiling left out. Error and
  implied VE are averaged on the KFKHFM grid (nmot by rl_w, the ECU's own
  lookup); a "KFKHFM x expected / measured" block is shown for information
  only, since KFKHFM changes the load and everything after it. The
  ME7-Logger units row is kept (df.attrs["units"]); ml_w in kg/h is
  converted to g/s at ingest. The user's Excel sheet for this had a
  missing bracket (density not interpolated), divided by Patm and used
  1000 hPa for a 1013 hPa density table.
- Boost PID (ME7, 2026-10-29). KFLDRQ0 / Q1 / Q2 and the curve LDRQ1ST
  share one ROM rpm axis; all four go onto the KFLDRL rpm axis (the auto
  spool axis when ticked), Q1 / Q2 / LDRQ1ST keeping their values at the
  same rpm. P (KFLDRQ0, same value in all four deviation bands) comes from
  the forced-duty logs: per rpm point the mean boost per duty (rounded to
  1 %, at least 10 samples), the steepest rise between duties at least 4 %
  apart normalised to 10 % duty, P = 1000 / that rise (200 hPa per 10 %
  gives 5 %/100 hPa). Points below the spool rpm take the first P after
  it; gaps after it are interpolated. I and D are set by hand from there.
  The duty-ratio rule (scale all three by logs / file duty from KFLDRL)
  stays as a choice. KFLDRAPP is only used for open-loop logging (code
  word set to 8) and is never touched. The in-between duties in the logs
  (15 to 33 % at 5100 to 6500 rpm) are KFLDRAPP interpolating between its
  rpm rows, held a fraction of a second each. The PID rpm axes of both ME7.5
  layouts are bytes in 40 rpm steps (1000, 1240, 1520 ...), so the KFLDRL
  axis is rounded to them before the maps move (2026-11-06).
- 512 kB ME7.5 layout (06A906032S, HW 0261206197, SW 352760, narrowband;
  `...\_Files\seat leon 1.8t s3 setup\`, 2026-11-06). Same KFLDIMX /
  KFLDRL / KFVPDKSD / FKKVS / KFZW / KFFWL(W) names; KFZW and KFKHFM with
  byte axes.
  - Boost PID: LDRQ0DY and LDRQ1DY (dynamic P and I, curves) and LDRQ1ST
    share one 16-point axis. LDRQ0S is a single stationary P (2.0; the
    export cannot carry it). KFLDRQ2 is 4 x 8 on an rpm axis of its own.
    The stock LDRQ0DY / LDRQ1DY are exactly a KFLDRQ0 / KFLDRQ1 column of
    the 1 MB file. P goes into LDRQ0DY. The curves move onto the KFLDRL
    axis; KFLDRQ2 keeps its axis and is only scaled in the ratio modes.
  - Manifold model: URLNM and PRGNM are curves over rpm, 30 points of which
    10 are real (700 .. 6000 rpm) and the rest padding in 1 rpm steps.
    There is no KFURL / KFPRG and no KFPBRKNW. The fit runs on the real
    points; points without rows keep the file's value; the padding holds
    the last one.
  - The first map pack gave PRGNM's axis factor 0.1 and kg/h (280 ..
    2400), the bytes of URLNM's rpm axis. An axis proportional to URLNM's
    is still read as URLNM's. The user has since set it to Upm, factor
    0.25.
  - After that fix WinOLS exports URLNM / PRGNM as 30 x 1 with X empty and
    the rpm on Y. The importer reads a curve with its axis on Y as a curve.
  - KFPBRK came as the unused default: all 1.0 on 0 .. 9000 rpm by 0 ..
    843.75 % load. The user has given it real axes (1000 .. 6500 rpm by
    0 .. 194 % load). The app still warns when a load axis passes 400 %.
  - KFKHFM read 0 in every cell because it was exported in WinOLS's
    percent-difference view; the export fields do not show the view. The
    MAF check then leaves its information block out and says so.
  - Generators take either layout: GeneratorSpec axes and base maps can be
    any-of tuples.
  - Spool on this car: its hybrid turbo makes about 1000 hPa at 6000 rpm
    even at 0 % duty, so the median-of-all-WOT-rows spool comes out late:
    4850 rpm at a 60 % share, 5500 rpm at 90 %. The 82-91 % duties make
    1060-1200 hPa from 2750-3000 rpm. The user's decision (2026-11-06):
    leave the detection as it is; this car is the exception.
- ME7.1, Audi 2.7 biturbo (8D0907551M, HW 0261207143, SW 360857, 1 MB;
  `...\_Files\audi a4 2.7biturbo 1200cc, k04 turbo\`, 2026-11-07). Same
  ME7 app.
  - Boost PID: the curve layout of the 512 kB ME7.5 (LDRQ0DY, LDRQ1DY,
    LDRQ1ST, LDRQ0S). KFLDRQ2 is 4 x 8 with rpm on X (1000 .. 6000) and
    deviation 0 / 300 / 500 / 700 hPa.
  - Manifold model: the VVT maps of the 1 MB ME7.5 (KFURL / KFPRG /
    KFPBRK / KFPBRKNW). KFURL / KFPRG have six cam columns (2, 18, 30.5,
    41, 42, 43); only 2 / 18 / 30.5 are used (18 = 30.5), 41-43 are 0.
    The app's cam-off column goes into 2, cam-on into 18 and 30.5. The
    logged wnwi_w sits at about 0 or 20-22, so the 18 deg split fits.
  - KFLDIMX x axis 600 .. 1400 hPa. KFZW, KFKHFM, FKKVS and KFFWLW have
    byte axes. KFLDRL / KFLDIMX share the rpm axis as on the 1.8T.
  - The first export had KFKHFM in WinOLS's percent-difference view. That
    export carries bPercent = 1 on the map, so the importer refuses such a
    map ("Percent view"). bDelta = 1 is a property of the delta maps
    (DZW, KFLURB ...), not a view.
  - The log channels differ from the 1.8T: nmot, rl (bytes), pvdkds_w,
    pus_w and tmot instead of nmot_w, rl_w, pvdks_w, pu and tmotlin. There
    is no ml_w (mshfm_w is in g/s). There are two banks: frm2_w / fra2_w,
    dwkrz_0..5 and wnwi2_w. Ingest names every configured channel a log
    lacks together with its closest log column; it pops up only when a
    split channel (rpm, pedal, tmot, time) is missing.
  - The optional vars stft2 / ltft2 (bank 2) are averaged with bank 1 at
    ingest; the two banks differ by 3 % (frm 0.976 against 0.947).
  - Displacement 2671 cc for the MAF check.
  - The channel names are a preset: "Channel names" on the profile tab
    (Family.channel_presets, ChannelPreset). It holds the 1.8T defaults
    or "Audi 2.7 biturbo (ME7.1, 8D0907551M)", plus the 5120 pressure
    columns. maf = ml_w, which the user logs from the next logs on; the
    2026-11-07 logs have mshfm_w only.
  - The profile tab's channel fields take effect when a field is left.
    Before this they were only read on save or map import.
- Automatic axes (ME7 set, 2026-10-29), each behind a tick in Boost &
  Wastegate, default off. KFLDRL / KFLDIMX rpm axis: the spool point is
  the lowest 50-rpm bin whose median relative boost reaches 90 % (parameter)
  of the peak bin median, on all WOT rows (no duty condition: on the 032BJ
  the modulated duty never passed 34 % and rose only above 6000 rpm); the
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
| Bosch ME1.5.5 Opel (vehicle logs) | WinOLS CSV export (ME7 map names until an export proves otherwise) | vehicle logger, same shape and RAM names as ME7.6.2 | the ME7 six plus the boost PID via `families/opel_vehicle.py`; knock from wkrm or worst cylinder (dwkrz_0_A..3_A); overrun rows dropped; zero-WGDC and modelled-ps_w warnings | unit tests; ingest run on the one Astra G log, no maps yet |
| Bosch ME7.6.2 Opel (vehicle logs) | WinOLS CSV export (ME7 map names until an export proves otherwise) | vehicle logger: RAM names, German descriptions, units row, time in ms | the ME7 six plus the boost PID on Opel names (nmot, rl_w, wped, pvdkds_w, ps_w, ldtvm, tevfa_w, frm_w, fra_w, tmot, wkrm); overrun rows dropped; modelled-ps_w warning | unit tests; ingest and boost (provisional axes) run on the 2026-11-04 Astra logs, no WinOLS export yet |
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

ME7.6.2 update (2026-11-04): eleven new Astra logs (`...\astra h 2.0
hybrid\logs\`, SW 1037378796, Z20LEH, all WOT pulls at about 330-350
rpm/s, one gear) with forced duties as on ME7: 0, 18, 23/24, 30, 40,
47-50, 58, 64, 69-73, 90 %, integers rather than n/256. The Opel families
now carry the boost PID (KFLDRQ0 / Q1 / Q2 / LDRQ1ST, ME7 names) next to
the KFLDRL rows and finish. With provisional axes:
- The spool sits at 3750 rpm (median boost 943 of a 1037 hPa peak).
- Below the spool, levels from different files disagree. At 3500 rpm,
  40 % made 880 hPa against 811 for 47 % and 825 for 50 %. Above the
  spool they rise in order.
- P comes out at 3.2 to 5.9 %/100 hPa.
Not ported yet:
- MAF check: built on 2026-11-04, see the MAF check bullet below. Where
  tans sits is still open.
- ml_w is in kg/h. The vehicle reader does not keep the units row yet
  (its row under the header is the German descriptions).
- pu is still not logged.

ME7.6.2 damos (2026-11-04):
- Exports:
  - `...\astra h 2.0 hybrid\damos\WinOLS(Opel Astra-H (Original) 371226
    ...).bin.csv` is the damos file, 3507 maps.
  - The car's own file carries the ported names:
    `...\astra h 2.0 hybrid\WinOLS(Opel (Original|more fuel) 378796 ...).bin.csv`.
- The ME7.6.2 family has its own target list (`bosch_me762.TARGET_MAPS`).
- KFURL and KFPRG are KFURLE and KFPRGE: rpm by cam overlap 0 / 90, equal
  columns, each on its own 24-point rpm axis. The fitted KFPRG is moved
  onto the KFPRG axis whenever it differs from the KFURL one.
- KFPBRK is KFPBRKLM: throttle angle by rpm, all 1.0 on a default axis.
  It is not imported, since ps_w is modelled on this ECU.
- KFVPDKSD does not exist. The 1.8T has both KFVPDKSD (dynamic) and
  KFVPDKSE (steady state); ME7.6.2 has only KFVPDKSE.
  - Its x axis is (ps - plgru) / (plsolmax - plgru): damos 0.3 / 0.5 / 0.8
    / 0.85, car file 0 / 0.15 / 0.6 / 0.9.
  - plsolmax comes from VVMDXSN (max pressure ratio in altitude by rpm,
    2.42 to 1.76) and VVNTUXS (turbo overspeed, 4.0 flat), not KFLDHBN.
  - plgru comes from DPLPU / DPLPUR, or plgru_w in the logs.
  - The MATLAB MED9 GenerateKFVPDKSE is the model for a port.
- FKKVS te axis is "effektive Einspritzzeit vor Feinabgleich": tevfa_w is
  confirmed.
- KFLDRAPP is rpm by pedal (wped), 8 x 8, with LDRAPP = 0, so forced-duty
  logging works as on ME7.
- KFKHFM exists (14 x 14, rpm by rl), and the MAF check runs on it.
  tans is the charge temperature: it comes from the boost pressure
  sensor after the intercooler. The user checked it on the car.
- KFVPDKSE is built (2026-11-04) by the MED9 transform, in
  `handover.generate_kfvpdkse`:
  - plgru is the boost of the WOT rows at 0 % duty (the 0 % pull plus the
    zero-duty starts of the other pulls), held flat outside its rpm.
  - plsolmax is min(VVMDXSN, VVNTUXS) x the ambient setting.
  - Each cell stands for plgru + ratio x (plsolmax - plgru). It takes the
    ME7 KFVPDKSD value there: 0.95 below the base boost, 1.0 above, 3 x 3
    smoothed on the automatic ratio axis.
  - On the car file the result is about 0.97-0.98 at ratio 0, 0.98-1.0
    at 0.15 and 1.0 from 0.6 up. The file had 0.95 / 0.955 / 0.99 / 1.0.
  - ME7.6.2 drops the KFVPDKSD generator and its auto-axis setting.
- The ME7.6.2 LDR works above the base boost (2026-11-04, after the first
  calibrated drive, Log00012):
  - KFLDIMX and KFLDRL are looked up with plsolr_w = plsol_w - plgru_w;
    all 12 logs agree within 10 hPa. They are not looked up above ambient
    as on the 1.8T.
  - Base boost is plgru_w = pu + DPLPU(nmot), from BGPLGU. In the car file
    DPLPU is at $AD578 (axis, 4 x 16 bit, 0.25 rpm) and $AD580 (4 bytes,
    10 hPa): 1000/2320/4000/6400 rpm -> +150/+610/+560/+370 hPa.
  - DPLPUR (LDRPLSBY) at $ADC14 / $ADC1C holds the same curve. Neither is
    in the ported export.
  - plgru_w - DPLPU gives pu at 980-992 hPa in every log.
  - KFLDIMX was rescaled to 400-1400 hPa as if ambient-relative. With it,
    Log00012 got an I-part limit of KFLDIMX(plsolr 620-800) = 22-40 %.
    ldtvm was 26-45 % against about 60 % needed, so boost ran 350-430 hPa
    under target from 3000 rpm. The logged duty matches that lookup within
    about 2 %.
  - Fix:
    - DPLPU / DPLPUR are fitted to the 0 % duty pull (generators/base_boost.py):
      least squares on the curve's own 4 breakpoints, 10 hPa steps, pu per row
      from plgru_w - file DPLPU. Result: +0 / +380 / +570 / +410.
    - KFLDRL / KFLDIMX are measured above the base boost after the new
      DPLPU: the logged plgru_w is moved by new - file DPLPU. This is the
      `boost_reference` setting, plgru by default.
    - KFLDIMX gets an axis from 0 to the 99th percentile of plsol - plgru,
      rounded up to 50 hPa (0..850).
    - The KFLDRL spool test stays on boost above ambient, because plgru
      falls with rpm.
    - KFVPDKSE cells use pu + new DPLPU, and pu comes from the logs.
  - Replayed on Log00012, the new maps ask about 59-66 % at 4000-5000 rpm,
    where the ECU gave 31-38 %. The forced pulls needed 58-64 % for
    that boost.
- MAF check on ME7.6.2 (2026-11-04), the ME7 check with 1998 cc. KFKHFM
  is a target, 14 x 14 rpm by rl.
  - Wide open is judged on the throttle wdk1, not the pedal: below about
    1500 rpm this file holds the throttle at about 34 % at full pedal.
  - ml_w is in kg/h. The vehicle reader now keeps the units row, and
    airflow_to_grams converts the airflow.
  - tans is the charge temperature, as on ME7. The sensor is in the boost
    pressure sensor after the intercooler; the user checked on the car.
    It drops in a pull (18.8 -> 15.0 C in Log00012): the sensor is heat
    soaked and the charge air cools it, as on the 1.8T.
  - Result with tans: median VE 92.9 % (85.6 to 99.4 %) over 4244 rows.
    It is 86 % at 1800-2000 rpm, 92-97 % at 3000-3500, about 100 % at
    4000-4500, 94-98 % at 5000, 86 % at 6000 and 81-84 % at 6400.
  - From 4000 rpm up, VE falls with load by 2-4 %. At 2520-3520 it rises
    with load during spool.
- The modelled-ps_w warning: on the Astra logs, 9.6 % of the rows have
  ps_w above pvdkds_w + 50 hPa. All of them are at wide-open throttle,
  around 2200 rpm, with a median excess of 79 hPa. rl_w follows the
  file's KFURLE / KFPRGE through ps_w within about 1.5 % load, and a fit
  gives the file's values back. On the Leon 1.8T, ps_w stays below
  pvdks_w at WOT (median -27 hPa).
- The car file's KFLDIMX axis is 0 / 50 / 100 / 300 / 500 / 600 / 800 /
  1000 hPa, and its KFLDRL top column is 100 %. The damos file has 300 to
  1000 hPa and 95 %. The logs reach about 1360 hPa relative, so the axis
  is rescaled before the export, as on ME7.

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

- [ ] ME7 boost PID, continue with the next ME7 car's forced-duty logs
      (user brings them 2026-10-30): P from the boost-per-duty sensitivity
      is built; the 032BJ logs were judged a poor example. Candidate addition:
      a check row with the KFLDRL stair slope (last 0 % duty cell to the last
      filled cell of each row), since cell-to-cell KFLDRL slopes from forced
      duties are a staircase (risers ~12, treads ~1 %/100 hPa). I and D stay
      manual.
- [ ] Siemens MS43X turbo (BMW M54B30 with a turbo, MS43X custom firmware,
      speed density): built from the ground up in `motronic_autotuner/ms43_turbo/`,
      app `apps/ms43_turbo`, `run_ms43_turbo.bat` (2026-10-29). Almost nothing
      in this plan applies to it: not the Siemens MS43 family and not the
      conventions above. It uses the three-tab window. Kept: the TunerPro log
      reader and the 4-cell splat. Every further step comes from the user.
      Data: `C:/Users/chavd/OneDrive/Desktop/_Files/bmw e36 m54b30 turbo/` (bins incl. the readback,
      the logging ADX, `csv logs\log2.csv`, `log3.csv`); XDF
      `D:\Repos\BMW-XDFs\MS43\Siemens_MS43_MS43X001_512K.xdf`.
      Built: VE correction of ip_map_ve_1..8 (VE fraction, MAP kPa rows, rpm
      columns). "Wideband present" tick on the ingestion tab: f = Wideband AFR
      / AFR target + (STFT + LTFT mult) / 100 on all rows outside fuel cut,
      else f = 1 + trims / 100 on closed-loop rows; bank 1 trims or both
      banks averaged; VEnew = VEold x f. Rows count towards the blended tables
      by the fraction in "Active VE Table". Fuel-cut rows and 1 s after each
      cut, and rows with the wideband input at 0 or 5 V, are left out.
      Facts from the logs: load = 5.75 x VE x MAP (correlation 0.9998), so
      higher VE = more fuel; Wideband AFR = 9.40 + 1.894 x V (rear O2 input
      bank 1); "Wideband Lambda" logs 0 throughout; the wideband reads lean
      0.36 to 0.53 s after a fuel cut starts; no closed-loop rows yet, only
      table 1 active. The wideband term is measured / target (lean raises
      VE, same sign as the trims); the user confirmed this on 2026-10-29.
      ip_maf_1_diag__n__tps_av (MAF substitute, rpm rows by throttle body
      position 0..70 deg columns, mg/stk): the logged Engine Load Injection
      times the same row factor as the VE correction, splatted on the table
      grid; cells without data keep the factory value (an NA table, about
      1.5 x lower than the logged cells, so the new table has steps where
      logged and factory cells meet). Goes on the Load sheet.
      In the firmware this table's airflow goes through the intake manifold
      model to an estimated manifold pressure, and the load comes from that
      pressure. Best would be post-tune load data for every cell; the user
      tests the current table on the car first and decides from that.
      Ignition (ip_iga_ron98_pl__n__maf, 20 rpm rows by 16 load columns,
      Engine Load Ignition, 0.375 deg steps): rows with Part Load or Full
      Load on (never idle or fuel cut there). Knock Correction Average
      (logged negative) splatted as a magnitude; cells at or above 0.1 deg
      pull the average rounded up to whole steps (the old MS43 algorithm);
      cells with no retard at all and at least 5 samples get +0.7 deg (lands
      as +0.75 once pasted); slivers under 0.1 deg and thin cells unchanged.
      On log2 + log3: 0 cells pulled, 48 advanced. The six-cylinder average
      dilutes single-cylinder knock (cylinder 5 retarded 3 deg, average
      0.5): the worst cylinder would pull 0.375 in 5 of the 12 cells that
      saw knock. The user chose to keep the average (2026-10-29).
      Patches tab (2026-10-29): fixed patches written into the bin through
      the XDF, saved under a new name (the input bin is never overwritten).
      A patch is the MS4X wiki copy-paste text (name line, then value rows as
      TunerPro shows them) in `ms43_turbo/patches.py`; a wiki name without
      the XDF axis suffix matches the one title starting with name + "__".
      Nothing is written unless every object is found, has the patch's shape
      and every value fits; then each object is read back, the monitor sum
      (0x72FFC) is recalculated and the calibration CRC kept equal to the
      input bin's through the padding bytes at 0x72FF8 (checksum.py, ported
      from BMW-XDFs/ms43_checksum.py); bytes outside the calibration CRC
      segments are refused. core/xdf.py now reads XDFCONSTANT and writes
      values through linear equations. First patch: ICV delete (M54B30
      values, 19 objects); on the car's readback bin 17 change, 796 bytes,
      checked with the BMW-XDFs reader and checksum script.
      Warm-up (2026-10-31): fits ip_ti_tco_wup_ron98__tco__tco_st and its
      idle twin (coolant now by coolant at start) with the base
      ip_ti_wup_ron98__n__maf fixed. The ECU applies 1 + base x fade
      (checked on logs after v4/warmup.csv: injection time over the hot line
      gave +3.6 % at idle, base x fade +3.6 %; ip_ti_vo_wup does not scale
      the whole injection time). Target lambda from the calibrator's own
      table setting, coolant by lambda (a "curve" setting edited as a
      two-row table on the ingestion tab, saved in the profile; default 0.90
      at 0 C to 1.00 at 60 C), linear between points, held beyond the ends,
      times the logged AFR target; the table used heads the Warm-up sheet.
      Cold rows
      (coolant under the warm-engine threshold, default 80 C) feed only the
      warm-up; VE, ip_maf_1_diag and ignition use only warm rows. Each cold
      row's base-fueling error is the warm rows' VE correction at its VE
      cell; rows without warm data are skipped (default) or taken as VE
      right. Steady filter on rpm and load rates. Coolant at start from the
      Engine Start flag, else the file's first coolant. After-start tables
      (sawup) not done: no log with the start yet. On warmup.csv (35 to 43
      C, no warm rows): lambda 0.73 against 0.97, so the wanted fade is
      negative; the richness is base fueling (v3/v4 c_inj_flow 557, was
      680; VE tables 3 to 6 active cold, never tuned warm).
      Car diagnosis (2026-11-02): the knock retard on all six cylinders at
      once (-3 deg per firing up to the limit, also under vacuum, only while
      load is above ip_maf_min_knk__n__tco) appeared only after the Engine
      Malfunction Light. That was DTC 211, INPA "LLFS Fehler in der
      Mechanik": the idle valve's mechanical fault (mec_isa, P1500/P1501),
      set in light cruise, where the valve carries most of the air (throttle
      0 to 5 %, ISA 60 to 95 %). The ICV delete patch applied to "v6, with
      lambda open loop always, dtc fix (2)", saved as "BMW v7 ICV delete
      (from v6 dtc fix 2).bin", stopped the retard on the car (user). Not
      settled: after clearing the DTCs, the old records (same data words)
      came back after a key cycle.

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
