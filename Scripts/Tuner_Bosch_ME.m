% =========================================================================
% BOSCH ME7/ME9 MASTER TUNING SUITE: Boost, Handover, Fuel, Ignition
% =========================================================================
clear; clc; close all;
% Add the utils folder to MATLAB's search path
addpath(fullfile(fileparts(mfilename('fullpath')), 'Utilities'));

% =========================================================================
% BOSCH ME7/ME9 MASTER TUNING SUITE
% =========================================================================
clear; clc; close all;

% Hook up the utilities folder
addpath(fullfile(fileparts(mfilename('fullpath')), 'utils'));

% =========================================================================
% BOSCH ME7/ME9 MASTER TUNING SUITE
% =========================================================================
clear; clc; close all;

% Hook up the utilities folder
addpath(fullfile(fileparts(mfilename('fullpath')), 'utils'));

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

% --- EXTRACT WINOLS AXES ---
% (This prevents the scope/initialization errors you were seeing)
axis_rpm_boost   = config.axes.rpm_boost;
axis_boost       = config.axes.boost;
axis_kfldrl_x    = config.axes.kfldrl_x;
axis_rpm_kfvp    = config.axes.rpm_kfvp;
axis_pratio_kfvp = config.axes.pratio_kfvp;
axis_rpm_fuel    = config.axes.rpm_fuel;
axis_te          = config.axes.te;
axis_tmot        = config.axes.tmot;
axis_rpm_kffwlw  = config.axes.rpm_kffwlw;
axis_load_kffwlw = config.axes.load_kffwlw;
axis_rpm_ign     = config.axes.rpm_ign;
axis_load_ign    = config.axes.load_ign;

% Some math blocks use Absolute Boost instead of Relative Boost
axis_boost_abs   = axis_boost + ambient_pressure;

% Saugrohrmodell Axes (Fallback to empty if older JSON is used)
if isfield(config.axes, 'rpm_pbrk'),   axis_rpm_pbrk   = config.axes.rpm_pbrk;   else axis_rpm_pbrk = []; end
if isfield(config.axes, 'load_pbrk'),  axis_load_pbrk  = config.axes.load_pbrk;  else axis_load_pbrk = []; end
if isfield(config.axes, 'rpm_pbrknw'), axis_rpm_pbrknw = config.axes.rpm_pbrknw; else axis_rpm_pbrknw = []; end
if isfield(config.axes, 'load_pbrknw'),axis_load_pbrknw= config.axes.load_pbrknw;else axis_load_pbrknw = []; end
if isfield(config.axes, 'rpm_prg'),    axis_rpm_prg    = config.axes.rpm_prg;    else axis_rpm_prg = []; end
if isfield(config.axes, 'vvt_prg'),    axis_vvt_prg    = config.axes.vvt_prg;    else axis_vvt_prg = []; end
if isfield(config.axes, 'rpm_url'),    axis_rpm_url    = config.axes.rpm_url;    else axis_rpm_url = []; end
if isfield(config.axes, 'vvt_url'),    axis_vvt_url    = config.axes.vvt_url;    else axis_vvt_url = []; end

% --- EXTRACT BASE MAPS ---
base_kfldimx = []; base_kfldrl = []; base_kfvp = []; base_fkkvs = []; 
base_kffwlw = []; base_kfzw = []; base_kfpbrk = []; base_kfpbrknw = []; 
base_kfprg = []; base_kfurl = [];

if isfield(config, 'base_maps')
    if isfield(config.base_maps, 'base_kfldimx'),  base_kfldimx  = config.base_maps.base_kfldimx;  end
    if isfield(config.base_maps, 'base_kfldrl'),   base_kfldrl   = config.base_maps.base_kfldrl;   end
    if isfield(config.base_maps, 'base_kfvp'),     base_kfvp     = config.base_maps.base_kfvp;     end
    if isfield(config.base_maps, 'base_fkkvs'),    base_fkkvs    = config.base_maps.base_fkkvs;    end
    if isfield(config.base_maps, 'base_kffwlw'),   base_kffwlw   = config.base_maps.base_kffwlw;   end
    if isfield(config.base_maps, 'base_kfzw'),     base_kfzw     = config.base_maps.base_kfzw;     end
    if isfield(config.base_maps, 'base_kfpbrk'),   base_kfpbrk   = config.base_maps.base_kfpbrk;   end
    if isfield(config.base_maps, 'base_kfpbrknw'), base_kfpbrknw = config.base_maps.base_kfpbrknw; end
    if isfield(config.base_maps, 'base_kfprg'),    base_kfprg    = config.base_maps.base_kfprg;    end
    if isfield(config.base_maps, 'base_kfurl'),    base_kfurl    = config.base_maps.base_kfurl;    end
