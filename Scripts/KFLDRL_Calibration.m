% =========================================================================
% MASTER TUNING SUITE: Boost, Base WG, KFVPDKSD, Fuel, Ignition & Sample Counts
% =========================================================================
clear; clc; close all;
% =========================================================================
% MASTER TUNING SUITE: Boost, Base WG, KFVPDKSD, Fuel, Ignition, Warmup & Counts
% =========================================================================
clear; clc; close all;

%% 1. GLOBAL CONTROL CENTER & PRESET MANAGER

% --- PRESET MANAGER ---
% 'manual' = Use the settings typed below
% 'save'   = Use the settings typed below AND save them to the preset file
% 'load'   = Ignore settings below and load directly from the preset file
PRESET_MODE = 'save';           
preset_file = 'VolvoMe7.mat'; 

if strcmp(PRESET_MODE, 'manual') || strcmp(PRESET_MODE, 'save')
    
    % =========================================================================
    % 1.1 FILE MANAGEMENT & EXPORT SETTINGS
    % =========================================================================
    filename_wot     = 'ME9_Logs_WOT.csv';    % Used for Boost & KFVPDKSD
    filename_full    = 'ME9_Logs_Full.csv';   % Used for Fuel & Ignition
    filename_warmup  = 'ME9_Logs_Warmup.csv'; % Used for KFFWL & KFFWLW
    excel_filename   = 'ME7_ME9_Tuning_Maps.xlsx';
    EXPORT_TO_EXCEL  = 1;                     % 1 = Export maps to Excel, 0 = Console only
    SHOW_VISUALS     = 0;                     % 1 = Show 3D and Heatmap plots, 0 = Hide plots
    
    % =========================================================================
    % 1.2 LOGGER VARIABLE NAMES (Must match CSV headers exactly)
    % =========================================================================
    log_vars.rpm     = 'nmot';      % Engine Speed (RPM)
    log_vars.wgdc    = 'ldtvm';       % Wastegate Duty Cycle / N75 (%)
    log_vars.boost   = 'pvdkds_w';     % Absolute Boost Pressure (mbar)
    log_vars.pu      = 'pu';          % Ambient Pressure / Spring Pressure (mbar)
    log_vars.inj     = 'tevfakge_w';  % Effective Injection Time (ms)
    log_vars.stft    = 'frm_w';       % Short Term Fuel Trim (Lambda multiplier)
    log_vars.ltft    = 'fra_w';       % Long Term Fuel Trim (Lambda multiplier)
    log_vars.load    = 'rl_w';        % Relative Engine Load (%)
    log_vars.knock   = 'wkrm';        % Average Knock Retard (Degrees)
    log_vars.vvt     = 'wnwi_w';      % Intake Cam Angle for KFZW2 Split (Optional)
    log_vars.tmot    = 'tmotlin';     % Engine Coolant Temperature (C)
    
    % =========================================================================
    % 1.3 GLOBAL PROCESSING PARAMETERS
    % =========================================================================
    min_samples         = 1;          % Min statistical weight for a valid map cell
    min_samples_base_wg = 1;          % Min weight specifically for Base WG curve extraction
    trim_format         = 0;          % 0 = Factor (e.g., 1.00 is perfect), 1 = Percentage (0.0 is perfect)
    axis_wgdc_splat     = 0:5:95;     % Internal script resolution for reverse WGDC calculation
    
    % =========================================================================
    % 1.4 MODULE ALGORITHM SETTINGS (Boost & Throttle)
    % =========================================================================
    FILL_MISSING_DATA   = 0;          % 0 = Keep NaNs, 1 = Extrapolate missing KFLDRL target boost data
    CWLDIMX             = 0;          % 0 = Subtract Ambient (pu_w), 1 = Subtract Spring Pressure
    ambient_pressure    = 1000;       % Baseline fallback used for KFVPDKSD math and Abs WGDC conversion
    safety_margin       = 0;          % % WGDC added to KFLDIMX (Usually 0 when using Nefmoto hack)
    
    % =========================================================================
    % 1.5 WINOLS MAP AXES (Define your map dimensions here)
    % =========================================================================
    % --- BOOST (KFLDRL / KFLDIMX) ---
    axis_rpm_boost   = [1520	1760	2000	2240	2520	2760	3000	3240	3520	3760	4000	4520	5000	5520	6000	6520];
    axis_boost       = [300	450	600	750	900	1050	1200	1400]; 
    axis_kfldrl_x    = [ 0	1	10	20	35	50	65	80	90	100];
    
    % --- THROTTLE HANDOVER (KFVPDKSD) ---
    axis_rpm_kfvp    = [1000.000	2000.000	2500.000	3000.000	3500.000	3600.000	3750.000	3900.000	5000.000	6000.000	6500.000	7000.000];
    axis_pratio_kfvp = [1.323181	1.530334	2.069946	2.207886	2.345886	2.484009	2.669434	2.759949	2.897949	3.049194	3.221802	3.451965];
    
    % --- FUEL TRIMS (FKKVS) ---
    axis_rpm_fuel    = [640	840	1000	1240	1520	1760	2000	2240	2520	2760	3000	3520	4000	4520	5000	6000];
    axis_te          = [0.71	0.84	1.25	1.67	2.09	2.50	2.92	3.33	4.17	5.00	6.67	8.33	10.00	11.67	13.34	15.00]; 
    
    % --- WARMUP ENRICHMENT (KFFWL / KFFWLW) ---
    axis_tmot        = [-39.75 -30.00 -20.25 -9.75 0.00 9.75 20.25 30.00 45.00 60.00 90.00 120.00];
    axis_rpm_kffwlw  = [800.0 1480.0 2000.0 3000.0 5000.0 7000.0]; 
    axis_load_kffwlw = [15.000 30.000 45.000 60.000 75.000 90.000]; 
    
    % --- IGNITION KNOCK RETARD (KFZW / KFZW2) ---
    axis_rpm_ign     = [ 800.000	 1000.000	 1480.000	 1720.000	 2000.000	 2200.000	 2520.000	 3000.000	 3520.000	 4000.000	 4520.000	 5000.000	 6000.000	 6500.000	 7000.000	 7500.000];
    axis_load_ign    = [ 9.7500	 20.2500	 30.0000	 45.0000	 60.0000	 69.7500	 90.0000	 134.9766	 164.9766	 184.9922	 219.9844	 259.9922];

    % --- SAVE THE PRESET ---
    if strcmp(PRESET_MODE, 'save')
        save(preset_file, 'filename_wot', 'filename_full', 'filename_warmup', 'excel_filename', ...
             'EXPORT_TO_EXCEL', 'SHOW_VISUALS', 'log_vars', 'min_samples', 'min_samples_base_wg', ...
             'trim_format', 'axis_wgdc_splat', 'FILL_MISSING_DATA', 'CWLDIMX', 'ambient_pressure', ...
             'safety_margin', 'axis_rpm_boost', 'axis_boost', 'axis_kfldrl_x', 'axis_rpm_kfvp', ...
             'axis_pratio_kfvp', 'axis_rpm_fuel', 'axis_te', 'axis_tmot', 'axis_rpm_kffwlw', ...
             'axis_load_kffwlw', 'axis_rpm_ign', 'axis_load_ign');
        disp(['*** Successfully saved current settings to preset: ', preset_file, ' ***']);
    end

    
