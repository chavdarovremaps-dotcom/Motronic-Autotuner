% =========================================================================
% Log Prep: Batch CSV Merger, WOT/Warmup Filters, 5120 Hack & Time Stitching
% =========================================================================
clear; clc;

% 1. Setup Folder and Files
log_folder = 'D:\Damos files\Matlab scripts\Volvo S60'; % Location of your RAW logs
file_pattern = fullfile(log_folder, '*.csv');
csv_files = dir(file_pattern);

% --- LOGGING VARIABLE NAMES & FILTER SETTINGS ---
filter_vars.pedal      = 'wped';   % Pedal position column name
filter_thresh.wot_min  = 95;         % Minimum pedal % to be considered WOT

filter_vars.temp       = 'tmot';     % Coolant temperature column name
filter_thresh.temp_max = 80;         % Maximum temp (C) to be considered Warm-up

% --- TIME ALIGNMENT SETTINGS ---
ALIGN_TIMESTAMPS = 1;           % 1 = Make time continuous across merged logs
time_col_name    = 'Time'; % Your logger's exact time header

% --- 5120mbar Hack Toggle ---
HACK_5120 = 0; % 1 = Multiply logged pressures by 2 (for 3/4-bar MAP sensors)
pressure_columns = {'pvdks_w', 'pu', 'pssol_w', 'pvdk_w', 'plgru_w'};


%% 2. EXECUTION BLOCK
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
% SAVE OUTPUTS TO THE SCRIPT'S LOCAL DIRECTORY
% =========================================================================
disp(' ');

% Dynamically find the folder where this script is saved
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir)
    script_dir = pwd; % Fallback
end

% --- CLEAR OLD FILES ---
disp('Cleaning up old CSV files...');
old_files = {'ME9_Logs_Full.csv', 'ME9_Logs_WOT.csv', 'ME9_Logs_Warmup.csv', 'ME9_Logs_Hot.csv'};
for i = 1:length(old_files)
    target_file = fullfile(script_dir, old_files{i});
    if exist(target_file, 'file')
        delete(target_file);
    end
end

% --- SAVE NEW FILES ---
if ~isempty(Master_Log_Full)
    output_path_full = fullfile(script_dir, 'ME9_Logs_Full.csv');
    writetable(Master_Log_Full, output_path_full);
    disp(['Success! Saved FULL data to:   ', output_path_full]);
end

if ~isempty(Master_Log_WOT)
    output_path_wot = fullfile(script_dir, 'ME9_Logs_WOT.csv');
    writetable(Master_Log_WOT, output_path_wot);
    disp(['Success! Saved WOT data to:    ', output_path_wot]);
end

if ~isempty(Master_Log_Warmup)
    output_path_warmup = fullfile(script_dir, 'ME9_Logs_Warmup.csv');
    writetable(Master_Log_Warmup, output_path_warmup);
    disp(['Success! Saved WARMUP data to: ', output_path_warmup]);
end

if ~isempty(Master_Log_Hot)
    output_path_hot = fullfile(script_dir, 'ME9_Logs_Hot.csv');
    writetable(Master_Log_Hot, output_path_hot);
    disp(['Success! Saved HOT data to:    ', output_path_hot]);
end

if ALIGN_TIMESTAMPS == 1
    disp('*** Timestamps were successfully aligned and gaps were stitched. ***');
end
if HACK_5120 == 1
    disp('*** NOTE: 5120mbar Hack was ENABLED. All pressure values were multiplied by 2. ***');
end


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