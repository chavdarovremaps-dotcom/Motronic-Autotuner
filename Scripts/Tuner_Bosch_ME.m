% =========================================================================
% BOSCH ME7/ME9 MASTER TUNING SUITE
% =========================================================================
clear; clc; close all;

% Hook up the utilities folder
addpath(fullfile(fileparts(mfilename('fullpath')), 'Utilities'));

%% 1. LOAD TUNING PRESET
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end

disp('Waiting for user to select a JSON preset...');
[preset_name, preset_path] = uigetfile(fullfile(script_dir, 'presets', '*.json'), 'Select a Tuning Preset');

if isequal(preset_name, 0)
    disp('*** Preset selection canceled. Script stopped. ***');
    return;
end

% Read the JSON file natively
config = jsondecode(fileread(fullfile(preset_path, preset_name)));
disp(['*** Successfully loaded config from: ', preset_name, ' ***']);
disp(' ');

% --- EXTRACT WORKFLOW & FILES ---
filename_wot     = config.files.filename_wot;
filename_full    = config.files.filename_full;
filename_warmup  = config.files.filename_warmup;
filename_hot     = config.files.filename_hot;
excel_filename   = config.files.excel_filename;

PROCESS_RAW_LOGS = config.workflow.PROCESS_RAW_LOGS;
EXPORT_TO_EXCEL  = config.workflow.EXPORT_TO_EXCEL;
SHOW_VISUALS     = config.workflow.SHOW_VISUALS;

% --- EXTRACT LOGGER VARIABLES & PARAMETERS ---
log_vars            = config.vars;
min_samples         = config.params.min_samples;
min_samples_base_wg = config.params.min_samples_base_wg;
trim_format         = config.params.trim_format;
axis_wgdc_splat     = config.params.axis_wgdc_splat;
FILL_MISSING_DATA   = config.params.FILL_MISSING_DATA;
CWLDIMX             = config.params.CWLDIMX;
ambient_pressure    = config.params.ambient_pressure;
safety_margin       = config.params.safety_margin;

% =========================================================================
% --- FAIL-SAFE EXTRACTION: AXES & BASE MAPS ---
% =========================================================================
% Core Axes
if isfield(config.axes, 'rpm_boost'),   axis_rpm_boost   = config.axes.rpm_boost;   else axis_rpm_boost = []; end
if isfield(config.axes, 'boost'),       axis_boost       = config.axes.boost;       else axis_boost = []; end
if isfield(config.axes, 'kfldrl_x'),    axis_kfldrl_x    = config.axes.kfldrl_x;    else axis_kfldrl_x = []; end
if isfield(config.axes, 'rpm_kfvp'),    axis_rpm_kfvp    = config.axes.rpm_kfvp;    else axis_rpm_kfvp = []; end
if isfield(config.axes, 'pratio_kfvp'), axis_pratio_kfvp = config.axes.pratio_kfvp; else axis_pratio_kfvp = []; end
if isfield(config.axes, 'rpm_fuel'),    axis_rpm_fuel    = config.axes.rpm_fuel;    else axis_rpm_fuel = []; end
if isfield(config.axes, 'te'),          axis_te          = config.axes.te;          else axis_te = []; end
if isfield(config.axes, 'tmot'),        axis_tmot        = config.axes.tmot;        else axis_tmot = []; end
if isfield(config.axes, 'rpm_kffwlw'),  axis_rpm_kffwlw  = config.axes.rpm_kffwlw;  else axis_rpm_kffwlw = []; end
if isfield(config.axes, 'load_kffwlw'), axis_load_kffwlw = config.axes.load_kffwlw; else axis_load_kffwlw = []; end
if isfield(config.axes, 'rpm_ign'),     axis_rpm_ign     = config.axes.rpm_ign;     else axis_rpm_ign = []; end
if isfield(config.axes, 'load_ign'),    axis_load_ign    = config.axes.load_ign;    else axis_load_ign = []; end

if ~isempty(axis_boost), axis_boost_abs = axis_boost + ambient_pressure; else axis_boost_abs = []; end

