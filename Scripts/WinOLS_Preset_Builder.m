% =========================================================================
% WINOLS PRESET BUILDER: 1-Click Extraction (Axes & Base Maps) & Auto-Save
% =========================================================================
clear; clc;

% --- 1. CONFIGURATION & PATH RESOLUTION ---
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end

export_folder = fullfile(script_dir, '..', 'ExportsFromWinols');
preset_folder = fullfile(script_dir, 'Presets');

% Hardcode the background template
base_json_template = fullfile(preset_folder, 'Bosch_ME9_Default.json'); 

% --- 1A. Select the WinOLS Data ---
disp('Waiting for user to select WinOLS export file...');
[win_file, win_path] = uigetfile(fullfile(export_folder, '*.csv'), 'Select the WinOLS Export File');

if isequal(win_file, 0)
    disp('*** File selection canceled. Script stopped. ***');
    return; 
end
winols_export_file = fullfile(win_path, win_file);


% --- 2. MAP MAPPING (WinOLS Name -> JSON Y-Axis, JSON X-Axis, JSON Base Map) ---
target_maps = {
    'KFLDIMX',  'rpm_boost',  'boost',       'base_kfldimx';    
    'KFLDRL',   'rpm_boost',  'kfldrl_x',    'base_kfldrl';
    'KFVPDKSD', 'rpm_kfvp',   'pratio_kfvp', 'base_kfvp';
    'FKKVS',    'rpm_fuel',   'te',          'base_fkkvs';
    'KFFWLW',   'rpm_kffwlw', 'load_kffwlw', 'base_kffwlw';
    'KFZW',     'rpm_ign',    'load_ign',    'base_kfzw';
    'KFPBRK',   'rpm_pbrk',   'load_pbrk',   'base_kfpbrk';
    'KFPBRKNW', 'rpm_pbrknw', 'load_pbrknw', 'base_kfpbrknw';
    'KFPRG',    'rpm_prg',    'vvt_prg',     'base_kfprg';
    'KFURL',    'rpm_url',    'vvt_url',     'base_kfurl'
};

%% --- 3. EXECUTION BLOCK ---
disp(' ');
disp('=======================================================');
disp('   WINOLS JSON PRESET BUILDER (AXES & BASE MAPS)');
disp('=======================================================');

% 1. Read the hidden Base JSON Template
if ~exist(base_json_template, 'file')
    error(['Cannot find background template: ', base_json_template]);
end
fid = fopen(base_json_template, 'r');
raw = fread(fid, inf); str = char(raw'); fclose(fid);
config = jsondecode(str);

% Ensure the base_maps struct exists in the config
if ~isfield(config, 'base_maps')
    config.base_maps = struct();
end

% 2. Read the WinOLS Export File
fid = fopen(winols_export_file, 'r');
lines = {};
while ~feof(fid)
    lines{end+1} = fgetl(fid); %#ok<SAGROW>
end
fclose(fid);
disp(['Loaded WinOLS Data: ', win_file]);
disp(' ');

% 3. Search and Extract Axes & Base Maps
maps_updated = 0;

for m = 1:size(target_maps, 1)
    target_winols_name = target_maps{m, 1};
    json_y_axis_name   = target_maps{m, 2};
    json_x_axis_name   = target_maps{m, 3};
    json_map_name      = target_maps{m, 4};
    
    for L = 1:length(lines)
        current_line = lines{L};
        parts = strsplit(current_line, ';');
        
        % Check if the line matches our target map
        if length(parts) > 15 && strcmp(strtrim(parts{2}), target_winols_name)
            
            % WinOLS Metadata for Map Dimensions (Columns=14, Rows=15)
            num_cols = str2double(parts{14});
            num_rows = str2double(parts{15});
            
            % WinOLS Data Strings
            z_values_str = parts{end-2}; % The flattened Map Data
            x_values_str = parts{end-1}; % X-Axis
            y_values_str = parts{end};   % Y-Axis
            
            x_array    = str2num(x_values_str); %#ok<ST2NM>
            y_array    = str2num(y_values_str); %#ok<ST2NM>
            z_array_1d = str2num(z_values_str); %#ok<ST2NM>
            
            if ~isempty(x_array) && ~isempty(y_array) && ~isempty(z_array_1d)
                
                % Inject Axes
                config.axes.(json_x_axis_name) = x_array;
                config.axes.(json_y_axis_name) = y_array;
                
                % Fold the 1D Z-data back into a 2D matrix (WinOLS exports row by row)
                % We transpose (') the reshape because MATLAB fills columns first naturally
                try
                    z_matrix = reshape(z_array_1d, [num_cols, num_rows])';
                    config.base_maps.(json_map_name) = z_matrix;
                    
                    disp(['SUCCESS: Extracted axes & map data for [ ', target_winols_name, ' ]']);
                    maps_updated = maps_updated + 1;
                catch
                    disp(['WARNING: [ ', target_winols_name, ' ] size mismatch. Expected ', num2str(num_rows), 'x', num2str(num_cols)]);
                end
                
            else
                disp(['WARNING: Found [ ', target_winols_name, ' ] but data fields were empty.']);
            end
            break; 
        end
    end
end

% --- 4. AUTO-SAVE AS NEW FILE ---
disp(' ');
if maps_updated > 0
    % Force 1D arrays to be row vectors before saving
    axes_fields = fieldnames(config.axes);
    for i = 1:length(axes_fields)
        config.axes.(axes_fields{i}) = config.axes.(axes_fields{i})(:)';
    end
    
    % Strip the .csv extension and append .json
    [~, base_name, ~] = fileparts(win_file);
    final_output_name = [base_name, '.json'];
    final_output_file = fullfile(preset_folder, final_output_name);
    
    json_txt = jsonencode(config, 'PrettyPrint', true); 
    fid = fopen(final_output_file, 'w');
    fwrite(fid, json_txt, 'char');
    fclose(fid);
    
    disp(['*** Success! Auto-saved ', num2str(maps_updated), ' maps/axes into: ', final_output_name, ' ***']);
else
    disp('*** No matching maps found in the WinOLS export. JSON was not generated. ***');
end