elseif strcmp(PRESET_MODE, 'load') %#ok<UNRCH>
    % --- LOAD THE PRESET ---
    if exist(preset_file, 'file')
        load(preset_file);
        disp(['*** Successfully loaded settings from preset: ', preset_file, ' ***']);
    else
        error(['Preset file not found: ', preset_file, '. Change PRESET_MODE to ''save'' first to create it!']);
    end
else %#ok<UNRCH>
    error('Invalid PRESET_MODE. Use ''manual'', ''save'', or ''load''.');
end

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

%% ========================================================================
% FUNCTION: Side-By-Side Excel Exporter
% ========================================================================
function ExportAllMapsToExcel(filename, KFLDIMX_Map, KFLDRL_Map, KFLDRL_Counts, Abs_WGDC_Map, Abs_WGDC_Counts, Base_Pressure_Curve, Base_Pressure_Counts, KFVPDKSD_Map, KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map, FKKVS_Map, FKKVS_Counts, KFZW_Map, KFZW_Counts, KFZW2_Map, KFZW2_Counts, axis_rpm_boost, axis_boost, axis_boost_abs, axis_kfldrl_x, axis_rpm_kfvp, axis_pratio_kfvp, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, axis_rpm_fuel, axis_te, axis_rpm_ign, axis_load_ign)
    output_cells = {};
    
    function add_linked_maps_to_sheet(title_str1, map_data1, title_str2, map_data2, x_axis, y_axis, secondary_x_label, secondary_x_data)
        if isempty(map_data1), return; end
        start_row = size(output_cells, 1) + 1; gap_cols = 2; col_offset = length(x_axis) + 1 + gap_cols; 
        
        output_cells{start_row, 1} = title_str1;
        if nargin > 3 && ~isempty(map_data2), output_cells{start_row, 1 + col_offset} = title_str2; end
        
        header_row = cell(1, length(x_axis) + 1); header_row{1} = 'Y-Axis \ X-Axis'; 
        for c = 1:length(x_axis), header_row{c+1} = x_axis(c); end
        output_cells(start_row + 1, 1:length(header_row)) = header_row;
        if nargin > 3 && ~isempty(map_data2), output_cells(start_row + 1, (1 + col_offset):(length(header_row) + col_offset)) = header_row; end
        
        current_r = start_row + 2;
        if nargin > 6 && ~isempty(secondary_x_data)
            header_row_2 = cell(1, length(x_axis) + 1); header_row_2{1} = secondary_x_label;
            for c = 1:length(secondary_x_data), header_row_2{c+1} = round(secondary_x_data(c), 1); end
            output_cells(current_r, 1:length(header_row_2)) = header_row_2;
            if nargin > 3 && ~isempty(map_data2), output_cells(current_r, (1 + col_offset):(length(header_row_2) + col_offset)) = header_row_2; end
            current_r = current_r + 1;
        end
        
        for r = 1:length(y_axis)
            data_row1 = cell(1, length(x_axis) + 1);
            if iscell(y_axis) || isstring(y_axis), data_row1{1} = char(y_axis(r)); else, data_row1{1} = y_axis(r); end
            data_row2 = data_row1; 
            for c = 1:length(x_axis)
                if isnan(map_data1(r,c)), data_row1{c+1} = ''; else, data_row1{c+1} = round(map_data1(r,c), 3); end
                if nargin > 3 && ~isempty(map_data2)
                    if isnan(map_data2(r,c)), data_row2{c+1} = ''; else, data_row2{c+1} = round(map_data2(r,c), 3); end
                end
            end
            output_cells(current_r, 1:length(data_row1)) = data_row1;
            if nargin > 3 && ~isempty(map_data2), output_cells(current_r, (1 + col_offset):(length(data_row2) + col_offset)) = data_row2; end
            current_r = current_r + 1;
        end
        output_cells{current_r, 1} = ''; 
    end

    add_linked_maps_to_sheet('KFLDIMX (Linear Converter Map)', KFLDIMX_Map, '', [], axis_boost, axis_rpm_boost);
    
    min_boost_axis = axis_boost(1); max_boost_axis = axis_boost(end);
    physical_boost_axis = min_boost_axis + (axis_kfldrl_x / 100) .* (max_boost_axis - min_boost_axis);
    add_linked_maps_to_sheet('KFLDRL (Base Linearization - WGDC %)', KFLDRL_Map, 'KFLDRL - SAMPLE WEIGHTS', KFLDRL_Counts, axis_kfldrl_x, axis_rpm_boost, 'Target Rel Boost (mbar)', physical_boost_axis);
    
    add_linked_maps_to_sheet('ABSOLUTE WGDC MAP (Abs Boost vs RPM)', Abs_WGDC_Map, 'ABS WGDC - SAMPLE WEIGHTS', Abs_WGDC_Counts, axis_boost_abs, axis_rpm_boost);
    add_linked_maps_to_sheet('Base WG Pressure (Abs mbar)', Base_Pressure_Curve, 'Base WG - SAMPLE WEIGHTS', Base_Pressure_Counts, axis_rpm_kfvp, {'Base Boost'});
    add_linked_maps_to_sheet('KFVPDKSD (Steady State Throttle Handover)', KFVPDKSD_Map, '', [], axis_rpm_kfvp, axis_pratio_kfvp);
    
    % New Warmup Maps
    add_linked_maps_to_sheet('KFFWL (Warmup Enrichment % vs Temp)', KFFWL_Map, 'KFFWL - SAMPLE WEIGHTS', KFFWL_Counts, axis_tmot, {'Trim %'});
    add_linked_maps_to_sheet('FKKVS_RL (Hot Trims mapped to Load/RPM)', FKKVS_RL_Map, '', [], axis_load_kffwlw, axis_rpm_kffwlw);
    add_linked_maps_to_sheet('KFFWLW (Warmup Weighting % vs Load/RPM)', KFFWLW_Map, 'KFFWLW - SAMPLE WEIGHTS', KFFWLW_Counts, axis_load_kffwlw, axis_rpm_kffwlw);

    add_linked_maps_to_sheet('FKKVS (Fuel Trim Correction %)', FKKVS_Map, 'FKKVS - SAMPLE WEIGHTS', FKKVS_Counts, axis_te, axis_rpm_fuel);
    add_linked_maps_to_sheet('KFZW (Ignition Knock Correction - VVT OFF)', KFZW_Map, 'KFZW - SAMPLE WEIGHTS', KFZW_Counts, axis_load_ign, axis_rpm_ign);
    add_linked_maps_to_sheet('KFZW2 (Ignition Knock Correction - VVT ON)', KFZW2_Map, 'KFZW2 - SAMPLE WEIGHTS', KFZW2_Counts, axis_load_ign, axis_rpm_ign);
    
    if ~isempty(output_cells)
        writecell(output_cells, filename, 'Sheet', 'Tuning Maps');
        disp(['Success! All generated maps saved to: ', filename]);
    end
