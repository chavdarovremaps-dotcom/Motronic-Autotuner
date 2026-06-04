% =========================================================================
% SIEMENS MS43 MASTER TUNING SUITE: Raw Parsing & 3D VE Generation
% =========================================================================
clear; clc; close all;

%% 1. GLOBAL CONTROL CENTER
% =========================================================================
% 1.1 WORKFLOW & FILE MANAGEMENT
% =========================================================================
PROCESS_RAW_LOGS = 1; % 1 = Parse raw folder & build Master Log, 0 = Skip to VE Tuning

raw_log_folder  = 'D:\Damos files\Matlab scripts\MS43Logs'; 
filename_log    = 'MS43_Master_Log.csv';      % Cached full data
filename_ve_log = 'MS43_ClosedLoop_VE.csv';   % Isolated VE tuning data
excel_filename  = 'MS43_Tuning_Maps.xlsx';

% =========================================================================
% 1.2 LOGGER VARIABLE NAMES (Fuzzy matching enabled)
% =========================================================================
log_vars.rpm        = 'Engine Speed';
log_vars.map        = 'Manifold Pressure';
log_vars.ve_table   = 'Active VE Table';
log_vars.load       = 'Engine Load Injection';
log_vars.inj        = 'Injection Time Average';  
log_vars.full_load  = 'Full Load';

% Fuel Trims
log_vars.stft_b1    = 'Short Term Fuel Trim Bank 1';
log_vars.ltft_m_b1  = 'Long Term Fuel Trim Multiplicative Bank 1'; 
log_vars.stft_b2    = 'Short Term Fuel Trim Bank 2';
log_vars.ltft_m_b2  = 'Long Term Fuel Trim Multiplicative Bank 2';

% Closed Loop Status
log_vars.lambda1    = 'Lambda Control 1';
log_vars.lambda2    = 'Lambda Control 2';

% =========================================================================
% 1.3 GLOBAL PROCESSING PARAMETERS
% =========================================================================
min_samples = 2; % Minimum statistical weight required to output a cell value

% =========================================================================
% 1.4 WINOLS MAP AXES (Siemens MS43 VE Tables)
% =========================================================================
axis_rpm_ve = [320, 704, 992, 1248, 1504, 2016, 2496, 3008, 3500, 4000, 4500, 4992, 5500, 6016, 6500, 7008];
axis_map_ve = [20.001, 30.001, 40.001, 50.002, 60.002, 70.002, 80.003, 90.003, 100.003, 120.004, 139.996, 159.997, 179.998, 199.998, 219.999, 240.000];
axis_ve_idx = 1:8; % The 8 VE Tables