% Saugrohrmodell Axes
if isfield(config.axes, 'rpm_pbrk'),    axis_rpm_pbrk    = config.axes.rpm_pbrk;    else axis_rpm_pbrk = []; end
if isfield(config.axes, 'load_pbrk'),   axis_load_pbrk   = config.axes.load_pbrk;   else axis_load_pbrk = []; end
if isfield(config.axes, 'rpm_pbrknw'),  axis_rpm_pbrknw  = config.axes.rpm_pbrknw;  else axis_rpm_pbrknw = []; end
if isfield(config.axes, 'load_pbrknw'), axis_load_pbrknw = config.axes.load_pbrknw; else axis_load_pbrknw = []; end
if isfield(config.axes, 'rpm_prg'),     axis_rpm_prg     = config.axes.rpm_prg;     else axis_rpm_prg = []; end
if isfield(config.axes, 'vvt_prg'),     axis_vvt_prg     = config.axes.vvt_prg;     else axis_vvt_prg = []; end
if isfield(config.axes, 'rpm_url'),     axis_rpm_url     = config.axes.rpm_url;     else axis_rpm_url = []; end
if isfield(config.axes, 'vvt_url'),     axis_vvt_url     = config.axes.vvt_url;     else axis_vvt_url = []; end

% Base Maps
base_kfldimx = []; base_kfldrl = []; base_kfvp = []; base_fkkvs = []; 
base_kffwlw = []; base_kffwl = []; base_kfzw = []; base_kfpbrk = []; 
base_kfpbrknw = []; base_kfprg = []; base_kfurl = [];

if isfield(config, 'base_maps')
    if isfield(config.base_maps, 'base_kfldimx'),  base_kfldimx  = config.base_maps.base_kfldimx;  end
    if isfield(config.base_maps, 'base_kfldrl'),   base_kfldrl   = config.base_maps.base_kfldrl;   end
    if isfield(config.base_maps, 'base_kfvp'),     base_kfvp     = config.base_maps.base_kfvp;     end
    if isfield(config.base_maps, 'base_fkkvs'),    base_fkkvs    = config.base_maps.base_fkkvs;    end
    if isfield(config.base_maps, 'base_kffwlw'),   base_kffwlw   = config.base_maps.base_kffwlw;   end
    if isfield(config.base_maps, 'base_kffwl'),    base_kffwl    = config.base_maps.base_kffwl;    end
    if isfield(config.base_maps, 'base_kfzw'),     base_kfzw     = config.base_maps.base_kfzw;     end
    if isfield(config.base_maps, 'base_kfpbrk'),   base_kfpbrk   = config.base_maps.base_kfpbrk;   end
    if isfield(config.base_maps, 'base_kfpbrknw'), base_kfpbrknw = config.base_maps.base_kfpbrknw; end
    if isfield(config.base_maps, 'base_kfprg'),    base_kfprg    = config.base_maps.base_kfprg;    end
    if isfield(config.base_maps, 'base_kfurl'),    base_kfurl    = config.base_maps.base_kfurl;    end
    if isfield(config.params, 'vvt_enabled'), vvt_enabled = config.params.vvt_enabled; else, vvt_enabled = 1; end
    if isfield(config.params, 'vvt_threshold'), vvt_threshold = config.params.vvt_threshold; else, vvt_threshold = 15; end
end

% =========================================================================
% --- MODULE GATEKEEPERS (Readiness Flags) ---
% =========================================================================
disp('--- PRESET DIAGNOSTICS ---');
READY_BOOST  = ~isempty(axis_rpm_boost) && ~isempty(axis_boost) && ~isempty(base_kfldimx);
READY_KFVP   = ~isempty(axis_rpm_kfvp) && ~isempty(axis_pratio_kfvp) && ~isempty(base_kfvp); % NEW: Added KFVP Gatekeeper
READY_FUEL   = ~isempty(axis_rpm_fuel) && ~isempty(axis_te) && ~isempty(base_fkkvs);
READY_IGN    = ~isempty(axis_rpm_ign) && ~isempty(axis_load_ign) && ~isempty(base_kfzw);
READY_WARMUP = ~isempty(axis_rpm_kffwlw) && ~isempty(axis_load_kffwlw) && ~isempty(base_kffwlw);
READY_SAUGROHR = ~isempty(axis_rpm_url) && ~isempty(axis_vvt_url) && ~isempty(base_kfurl) && ~isempty(base_kfprg);


