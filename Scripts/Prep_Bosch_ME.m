% =========================================================================
% Log Prep: Batch CSV Merger, WOT/Warmup Filters, 5120 Hack & Time Stitching
% =========================================================================
clear; clc;

% =========================================================================
% BOSCH ME7/ME9 LOG PREPARATION UTILITY
% =========================================================================
clear; clc; close all;

%% 1. LOAD CONFIGURATION FROM JSON PRESET
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end

disp('Waiting for user to select a JSON preset...');
[preset_name, preset_path] = uigetfile(fullfile(script_dir, 'presets', '*.json'), 'Select the ECU Tuning Preset');

if isequal(preset_name, 0)
    disp('*** Preset selection canceled. Script stopped. ***');
    return;
end

% Read the JSON file natively
config = jsondecode(fileread(fullfile(preset_path, preset_name)));
disp(['*** Successfully loaded config from: ', preset_name, ' ***']);

% --- Map JSON back to Prep Script Variables ---
log_folder = config.files.raw_log_folder;
file_pattern = fullfile(log_folder, '*.csv');
csv_files = dir(file_pattern);

% Filter Settings
filter_vars.pedal      = config.vars.pedal; 
filter_thresh.wot_min  = config.prep.wot_min;         
filter_vars.temp       = config.vars.tmot;     
filter_thresh.temp_max = config.prep.temp_max;        

% Time Alignment Settings
ALIGN_TIMESTAMPS = config.prep.ALIGN_TIMESTAMPS;           
time_col_name    = config.vars.time; 

% 5120mbar Hack Toggle
HACK_5120        = config.prep.HACK_5120; 
pressure_columns = config.prep.pressure_columns;

% File Outputs (for downstream saving)
filename_wot     = config.files.filename_wot;    
filename_full    = config.files.filename_full;   
filename_warmup  = config.files.filename_warmup;
filename_hot     = config.files.filename_hot;

%% 2. EXECUTION BLOCK
disp('--- STARTING RAW DATA EXTRACTION & VALIDATION ---');
if isempty(csv_files)
    error(['No CSV files found in: ', log_folder]);
end

Master_Log = table();

for i = 1:length(csv_files)
    file_path = fullfile(csv_files(i).folder, csv_files(i).name);
    
    % TunerPro Header Bypass & Load
    fid = fopen(file_path, 'r'); line1 = fgetl(fid); fclose(fid);
    if contains(line1, 'TunerPro')
        opts = detectImportOptions(file_path, 'NumHeaderLines', 1);
    else
        opts = detectImportOptions(file_path);
    end
    opts.VariableNamingRule = 'preserve'; 
    current_log = readtable(file_path, opts);
    if height(current_log) > 0, current_log(end, :) = []; end
    
    % =========================================================================
    % PRE-FLIGHT CHECK: Missing Variable Detector (Runs only on the first file)
    % =========================================================================
    if i == 1
        actual_log_columns = current_log.Properties.VariableNames;
        expected_json_vars = struct2cell(config.vars);
        missing_vars = {};
        
        for v = 1:length(expected_json_vars)
            var_name = expected_json_vars{v};
            % Check if the variable exists in the CSV headers
            if ~ismember(var_name, actual_log_columns)
                missing_vars{end+1} = var_name; %#ok<SAGROW>
            end
        end
        
        if ~isempty(missing_vars)
            disp('=======================================================');
            disp(' !!! WARNING: MISSING VARIABLES IN RAW LOGS !!!');
            disp('=======================================================');
            disp('The following variables defined in your JSON preset');
            disp('were NOT found in your TunerPro CSV files:');
            disp(' ');
            for m = 1:length(missing_vars)
                disp(['   - [ ', missing_vars{m}, ' ]']);
            end
            disp('=======================================================');
            disp('The script will attempt to continue, but downstream math may fail.');
            disp(' ');
        else
            disp('SUCCESS: All required JSON variables found in the raw logs!');
            disp(' ');
        end
    end
end   
    % --- Your existing Log Merging / Time Alignment logic goes here ---
    % ...
    
