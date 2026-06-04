% =========================================================================
% BOSCH ME7/ME9 MASTER TUNING SUITE: Boost, Handover, Fuel, Ignition
% =========================================================================
clear; clc; close all;

%% 1. GLOBAL CONTROL CENTER & JSON PRESET MANAGER
% =========================================================================
% 'manual' = Use settings typed below
% 'save'   = Use settings typed below AND save to JSON preset
% 'load'   = Load directly from JSON via Pop-Up
PRESET_MODE = 'load';           

if strcmp(PRESET_MODE, 'manual') || strcmp(PRESET_MODE, 'save')

    % --- 1.1 WORKFLOW & FILES ---
    config.workflow.PROCESS_RAW_LOGS = 1; 
    config.workflow.EXPORT_TO_EXCEL  = 1; 
    config.workflow.SHOW_VISUALS     = 0; 

    config.files.filename_wot     = 'ME9_Logs_WOT.csv';    
    config.files.filename_full    = 'ME9_Logs_Full.csv';   
    config.files.filename_warmup  = 'ME9_Logs_Warmup.csv'; 
    config.files.excel_filename   = 'ME7_ME9_Tuning_Maps.xlsx';

    % --- 1.2 LOGGER VARIABLE NAMES ---
    config.vars.rpm     = 'nmot_w';      
    config.vars.wgdc    = 'ldtvm';       
    config.vars.boost   = 'pvdks_w';     
    config.vars.pu      = 'pu';          
    config.vars.inj     = 'tevfakge_w';  
    config.vars.stft    = 'frm_w';       
    config.vars.ltft    = 'fra_w';       
    config.vars.load    = 'rl_w';        
    config.vars.knock   = 'wkrm';        
    config.vars.vvt     = 'wnwi_w';      
    config.vars.tmot    = 'tmotlin';     

    % --- 1.3 GLOBAL PARAMETERS ---
    config.params.min_samples         = 2;          
    config.params.min_samples_base_wg = 2;          
    config.params.trim_format         = 0;          % 0 = Factor (1.00), 1 = Percentage (0.0)
    config.params.axis_wgdc_splat     = 0:5:95;     
    config.params.FILL_MISSING_DATA   = 0;          
    config.params.CWLDIMX             = 0;          
    config.params.ambient_pressure    = 1000;       
    config.params.safety_margin       = 0;          

    % --- 1.4 WINOLS MAP AXES (Placeholders) ---
    config.axes.rpm_boost   = [1000 1250 1500 1750 2000 2250 2500 2750 3000 3500 4000 4500 5000 5500 6000 6500];
    config.axes.boost       = [250 350 500 700 900 1100 1300 1500]; 
    config.axes.kfldrl_x    = [0 10 20 30 40 50 60 70 80 95];
    config.axes.rpm_kfvp    = [1000 1480 1720 2000 2520 3000 3520 4520 5000 5520 6000 6520];
    config.axes.pratio_kfvp = [1.330 1.400 1.470 1.540 1.610 1.680 1.750 1.820 1.890 1.960 2.030 2.100];
    config.axes.rpm_fuel    = [600 800 1000 1240 1520 1720 2000 2520 3000 3520 4000 4520 5000 5520 6000 6520];
    config.axes.te          = [0.99 1.30 1.60 2.00 2.50 3.00 4.00 5.00 6.00 7.00 8.00 9.00 10.00 13.00 16.00 19.00]; 
    config.axes.tmot        = [-39.75 -30.00 -20.25 -9.75 0.00 9.75 20.25 30.00 45.00 60.00 90.00 120.00];
    config.axes.rpm_kffwlw  = [800 1480 2000 3000 5000 7000]; 
    config.axes.load_kffwlw = [15 30 45 60 75 90]; 
    config.axes.rpm_ign     = [600 800 1000 1480 1720 2000 2240 2520 3000 3520 4000 4520 5000 5520 6000 6520];
    config.axes.load_ign    = [10.0 20.0 35.0 50.0 65.0 80.0 90.0 100.0 125.0 150.0 180.0 200.0];
    
    % Saugrohrmodell Placeholders
    config.axes.rpm_pbrk    = [1000 2000 3000 4000 5000 6000];
    config.axes.load_pbrk   = [10 30 50 70 90 100];
    config.axes.rpm_pbrknw  = [1000 2000 3000 4000 5000 6000];
    config.axes.load_pbrknw = [10 30 50 70 90 100];
    config.axes.rpm_prg     = [1000 2000 3000 4000 5000 6000];
    config.axes.vvt_prg     = [0 10 20 30 40 50];
    config.axes.rpm_url     = [1000 2000 3000 4000 5000 6000];
    config.axes.vvt_url     = [0 10 20 30 40 50];

    % --- 1.5 BASE MAPS (Populated by WinOLS Preset Builder) ---
    config.base_maps = struct(); 

    % --- SAVE TO JSON ---
    if strcmp(PRESET_MODE, 'save')
        preset_file = 'presets/Bosch_ME9_Default.json';
        [preset_dir, ~, ~] = fileparts(preset_file);
        if ~isempty(preset_dir) && ~exist(preset_dir, 'dir'), mkdir(preset_dir); end
        
        json_txt = jsonencode(config, 'PrettyPrint', true); 
        fid = fopen(preset_file, 'w'); fwrite(fid, json_txt, 'char'); fclose(fid);
        disp(['*** Successfully saved template config to: ', preset_file, ' ***']);
    end