if ~READY_BOOST,  disp('[WARNING] KFLDIMX (Boost) skipped: Missing axes or base map in preset.'); end
if ~READY_KFVP,   disp('[WARNING] KFVPDKSD (Handover) skipped: Missing axes or base map in preset.'); end
if ~READY_FUEL,   disp('[WARNING] FKKVS (Fueling) skipped: Missing axes or base map in preset.'); end
if ~READY_IGN,    disp('[WARNING] KFZW (Ignition) skipped: Missing axes or base map in preset.'); end
if ~READY_WARMUP, disp('[WARNING] KFFWLW (Warmup) skipped: Missing axes or base map in preset.'); end
if ~READY_SAUGROHR, disp('[WARNING] Saugrohrmodell skipped: Missing KFURL/KFPRG axes or base maps.'); end

if READY_BOOST && READY_KFVP && READY_FUEL && READY_IGN && READY_WARMUP
    disp('All primary maps and axes loaded successfully. Ready to tune.');
end
disp(' ');

%% 2. EXECUTION BLOCK
disp('--- LOADING LOG DATA ---');

% Define the path to the PreparedLogs folder
prep_dir = fullfile(script_dir, 'PreparedLogs');

% Check if the folder actually exists before trying to load from it
if ~exist(prep_dir, 'dir')
    disp(['[ERROR] The folder ', prep_dir, ' does not exist. Run Prep_Bosch_ME first!']);
    return;
end

% Load the files directly from the PreparedLogs folder
try data_wot = readtable(fullfile(prep_dir, filename_wot)); catch, data_wot = table(); disp('No WOT log found.'); end
try data_full = readtable(fullfile(prep_dir, filename_full)); catch, data_full = table(); disp('No FULL log found.'); end
try data_warmup = readtable(fullfile(prep_dir, filename_warmup)); catch, data_warmup = table(); disp('No WARMUP log found.'); end
try data_hot = readtable(fullfile(prep_dir, filename_hot)); catch, data_hot = table(); disp('No HOT log found.'); end

% Initialize variables to prevent Excel exporter crashes if a module is skipped

KFLDIMX_Map=[]; KFLDRL_Map=[]; Abs_WGDC_Map=[]; axis_boost_abs=[];
KFLDRL_Counts=[]; Abs_WGDC_Counts=[]; Base_Pressure_Counts=[];
Base_Pressure_Curve=[]; KFVPDKSD_Map=[]; 
FKKVS_Map=[]; FKKVS_Counts=[]; 
KFZW_Map=[]; KFZW2_Map=[]; KFZW_Counts=[]; KFZW2_Counts=[];
KFFWL_Map=[]; KFFWL_Counts=[]; KFFWLW_Map=[]; KFFWLW_Counts=[]; FKKVS_RL_Map=[];
KFURL_Map=[]; KFPRG_Map=[]; Saugrohr_Counts=[];axis_vvt_out=[];
disp(' ');

% --- Run Boost Calibration ---
if READY_BOOST && ~isempty(data_wot)
    disp('--- STARTING BOOST CONTROL CALIBRATION ---');
    try
        [KFLDIMX_Map, KFLDRL_Map, Abs_WGDC_Map, axis_boost_abs, KFLDRL_Counts, Abs_WGDC_Counts] = GenerateBoostMaps(data_wot, CWLDIMX, ambient_pressure, safety_margin, FILL_MISSING_DATA, min_samples, axis_rpm_boost, axis_boost, axis_kfldrl_x, log_vars);
    catch ME, disp(['Boost Map Error: ', ME.message]); end
    disp(' ');