end

%% ========================================================================
% GENERATION FUNCTIONS
% ========================================================================
function [KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map] = GenerateWarmupMaps(data_warmup, data_full, min_samples, axis_tmot, axis_load, axis_rpm, log_vars, trim_format)
    req_vars = {log_vars.tmot, log_vars.stft, log_vars.ltft, log_vars.load, log_vars.rpm};
    for v = 1:length(req_vars)
        if ~ismember(req_vars{v}, data_warmup.Properties.VariableNames) || ~ismember(req_vars{v}, data_full.Properties.VariableNames)
            error(['Missing required variable for Warmup: ', req_vars{v}]);
        end
    end
    
    % 1. Calculate Raw Trims for Hot and Cold data
    if trim_format == 0
        Raw_Trim_Hot = (data_full.(log_vars.stft) .* data_full.(log_vars.ltft) - 1.0) .* 100;
        Raw_Trim_Cold = (data_warmup.(log_vars.stft) .* data_warmup.(log_vars.ltft) - 1.0) .* 100;
    else
        Raw_Trim_Hot = data_full.(log_vars.stft) + data_full.(log_vars.ltft);
        Raw_Trim_Cold = data_warmup.(log_vars.stft) + data_warmup.(log_vars.ltft);
    end
    
    % 2. Filter Hot Data (tmot >= 80) and find global baseline fallback
    hot_mask = data_full.(log_vars.tmot) >= 80;
    data_hot = data_full(hot_mask, :);
    Raw_Trim_Hot_Filtered = Raw_Trim_Hot(hot_mask);
    
    if sum(hot_mask) > 10
        Base_Hot_Trim = mean(Raw_Trim_Hot_Filtered, 'omitnan');
    else
        Base_Hot_Trim = 0;
        disp('Warning: Not enough data > 80C to calculate hot trims. Assuming base fueling is perfect.');
    end
    
    % 3. Generate FKKVS_RL (Hot Trims mapped onto Load vs RPM axes)
    [FKKVS_RL_Map, ~] = BilinearSplatting(data_hot.(log_vars.load), data_hot.(log_vars.rpm), Raw_Trim_Hot_Filtered, axis_load, axis_rpm, min_samples);
    
    % Fallback: If a Load/RPM cell wasn't hit while hot, fill it with the global average hot trim
    FKKVS_RL_Filled = FKKVS_RL_Map;
    FKKVS_RL_Filled(isnan(FKKVS_RL_Filled)) = Base_Hot_Trim;
    
    % 4. 1D Splatting for KFFWL (Temp vs Trim)
    Net_Warmup_Trim_Pct = Raw_Trim_Cold - Base_Hot_Trim;
    [KFFWL_Map, KFFWL_Counts] = LinearSplatting1D(data_warmup.(log_vars.tmot), Net_Warmup_Trim_Pct, axis_tmot, min_samples);
    
    % Force the operating temp cells to exactly 0.00%
    for i = 1:length(axis_tmot)
        if axis_tmot(i) >= 80 && ~isnan(KFFWL_Map(i))
            KFFWL_Map(i) = 0.00;
        end
    end

    % 5. Generate Raw KFFWLW (Cold Trims mapped onto Load vs RPM)
    [KFFWLW_Raw, KFFWLW_Counts] = BilinearSplatting(data_warmup.(log_vars.load), data_warmup.(log_vars.rpm), Raw_Trim_Cold, axis_load, axis_rpm, min_samples);
    
    % 6. True KFFWLW calculation: Subtract the base hot correction (FKKVS_RL) from the raw cold trims
    KFFWLW_Map = KFFWLW_Raw - FKKVS_RL_Filled;