elseif strcmp(PRESET_MODE, 'load') 
    % --- LOAD FROM JSON VIA POP-UP ---
    script_dir = fileparts(mfilename('fullpath'));
    if isempty(script_dir), script_dir = pwd; end
    
    disp('Waiting for user to select a JSON preset...');
    [preset_name, preset_path] = uigetfile(fullfile(script_dir, 'presets', '*.json'), 'Select a Tuning Preset');
    
    if isequal(preset_name, 0)
        disp('*** Preset selection canceled. Script stopped. ***');
        return;
    end
    
    preset_file = fullfile(preset_path, preset_name);
    fid = fopen(preset_file, 'r'); raw = fread(fid, inf); str = char(raw'); fclose(fid);
    config = jsondecode(str);
    disp(['*** Successfully loaded config from: ', preset_name, ' ***']);
    
    % Force axis arrays to be row vectors
    axes_fields = fieldnames(config.axes);
    for i = 1:length(axes_fields)
        config.axes.(axes_fields{i}) = config.axes.(axes_fields{i})(:)';
    end
else 
    error('Invalid PRESET_MODE.');
end

% =========================================================================
% --- EXTRACT VARIABLES TO WORKSPACE (Safe for Downstream Math) ---
% =========================================================================

% Files & Workflow
filename_wot     = config.files.filename_wot;
filename_full    = config.files.filename_full;
filename_warmup  = config.files.filename_warmup;
excel_filename   = config.files.excel_filename;

PROCESS_RAW_LOGS = config.workflow.PROCESS_RAW_LOGS;
EXPORT_TO_EXCEL  = config.workflow.EXPORT_TO_EXCEL;
SHOW_VISUALS     = config.workflow.SHOW_VISUALS;

% Logger Variables & Parameters
log_vars         = config.vars;
min_samples         = config.params.min_samples;
min_samples_base_wg = config.params.min_samples_base_wg;
trim_format         = config.params.trim_format;
axis_wgdc_splat     = config.params.axis_wgdc_splat;
FILL_MISSING_DATA   = config.params.FILL_MISSING_DATA;
CWLDIMX             = config.params.CWLDIMX;
ambient_pressure    = config.params.ambient_pressure;
safety_margin       = config.params.safety_margin;

% WinOLS Axes
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
axis_rpm_pbrk    = config.axes.rpm_pbrk;
axis_load_pbrk   = config.axes.load_pbrk;
axis_rpm_pbrknw  = config.axes.rpm_pbrknw;
axis_load_pbrknw = config.axes.load_pbrknw;
axis_rpm_prg     = config.axes.rpm_prg;
axis_vvt_prg     = config.axes.vvt_prg;
axis_rpm_url     = config.axes.rpm_url;
axis_vvt_url     = config.axes.vvt_url;

% --- EXTRACT BASE MAPS (Safely Fallback to Empty if Missing) ---
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

%% 2. RAW LOG PROCESSING ENGINE ... (Execution block continues below)

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