end

% --- Run Throttle Handover ---
if READY_KFVP && ~isempty(data_wot)
    disp('--- STARTING THROTTLE HANDOVER (KFVPDKSD) ---');
    try
        [Base_Pressure_Curve, Base_Pressure_Counts] = GenerateBaseWGPressure(data_wot, min_samples_base_wg, axis_rpm_kfvp, log_vars);
        KFVPDKSD_Map = GenerateKFVPDKSD(Base_Pressure_Curve, axis_rpm_kfvp, axis_pratio_kfvp, ambient_pressure);
    catch ME, disp(['KFVPDKSD Map Error: ', ME.message]); end
    disp(' ');
end

% --- Run Warmup Enrichment (KFFWL / KFFWLW / FKKVS_RL) ---
if READY_WARMUP && ~isempty(data_warmup)
    disp('--- STARTING WARMUP ENRICHMENT CALIBRATION ---');
    try
        [KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map] = GenerateWarmupMaps(data_warmup, data_full, min_samples, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, log_vars, trim_format);
    catch ME, disp(['Warmup Map Error: ', ME.message]); end
    disp(' ');
end

% --- Run Fuel Trim ---
if READY_FUEL && ~isempty(data_hot)
    disp('--- STARTING FKKVS FUEL TRIM CALIBRATION ---');
    try
        % FIX: Now correctly routing data_hot instead of data_full!
        [FKKVS_Map, FKKVS_Counts] = GenerateFKKVS(data_hot, min_samples, axis_rpm_fuel, axis_te, log_vars, trim_format);
    catch ME, disp(['Fuel Map Error: ', ME.message]); end
    disp(' ');
end

% --- Run Ignition Timing ---
if READY_IGN && ~isempty(data_full)
    disp('--- STARTING IGNITION TIMING CORRECTION ---');
    try
        [KFZW_Map, KFZW2_Map, KFZW_Counts, KFZW2_Counts] = GenerateKFZW(data_full, min_samples, axis_rpm_ign, axis_load_ign, log_vars);
    catch ME, disp(['Ignition Map Error: ', ME.message]); end
    disp(' ');
end

% --- Run Intake Manifold Model ---
if READY_SAUGROHR && ~isempty(data_full)
    disp('--- STARTING INTAKE MANIFOLD CALIBRATION ---');
    try
        % NOTICE: Now passing data_full so the math has part-throttle data to draw a line!
        [KFURL_Map, KFPRG_Map, Saugrohr_Counts, axis_vvt_out] = GenerateSaugrohrmodell(data_full, axis_rpm_url, log_vars, min_samples, vvt_enabled, vvt_threshold);
        disp('Successfully calculated pure binary VVT Saugrohrmodell data.');
    catch ME
        disp(['Saugrohr Map Error: ', ME.message]); 
    end
    disp(' ');
end
% --- Excel Export ---
if EXPORT_TO_EXCEL == 1
    disp('--- EXPORTING MAPS TO EXCEL ---');
    ExportAllMapsToExcel(excel_filename, KFLDIMX_Map, KFLDRL_Map, KFLDRL_Counts, Abs_WGDC_Map, Abs_WGDC_Counts, ...
                         Base_Pressure_Curve, Base_Pressure_Counts, KFVPDKSD_Map, ...
                         KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map, ...
                         FKKVS_Map, FKKVS_Counts, KFZW_Map, KFZW_Counts, KFZW2_Map, KFZW2_Counts, ...
                         KFURL_Map, KFPRG_Map, Saugrohr_Counts, ... 
                         axis_rpm_boost, axis_boost, axis_boost_abs, axis_kfldrl_x, axis_rpm_kfvp, axis_pratio_kfvp, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, axis_rpm_fuel, axis_te, axis_rpm_ign, axis_load_ign, axis_rpm_url, axis_vvt_out);
    disp(['Success! Maps saved to: ', excel_filename]);
end
disp('Master Suite Execution Complete.');