end

function [KFLDIMX_Map, KFLDRL_Map, Abs_WGDC_Map, axis_boost_abs, KFLDRL_Counts, Abs_WGDC_Counts] = GenerateBoostMaps(data, CWLDIMX, ambient_pressure, safety_margin, FILL_MISSING_DATA, min_samples, axis_rpm, axis_boost, axis_kfldrl_x, log_vars)
    if CWLDIMX == 1, Relative_Boost_log = data.(log_vars.boost) - data.(log_vars.pu);
    else, Relative_Boost_log = data.(log_vars.boost) - ambient_pressure; end

    numRows = length(axis_rpm); max_boost_axis = max(axis_boost); min_boost_axis = axis_boost(1); max_pid_limit = 100; 
    
    KFLDIMX_Map = zeros(numRows, length(axis_boost));
    for c = 1:length(axis_boost), KFLDIMX_Map(:, c) = ((axis_boost(c) - min_boost_axis) / (max_boost_axis - min_boost_axis)) * max_pid_limit; end

    physical_boost_axis = min_boost_axis + (axis_kfldrl_x / max_pid_limit) .* (max_boost_axis - min_boost_axis);
    [KFLDRL_Map, KFLDRL_Counts] = BilinearSplatting(Relative_Boost_log, data.(log_vars.rpm), data.(log_vars.wgdc), physical_boost_axis, axis_rpm, min_samples);

    if FILL_MISSING_DATA == 1
        valid_mask = ~isnan(KFLDRL_Map); 
        [X_grid_drl, Y_grid_drl] = meshgrid(physical_boost_axis, axis_rpm);
        if sum(valid_mask(:)) > 4
            F_drl = scatteredInterpolant(X_grid_drl(valid_mask), Y_grid_drl(valid_mask), KFLDRL_Map(valid_mask), 'linear', 'nearest');
            KFLDRL_Map = F_drl(X_grid_drl, Y_grid_drl);
        end
        KFLDRL_Map(:, end) = max_pid_limit; 
    end
    KFLDRL_Map(KFLDRL_Map < 0) = 0; KFLDRL_Map(KFLDRL_Map > 95) = 95;
    
    axis_boost_abs = axis_boost + ambient_pressure;
    [Abs_WGDC_Map, Abs_WGDC_Counts] = BilinearSplatting(data.(log_vars.boost), data.(log_vars.rpm), data.(log_vars.wgdc), axis_boost_abs, axis_rpm, min_samples);