% Initialize empty tables and our global time offset tracker
Master_Log_Full   = table();
Master_Log_WOT    = table();
Master_Log_Warmup = table(); 
Master_Log_Hot    = table(); % NEW: Dedicated table for fully warmed up data
global_time_offset = 0;      

disp('Processing raw log files...');
for i = 1:length(csv_files)
    
    file_path = fullfile(csv_files(i).folder, csv_files(i).name);
    
    warning('off', 'MATLAB:table:ModifiedAndSavedVarnames');
    current_log = readtable(file_path);
    warning('on', 'MATLAB:table:ModifiedAndSavedVarnames');
    
    % Preliminary removal of the incomplete final row
    if height(current_log) > 0
        current_log(end, :) = []; 
    end
    
    all_vars = current_log.Properties.VariableNames;
    
    % Convert ALL text/description rows into NaNs
    for c = 1:length(all_vars)
        col_name = all_vars{c};
        col_data = current_log.(col_name);
        
        if iscell(col_data) || isstring(col_data)
            current_log.(col_name) = str2double(col_data);
        end
    end
    
    % Remove ANY row that contains a NaN
    initial_rows = height(current_log);
    current_log = rmmissing(current_log);
    nan_rows_removed = initial_rows - height(current_log);
    
    % --- Align Timestamps Sequentially (For FULL Log) ---
    if ALIGN_TIMESTAMPS == 1
        if ismember(time_col_name, all_vars)
            current_log.(time_col_name) = current_log.(time_col_name) + global_time_offset;
            global_time_offset = max(current_log.(time_col_name));
        else
            warning(['Time column ''', time_col_name, ''' not found in ', csv_files(i).name, '. Timestamps not adjusted.']);
        end
    end
    
    % Apply 5120 Hack (Multiply pressures by 2)
    if HACK_5120 == 1
        for p = 1:length(pressure_columns)
            p_col = pressure_columns{p};
            if ismember(p_col, all_vars)
                current_log.(p_col) = current_log.(p_col) .* 2;
            end
        end
    end
    
    % Append to the FULL Master Table
    try
        Master_Log_Full = vertcat(Master_Log_Full, current_log);
    catch ME
        error(['Failed to merge FULL log for ', csv_files(i).name, '. Ensure all CSVs have the exact same column headers!']);
    end
    
    wot_count = 0;
    warmup_count = 0;
    hot_count = 0;
    
    % --- Filter for Wide Open Throttle (WOT) ---
    if ismember(filter_vars.pedal, all_vars)
        wot_rows = current_log.(filter_vars.pedal) > filter_thresh.wot_min; 
        current_log_wot = current_log(wot_rows, :);
        wot_count = height(current_log_wot);
        try
            Master_Log_WOT = vertcat(Master_Log_WOT, current_log_wot);
        catch ME, error(['Failed to merge WOT log for ', csv_files(i).name, '.']); end
    else
        warning(['Pedal position (', filter_vars.pedal, ') not found in ', csv_files(i).name, '. Cannot apply WOT filter.']);
    end
    
    % --- Filter for Warmup (< 80C) and Hot (>= 80C) ---
    if ismember(filter_vars.temp, all_vars)
        % Warmup (Cold)
        warmup_rows = current_log.(filter_vars.temp) < filter_thresh.temp_max; 
        current_log_warmup = current_log(warmup_rows, :);
        warmup_count = height(current_log_warmup);
        try
            Master_Log_Warmup = vertcat(Master_Log_Warmup, current_log_warmup);
        catch ME, error(['Failed to merge Warmup log for ', csv_files(i).name, '.']); end
        
        % Hot (Fully Warmed Up)
        hot_rows = current_log.(filter_vars.temp) >= filter_thresh.temp_max; 
        current_log_hot = current_log(hot_rows, :);
        hot_count = height(current_log_hot);
        try
            Master_Log_Hot = vertcat(Master_Log_Hot, current_log_hot);
        catch ME, error(['Failed to merge Hot log for ', csv_files(i).name, '.']); end
    else
        warning(['Coolant temp (', filter_vars.temp, ') not found in ', csv_files(i).name, '. Cannot apply Temp filters.']);
    end
    
    % Print Summary
    fprintf('Loaded %s: Kept %d FULL, %d WOT, %d WARMUP, %d HOT rows.\n', ...
        csv_files(i).name, height(current_log), wot_count, warmup_count, hot_count);
end

% =========================================================================
% POST-PROCESSING: STITCH TIME GAPS (WOT, WARMUP, HOT)
% =========================================================================
if ALIGN_TIMESTAMPS == 1 && ismember(time_col_name, all_vars)
    disp('Stitching filtered logs together to create continuous time axes...');
    
    if ~isempty(Master_Log_WOT)
        Master_Log_WOT.(time_col_name) = StitchTimeArray(Master_Log_WOT.(time_col_name));
    end
    if ~isempty(Master_Log_Warmup)
        Master_Log_Warmup.(time_col_name) = StitchTimeArray(Master_Log_Warmup.(time_col_name));
    end
    if ~isempty(Master_Log_Hot)
        Master_Log_Hot.(time_col_name) = StitchTimeArray(Master_Log_Hot.(time_col_name));
    end
end

% =========================================================================
% SAVE OUTPUTS TO THE PREPARED LOGS DIRECTORY
% =========================================================================
disp(' ');
% Dynamically find the folder where this script is saved
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir)
    script_dir = pwd; % Fallback
end

% --- CREATE PreparedLogs FOLDER ---
prep_out_dir = fullfile(script_dir, 'PreparedLogs');
if ~exist(prep_out_dir, 'dir')
    mkdir(prep_out_dir);
end

% --- CLEAR OLD FILES ---
disp('Cleaning up old CSV files in PreparedLogs folder...');
old_files = {filename_full, filename_wot, filename_warmup, filename_hot};
for i = 1:length(old_files)
    target_file = fullfile(prep_out_dir, old_files{i});
    if exist(target_file, 'file')
        delete(target_file);
    end
end

% --- SAVE NEW FILES ---
if ~isempty(Master_Log_Full)
    output_path_full = fullfile(prep_out_dir, filename_full);
    writetable(Master_Log_Full, output_path_full);
    disp(['Success! Saved FULL data to:   PreparedLogs\', filename_full]);
end

if ~isempty(Master_Log_WOT)
    output_path_wot = fullfile(prep_out_dir, filename_wot);
    writetable(Master_Log_WOT, output_path_wot);
    disp(['Success! Saved WOT data to:    PreparedLogs\', filename_wot]);
end

if ~isempty(Master_Log_Warmup)
    output_path_warmup = fullfile(prep_out_dir, filename_warmup);
    writetable(Master_Log_Warmup, output_path_warmup);
    disp(['Success! Saved WARMUP data to: PreparedLogs\', filename_warmup]);
end

if ~isempty(Master_Log_Hot)
    output_path_hot = fullfile(prep_out_dir, filename_hot);
    writetable(Master_Log_Hot, output_path_hot);
    disp(['Success! Saved HOT data to:    PreparedLogs\', filename_hot]);
end

if ALIGN_TIMESTAMPS == 1
    disp('*** Timestamps were successfully aligned and gaps were stitched. ***');
end
if HACK_5120 == 1
    disp('*** NOTE: 5120mbar Hack was ENABLED. All pressure values were multiplied by 2. ***');
end

disp(' ');
disp('Master Prep Execution Complete. You can now run Tuner_Bosch_ME.m!');

%% ========================================================================
% HELPER FUNCTIONS
% ========================================================================
function stitched_time = StitchTimeArray(time_array)
    % Takes a fragmented time array and stitches the massive gaps together
    if length(time_array) <= 1
        stitched_time = time_array;
        return;
    end
    
    dt = diff(time_array);
    median_dt = median(dt(dt > 0 & dt < 1.0));
    
    if isnan(median_dt) || isempty(median_dt)
        median_dt = 0.1; 
    end
    
    stitched_time = zeros(size(time_array));
    stitched_time(1) = 0; 
    
    for k = 2:length(time_array)
        if dt(k-1) > 1.0 || dt(k-1) < 0
            stitched_time(k) = stitched_time(k-1) + median_dt;
        else
            stitched_time(k) = stitched_time(k-1) + dt(k-1);
        end
    end
end