%% 2. RAW LOG PROCESSING ENGINE
if PROCESS_RAW_LOGS == 1
    disp('--- STARTING RAW DATA EXTRACTION ---');
    file_pattern = fullfile(raw_log_folder, '*.csv');
    csv_files    = dir(file_pattern);
    Master_Log   = table(); 
    
    if isempty(csv_files)
        error(['No CSV files found in: ', raw_log_folder]);
    end

    for i = 1:length(csv_files)
        file_path = fullfile(csv_files(i).folder, csv_files(i).name);
        
        % TunerPro Header Bypass
        fid = fopen(file_path, 'r'); line1 = fgetl(fid); fclose(fid);
        if contains(line1, 'TunerPro')
            opts = detectImportOptions(file_path, 'NumHeaderLines', 1);
        else
            opts = detectImportOptions(file_path);
        end
        opts.VariableNamingRule = 'preserve'; 
        current_log = readtable(file_path, opts);
        if height(current_log) > 0, current_log(end, :) = []; end
        
        % High-Speed Column Scrubber
        all_vars = current_log.Properties.VariableNames; cols_to_remove = {};
        for c = 1:length(all_vars)
            col_name = all_vars{c}; col_data = current_log.(col_name);
            if ~isnumeric(col_data)
                str_data = strtrim(string(col_data)); 
                is_on_off = strcmpi(str_data, 'ON') | strcmpi(str_data, 'OFF');
                if sum(is_on_off) > (0.05 * length(str_data)) 
                    current_log.(col_name) = categorical(str_data);
                else
                    num_test = str2double(str_data);
                    if sum(~isnan(num_test)) > (0.1 * length(num_test))
                        current_log.(col_name) = num_test;
                    else
                        cols_to_remove{end+1} = col_name; %#ok<SAGROW>
                    end
                end
            end
        end
        if ~isempty(cols_to_remove)
            current_log = removevars(current_log, cols_to_remove);
            all_vars = current_log.Properties.VariableNames; 
        end
        
        % Fuzzy Header Matcher
        fields = fieldnames(log_vars);
        for f = 1:length(fields)
            target = log_vars.(fields{f});
            idx = find(strcmpi(all_vars, target), 1); 
            if isempty(idx), idx = find(contains(all_vars, target, 'IgnoreCase', true), 1); end
            if ~isempty(idx)
                current_log.Properties.VariableNames{idx} = target;
                all_vars{idx} = target; 
            end
        end
        
        % Smart NaN Filter
        initial_rows = height(current_log);
        critical_vars = {log_vars.rpm, log_vars.ve_table}; 
        valid_mask = true(initial_rows, 1);
        for v = 1:length(critical_vars)
            if ismember(critical_vars{v}, all_vars)
                valid_mask = valid_mask & ~isnan(current_log.(critical_vars{v}));
            end
        end
        current_log = current_log(valid_mask, :);
        
        try Master_Log = vertcat(Master_Log, current_log); catch, error('Table formats mismatched.'); end
        fprintf('Extracted %s: Kept %d valid rows.\n', csv_files(i).name, height(current_log));
    end
    
    script_dir = fileparts(mfilename('fullpath')); if isempty(script_dir), script_dir = pwd; end
    writetable(Master_Log, fullfile(script_dir, filename_log));
    disp(['Success! Saved master log to: ', filename_log]);
    disp(' ');
end


%% 3. VE CALIBRATION ENGINE
disp('--- LOADING MS43 DATA ---');
if ~exist(filename_log, 'file')
    error(['Log file not found: ', filename_log, '. Set PROCESS_RAW_LOGS = 1 to generate it!']);
end

opts = detectImportOptions(filename_log);
opts.VariableNamingRule = 'preserve';
data = readtable(filename_log, opts);
disp(['Log loaded successfully. Full workspace data contains ', num2str(height(data)), ' rows.']);
disp(' ');

disp('--- SMART CLOSED-LOOP & BANK DETECTION ---');
has_lambda1 = ismember(log_vars.lambda1, data.Properties.VariableNames);
has_lambda2 = ismember(log_vars.lambda2, data.Properties.VariableNames);
is_single_bank = false;

if has_lambda1 && has_lambda2
    str_L2 = strtrim(string(data.(log_vars.lambda2)));
    if sum(strcmpi(str_L2, 'ON')) == 0
        is_single_bank = true;
        disp('*** Detected Single Bank Operation (Lambda Control 2 is OFF). Using Bank 1 only. ***');
    else
        disp('Detected Dual Bank Operation. Averaging Bank 1 and Bank 2 trims.');
    end
elseif has_lambda1 && ~has_lambda2
    is_single_bank = true;
    disp('*** Detected Single Bank Operation (Lambda Control 2 not logged). Using Bank 1 only. ***');
end

if has_lambda1
    mask_L1 = strcmpi(strtrim(string(data.(log_vars.lambda1))), 'ON');
else
    mask_L1 = true(height(data), 1); 
end

if has_lambda2 && ~is_single_bank
    mask_L2 = strcmpi(strtrim(string(data.(log_vars.lambda2))), 'ON');
    valid_closed_loop = mask_L1 & mask_L2; 
else
    valid_closed_loop = mask_L1; 
end