end

function [Base_Pressure_Curve, Base_Pressure_Counts] = GenerateBaseWGPressure(data, min_samples, axis_rpm, log_vars)
    base_wg_mask = (data.(log_vars.wgdc) < 10); 
    RPM_base   = data.(log_vars.rpm)(base_wg_mask);
    Boost_base = data.(log_vars.boost)(base_wg_mask);
    [Base_Pressure_Curve, Base_Pressure_Counts] = LinearSplatting1D(RPM_base, Boost_base, axis_rpm, min_samples);
end

function KFVPDKSD_Map = GenerateKFVPDKSD(Base_Pressure_Curve, axis_rpm, axis_pratio, pu_constant)
    numCols = length(axis_rpm); numRows = length(axis_pratio); KFVPDKSD_Map = ones(numRows, numCols);
    valid_idx = ~isnan(Base_Pressure_Curve);
    if sum(valid_idx) >= 2, filled_curve = interp1(axis_rpm(valid_idx), Base_Pressure_Curve(valid_idx), axis_rpm, 'linear', 'extrap');
    else, filled_curve = Base_Pressure_Curve; end
    for c = 1:numCols
        if isnan(filled_curve(c)), KFVPDKSD_Map(:, c) = NaN; continue; end
        base_ratio = filled_curve(c) / pu_constant;
        for r = 1:numRows
            if base_ratio > axis_pratio(r), KFVPDKSD_Map(r, c) = 0.95; else, KFVPDKSD_Map(r, c) = 1.0; end
        end
    end
    valid_mask = ~isnan(KFVPDKSD_Map);
    if any(valid_mask(:))
        padded = [KFVPDKSD_Map(1,:); KFVPDKSD_Map; KFVPDKSD_Map(end,:)]; padded = [padded(:,1), padded, padded(:,end)];
        smoothed = conv2(padded, ones(3,3)/9, 'valid'); smoothed(smoothed > 1.0) = 1.0; smoothed(smoothed < 0.95) = 0.95;
        smoothed(~valid_mask) = NaN; KFVPDKSD_Map = smoothed;
    end