end

%% 2. EXECUTION BLOCK
% (Your original execution code starts exactly here)

%% 2. EXECUTION BLOCK

disp('Loading WOT log data...');
data_wot = readtable(filename_wot);

disp('Loading FULL log data...');
data_full = readtable(filename_full);

disp('Loading WARMUP log data...');
try 
    data_warmup = readtable(filename_warmup);
catch
    disp('Warning: No Warmup log found. KFFWL/KFFWLW will be skipped.');
    data_warmup = table();
end

% Initialize variables to prevent Excel exporter crashes
KFLDIMX_Map=[]; KFLDRL_Map=[]; Abs_WGDC_Map=[]; axis_boost_abs=[];
KFLDRL_Counts=[]; Abs_WGDC_Counts=[]; Base_Pressure_Counts=[];
Base_Pressure_Curve=[]; KFVPDKSD_Map=[]; 
FKKVS_Map=[]; FKKVS_Counts=[]; 
KFZW_Map=[]; KFZW2_Map=[]; KFZW_Counts=[]; KFZW2_Counts=[];
KFFWL_Map=[]; KFFWL_Counts=[]; KFFWLW_Map=[]; KFFWLW_Counts=[]; FKKVS_RL_Map=[];

disp(' ');

% --- Run Boost Calibration ---
disp('--- STARTING BOOST CONTROL CALIBRATION ---');
try
    [KFLDIMX_Map, KFLDRL_Map, Abs_WGDC_Map, axis_boost_abs, KFLDRL_Counts, Abs_WGDC_Counts] = GenerateBoostMaps(data_wot, CWLDIMX, ambient_pressure, safety_margin, FILL_MISSING_DATA, min_samples, axis_rpm_boost, axis_boost, axis_kfldrl_x, log_vars);
catch ME, disp(['Boost Map Error: ', ME.message]); end

disp(' ');

% --- Run Throttle Handover ---
disp('--- STARTING THROTTLE HANDOVER (KFVPDKSD) ---');
try
    [Base_Pressure_Curve, Base_Pressure_Counts] = GenerateBaseWGPressure(data_wot, min_samples_base_wg, axis_rpm_kfvp, log_vars);
    KFVPDKSD_Map = GenerateKFVPDKSD(Base_Pressure_Curve, axis_rpm_kfvp, axis_pratio_kfvp, ambient_pressure);
catch ME, disp(['KFVPDKSD Map Error: ', ME.message]); end

disp(' ');

% --- Run Warmup Enrichment (KFFWL / KFFWLW / FKKVS_RL) ---
if ~isempty(data_warmup)
    disp('--- STARTING WARMUP ENRICHMENT CALIBRATION ---');
    try
        [KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map] = GenerateWarmupMaps(data_warmup, data_full, min_samples, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, log_vars, trim_format);
    catch ME, disp(['Warmup Map Error: ', ME.message]); end
end

disp(' ');

% --- Run Fuel Trim ---
disp('--- STARTING FKKVS FUEL TRIM CALIBRATION ---');
try
    [FKKVS_Map, FKKVS_Counts] = GenerateFKKVS(data_full, min_samples, axis_rpm_fuel, axis_te, log_vars, trim_format);
catch ME, disp(['Fuel Map Error: ', ME.message]); end

disp(' ');

% --- Run Ignition Timing ---
disp('--- STARTING IGNITION TIMING CORRECTION ---');
try
    [KFZW_Map, KFZW2_Map, KFZW_Counts, KFZW2_Counts] = GenerateKFZW(data_full, min_samples, axis_rpm_ign, axis_load_ign, log_vars);
catch ME, disp(['Ignition Map Error: ', ME.message]); end

disp(' ');

% --- Excel Export ---
if EXPORT_TO_EXCEL == 1
    disp('--- EXPORTING MAPS TO EXCEL ---');
    ExportAllMapsToExcel(excel_filename, KFLDIMX_Map, KFLDRL_Map, KFLDRL_Counts, Abs_WGDC_Map, Abs_WGDC_Counts, ...
                         Base_Pressure_Curve, Base_Pressure_Counts, KFVPDKSD_Map, ...
                         KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map, ...
                         FKKVS_Map, FKKVS_Counts, KFZW_Map, KFZW_Counts, KFZW2_Map, KFZW2_Counts, ...
                         axis_rpm_boost, axis_boost, axis_boost_abs, axis_kfldrl_x, axis_rpm_kfvp, axis_pratio_kfvp, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, axis_rpm_fuel, axis_te, axis_rpm_ign, axis_load_ign);
end

disp('Done!');