data_ve = data(valid_closed_loop, :);
disp(['Extracted ', num2str(height(data_ve)), ' Closed-Loop rows for VE Calibration.']);
writetable(data_ve, filename_ve_log);
disp(' ');

disp('--- STARTING 3D TRILINEAR VE CALIBRATION ---');
try
    Trim_B1 = data_ve.(log_vars.stft_b1) + data_ve.(log_vars.ltft_m_b1);
    if is_single_bank
        Total_Trim_Pct = Trim_B1; 
    else
        Trim_B2 = data_ve.(log_vars.stft_b2) + data_ve.(log_vars.ltft_m_b2);
        Total_Trim_Pct = (Trim_B1 + Trim_B2) / 2; 
    end
    
    [VE_Maps_3D, VE_Counts_3D] = TrilinearSplatting(...
        data_ve.(log_vars.rpm), data_ve.(log_vars.map), data_ve.(log_vars.ve_table), Total_Trim_Pct, ...
        axis_rpm_ve, axis_map_ve, axis_ve_idx, min_samples);
        
    disp('Successfully generated all 8 VE Correction Tables.');
catch ME
    disp(['Error during VE Generation: ', ME.message]); return;
end
disp(' ');

disp('--- EXPORTING TO EXCEL ---');
ExportMS43MapsToExcel(excel_filename, VE_Maps_3D, VE_Counts_3D, axis_rpm_ve, axis_map_ve);
disp('Done!');


%% ========================================================================
% HELPER FUNCTIONS
% ========================================================================
function ExportMS43MapsToExcel(filename, VE_Maps_3D, VE_Counts_3D, x_axis, y_axis)
    output_cells = {};
    for z = 1:8 
        map_data1 = VE_Maps_3D(:,:,z); map_data2 = VE_Counts_3D(:,:,z);
        if all(isnan(map_data1(:))), continue; end 
        
        start_row = size(output_cells, 1) + 1; col_offset = length(x_axis) + 3; 
        output_cells{start_row, 1} = sprintf('VE Table %d Correction (%%)', z);
        output_cells{start_row, 1 + col_offset} = sprintf('VE Table %d - SAMPLE WEIGHTS', z);
        
        header_row = cell(1, length(x_axis) + 1); header_row{1} = 'MAP \ RPM'; 
        for c = 1:length(x_axis), header_row{c+1} = x_axis(c); end
        output_cells(start_row + 1, 1:length(header_row)) = header_row;
        output_cells(start_row + 1, (1 + col_offset):(length(header_row) + col_offset)) = header_row;
        
        current_r = start_row + 2;
        for r = 1:length(y_axis)
            data_row1 = cell(1, length(x_axis) + 1); data_row1{1} = y_axis(r); data_row2 = data_row1; 
            for c = 1:length(x_axis)
                if isnan(map_data1(r,c)), data_row1{c+1} = ''; else, data_row1{c+1} = round(map_data1(r,c), 3); end
                if isnan(map_data2(r,c)), data_row2{c+1} = ''; else, data_row2{c+1} = round(map_data2(r,c), 3); end
            end
            output_cells(current_r, 1:length(data_row1)) = data_row1;
            output_cells(current_r, (1 + col_offset):(length(data_row2) + col_offset)) = data_row2;
            current_r = current_r + 1;
        end
        output_cells{current_r, 1} = ''; 
    end
    if ~isempty(output_cells)
        writecell(output_cells, filename, 'Sheet', 'MS43 VE Maps');
        disp(['Success! Saved all VE maps to: ', filename]);
    end
end