end

function [KFZW_Map, KFZW2_Map, KFZW_Counts, KFZW2_Counts] = GenerateKFZW(data, min_samples, axis_rpm, axis_load, log_vars)
    RPM_log = data.(log_vars.rpm); Load_log = data.(log_vars.load); Knock_log = data.(log_vars.knock);
    vars = data.Properties.VariableNames; vvt_idx = find(strcmpi(vars, log_vars.vvt), 1);
    if ~isempty(vvt_idx)
        VVT_log = data.(vars{vvt_idx}); mask_vvt_off = VVT_log <= 18; mask_vvt_on  = VVT_log > 18;
        [KFZW_Map, KFZW_Counts] = BilinearSplatting(Load_log(mask_vvt_off), RPM_log(mask_vvt_off), Knock_log(mask_vvt_off), axis_load, axis_rpm, min_samples);
        [KFZW2_Map, KFZW2_Counts] = BilinearSplatting(Load_log(mask_vvt_on), RPM_log(mask_vvt_on), Knock_log(mask_vvt_on), axis_load, axis_rpm, min_samples);
    else
        [KFZW_Map, KFZW_Counts] = BilinearSplatting(Load_log, RPM_log, Knock_log, axis_load, axis_rpm, min_samples); 
        KFZW2_Map = []; KFZW2_Counts = [];
    end
    KFZW_Map(isnan(KFZW_Map)) = 0; if ~isempty(KFZW2_Map), KFZW2_Map(isnan(KFZW2_Map)) = 0; end
end

