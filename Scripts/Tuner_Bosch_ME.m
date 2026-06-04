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

%% 1. LOAD TUNING PRESET
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end

disp('Waiting for user to select a JSON preset...');
[preset_name, preset_path] = uigetfile(fullfile(script_dir, 'presets', '*.json'), 'Select a Tuning Preset');

if isequal(preset_name, 0)
    disp('*** Preset selection canceled. Script stopped. ***');
    return;
end

% Read the JSON file natively in one line
config = jsondecode(fileread(fullfile(preset_path, preset_name)));
disp(['*** Successfully loaded config from: ', preset_name, ' ***']);

% Extract Workflow & Files
filename_wot     = config.files.filename_wot;
filename_full    = config.files.filename_full;
filename_warmup  = config.files.filename_warmup;
excel_filename   = config.files.excel_filename;
PROCESS_RAW_LOGS = config.workflow.PROCESS_RAW_LOGS;
EXPORT_TO_EXCEL  = config.workflow.EXPORT_TO_EXCEL;

% Extract Logger Variables & Parameters
log_vars            = config.vars;
min_samples         = config.params.min_samples;
min_samples_base_wg = config.params.min_samples_base_wg;
trim_format         = config.params.trim_format;
axis_wgdc_splat     = config.params.axis_wgdc_splat;
FILL_MISSING_DATA   = config.params.FILL_MISSING_DATA;
CWLDIMX             = config.params.CWLDIMX;
ambient_pressure    = config.params.ambient_pressure;
safety_margin       = config.params.safety_margin;

% --- Base Maps & Axes extraction (as we set up previously) goes here ---

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