function [Z_Map_3D, countArray_3D] = TrilinearSplatting(X_data, Y_data, Z_data, V_data, x_axis, y_axis, z_axis, min_samples)
    numCols = length(x_axis); numRows = length(y_axis); numDepths = length(z_axis); 
    sumArray_3D = zeros(numRows, numCols, numDepths); countArray_3D = zeros(numRows, numCols, numDepths);
    
    for i = 1:length(X_data)
        xVal = X_data(i); yVal = Y_data(i); zVal = Z_data(i); vVal = V_data(i);
        if ~isnan(xVal) && ~isnan(yVal) && ~isnan(zVal) && ~isnan(vVal)
            [xIdx, xFrac] = GetInterpolation(xVal, x_axis); 
            [yIdx, yFrac] = GetInterpolation(yVal, y_axis);
            [zIdx, zFrac] = GetInterpolation(zVal, z_axis);
            
            w000 = (1 - xFrac) * (1 - yFrac) * (1 - zFrac); w100 = xFrac * (1 - yFrac) * (1 - zFrac);
            w010 = (1 - xFrac) * yFrac * (1 - zFrac);       w110 = xFrac * yFrac * (1 - zFrac);
            w001 = (1 - xFrac) * (1 - yFrac) * zFrac;       w101 = xFrac * (1 - yFrac) * zFrac;
            w011 = (1 - xFrac) * yFrac * zFrac;             w111 = xFrac * yFrac * zFrac;
            
            sumArray_3D(yIdx, xIdx, zIdx) = sumArray_3D(yIdx, xIdx, zIdx) + (w000 * vVal); countArray_3D(yIdx, xIdx, zIdx) = countArray_3D(yIdx, xIdx, zIdx) + w000;
            if xIdx < numCols, sumArray_3D(yIdx, xIdx+1, zIdx) = sumArray_3D(yIdx, xIdx+1, zIdx) + (w100 * vVal); countArray_3D(yIdx, xIdx+1, zIdx) = countArray_3D(yIdx, xIdx+1, zIdx) + w100; end
            if yIdx < numRows, sumArray_3D(yIdx+1, xIdx, zIdx) = sumArray_3D(yIdx+1, xIdx, zIdx) + (w010 * vVal); countArray_3D(yIdx+1, xIdx, zIdx) = countArray_3D(yIdx+1, xIdx, zIdx) + w010; end
            if xIdx < numCols && yIdx < numRows, sumArray_3D(yIdx+1, xIdx+1, zIdx) = sumArray_3D(yIdx+1, xIdx+1, zIdx) + (w110 * vVal); countArray_3D(yIdx+1, xIdx+1, zIdx) = countArray_3D(yIdx+1, xIdx+1, zIdx) + w110; end
            
            if zIdx < numDepths
                sumArray_3D(yIdx, xIdx, zIdx+1) = sumArray_3D(yIdx, xIdx, zIdx+1) + (w001 * vVal); countArray_3D(yIdx, xIdx, zIdx+1) = countArray_3D(yIdx, xIdx, zIdx+1) + w001;
                if xIdx < numCols, sumArray_3D(yIdx, xIdx+1, zIdx+1) = sumArray_3D(yIdx, xIdx+1, zIdx+1) + (w101 * vVal); countArray_3D(yIdx, xIdx+1, zIdx+1) = countArray_3D(yIdx, xIdx+1, zIdx+1) + w101; end
                if yIdx < numRows, sumArray_3D(yIdx+1, xIdx, zIdx+1) = sumArray_3D(yIdx+1, xIdx, zIdx+1) + (w011 * vVal); countArray_3D(yIdx+1, xIdx, zIdx+1) = countArray_3D(yIdx+1, xIdx, zIdx+1) + w011; end
                if xIdx < numCols && yIdx < numRows, sumArray_3D(yIdx+1, xIdx+1, zIdx+1) = sumArray_3D(yIdx+1, xIdx+1, zIdx+1) + (w111 * vVal); countArray_3D(yIdx+1, xIdx+1, zIdx+1) = countArray_3D(yIdx+1, xIdx+1, zIdx+1) + w111; end
            end
        end
    end
    
    Z_Map_3D = NaN(numRows, numCols, numDepths);
    for z = 1:numDepths
        for r = 1:numRows
            for c = 1:numCols
                if countArray_3D(r, c, z) >= min_samples, Z_Map_3D(r, c, z) = sumArray_3D(r, c, z) / countArray_3D(r, c, z); end
            end
        end
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