function [FKKVS_Map, FKKVS_Counts] = GenerateFKKVS(data, min_samples, axis_rpm, axis_te, log_vars, trim_format)
    if trim_format == 0
        Trim_Pct_log = (data.(log_vars.stft) .* data.(log_vars.ltft) - 1.0) .* 100;
    else
        Trim_Pct_log = data.(log_vars.stft) + data.(log_vars.ltft);
    end
    [FKKVS_Map, FKKVS_Counts] = BilinearSplatting(data.(log_vars.inj), data.(log_vars.rpm), Trim_Pct_log, axis_te, axis_rpm, min_samples);
    FKKVS_Map(isnan(FKKVS_Map)) = 0;
end

%% ========================================================================
% CORE ENGINE: Splatting Algorithms
% ========================================================================
function [Z_Map, countArray] = BilinearSplatting(X_data, Y_data, Z_data, x_axis, y_axis, min_samples)
    numCols = length(x_axis); numRows = length(y_axis); sumArray = zeros(numRows, numCols); countArray = zeros(numRows, numCols);
    for i = 1:length(X_data)
        xVal = X_data(i); yVal = Y_data(i); zVal = Z_data(i);
        if ~isnan(xVal) && ~isnan(yVal) && ~isnan(zVal)
            [xIdx, xFrac] = GetInterpolation(xVal, x_axis); [yIdx, yFrac] = GetInterpolation(yVal, y_axis);
            w00 = (1 - yFrac) * (1 - xFrac); w10 = yFrac * (1 - xFrac); w01 = (1 - yFrac) * xFrac; w11 = yFrac * xFrac;
            sumArray(yIdx, xIdx) = sumArray(yIdx, xIdx) + (w00 * zVal); countArray(yIdx, xIdx) = countArray(yIdx, xIdx) + w00;
            if yIdx < numRows, sumArray(yIdx+1, xIdx) = sumArray(yIdx+1, xIdx) + (w10 * zVal); countArray(yIdx+1, xIdx) = countArray(yIdx+1, xIdx) + w10; end
            if xIdx < numCols, sumArray(yIdx, xIdx+1) = sumArray(yIdx, xIdx+1) + (w01 * zVal); countArray(yIdx, xIdx+1) = countArray(yIdx, xIdx+1) + w01; end
            if yIdx < numRows && xIdx < numCols, sumArray(yIdx+1, xIdx+1) = sumArray(yIdx+1, xIdx+1) + (w11 * zVal); countArray(yIdx+1, xIdx+1) = countArray(yIdx+1, xIdx+1) + w11; end
        end
    end
    Z_Map = NaN(numRows, numCols);
    for r = 1:numRows
        for c = 1:numCols
            if countArray(r, c) >= min_samples, Z_Map(r, c) = sumArray(r, c) / countArray(r, c); end
        end
    end
end

function [Z_Curve, countArray] = LinearSplatting1D(X_data, Z_data, x_axis, min_samples)
    numCols = length(x_axis); sumArray = zeros(1, numCols); countArray = zeros(1, numCols);
    for i = 1:length(X_data)
        xVal = X_data(i); zVal = Z_data(i);
        if ~isnan(xVal) && ~isnan(zVal)
            [xIdx, xFrac] = GetInterpolation(xVal, x_axis); w0 = 1 - xFrac; w1 = xFrac;
            sumArray(xIdx) = sumArray(xIdx) + (w0 * zVal); countArray(xIdx) = countArray(xIdx) + w0;
            if xIdx < numCols, sumArray(xIdx+1) = sumArray(xIdx+1) + (w1 * zVal); countArray(xIdx+1) = countArray(xIdx+1) + w1; end
        end
    end
    Z_Curve = NaN(1, numCols);
    for c = 1:numCols
        if countArray(c) >= min_samples, Z_Curve(c) = sumArray(c) / countArray(c); end
    end
end

function [lowerIdx, fraction] = GetInterpolation(val, axisArray)
    maxIdx = length(axisArray);
    if val <= axisArray(1), lowerIdx = 1; fraction = 0; return; end
    if val >= axisArray(maxIdx), lowerIdx = maxIdx; fraction = 0; return; end
    for i = 1:maxIdx-1
        if val >= axisArray(i) && val < axisArray(i+1), lowerIdx = i; fraction = (val - axisArray(i)) / (axisArray(i+1) - axisArray(i)); return; end
    end
end