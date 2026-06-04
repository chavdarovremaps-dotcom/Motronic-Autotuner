% =========================================================================
% WINOLS PRESET BUILDER: Inject Axes & Base Maps into an existing Preset
% =========================================================================
clear; clc;

% --- 1. PATH RESOLUTION ---
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end

export_folder = fullfile(script_dir, '..', 'ExportsFromWinols');
preset_folder = fullfile(script_dir, 'presets');

% --- 1A. Select the Target JSON Preset ---
disp('Waiting for user to select the target JSON preset...');
[json_file, json_path] = uigetfile(fullfile(preset_folder, '*.json'), '1. Select the JSON Preset to Update');

if isequal(json_file, 0)
    disp('*** Preset selection canceled. Script stopped. ***');
    return; 
end
target_json_file = fullfile(json_path, json_file);

% --- 1B. Select the WinOLS Data ---
disp('Waiting for user to select WinOLS export file...');
[win_file, win_path] = uigetfile(fullfile(export_folder, '*.csv'), '2. Select the WinOLS Export File');

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
    'KFFWL',    'rpm_kffwl',  'tmot',        'base_kffwl';    
    'KFZW',     'rpm_ign',    'load_ign',    'base_kfzw';
    'KFPBRK',   'rpm_pbrk',   'load_pbrk',   'base_kfpbrk';
    'KFPBRKNW', 'rpm_pbrknw', 'load_pbrknw', 'base_kfpbrknw';
    'KFPRG',    'rpm_prg',    'vvt_prg',     'base_kfprg';
    'KFURL',    'rpm_url',    'vvt_url',     'base_kfurl'
};

%% --- 3. EXECUTION BLOCK ---
disp(' ');
disp('=======================================================');
disp('   WINOLS JSON PRESET BUILDER (SMART MATCH ENGINE)');
disp('=======================================================');

% 1. Read the Target JSON Preset
fid = fopen(target_json_file, 'r');
raw = fread(fid, inf); str = char(raw'); fclose(fid);
config = jsondecode(str);

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
disp(['Loaded Target JSON: ', json_file]);
disp(['Loaded WinOLS Data: ', win_file]);
disp(' ');

% 3. Search and Extract Axes & Base Maps
maps_updated = 0;
total_targets = size(target_maps, 1);
found_flags = false(total_targets, 1); % NEW: Track which maps we find

for m = 1:total_targets
    target_winols_name = target_maps{m, 1};
    json_y_axis_name   = target_maps{m, 2};
    json_x_axis_name   = target_maps{m, 3};
    json_map_name      = target_maps{m, 4};
    
    for L = 1:length(lines)
        current_line = lines{L};
        parts = strsplit(current_line, ';');
        
        if length(parts) > 15 
            map_name = strtrim(parts{2});
            is_match = strcmp(map_name, target_winols_name) || startsWith(map_name, [target_winols_name, '_']);
            
            if is_match
                found_flags(m) = true; % Mark as found!
                
                num_cols = str2double(parts{14});
                num_rows = str2double(parts{15});
                
                z_values_str = parts{end-2}; 
                x_values_str = parts{end-1}; 
                y_values_str = parts{end};   
                
                x_array    = str2num(x_values_str); %#ok<ST2NM>
                y_array    = str2num(y_values_str); %#ok<ST2NM>
                z_array_1d = str2num(z_values_str); %#ok<ST2NM>
                
                if isempty(y_array) && num_rows == 1
                    y_array = 0; 
                end
                
                if ~isempty(x_array) && ~isempty(y_array) && ~isempty(z_array_1d)
                    config.axes.(json_x_axis_name) = x_array;
                    config.axes.(json_y_axis_name) = y_array;
                    
                    try
                        z_matrix = reshape(z_array_1d, [num_cols, num_rows])';
                        config.base_maps.(json_map_name) = z_matrix;
                        
                        disp(['SUCCESS: Extracted data for [ ', map_name, ' ] mapped to -> ', target_winols_name]);
                        maps_updated = maps_updated + 1;
                    catch
                        disp(['WARNING: [ ', map_name, ' ] size mismatch. Expected ', num2str(num_rows), 'x', num2str(num_cols)]);
                    end
                else
                    disp(['WARNING: Found [ ', map_name, ' ] but data fields were empty.']);
                end
                break; 
            end
        end
    end
end

% --- 4. MISSING MAP SUMMARY (NEW) ---
disp(' ');
if any(~found_flags)
    disp('=======================================================');
    disp(' !!! WARNING: THE FOLLOWING MAPS WERE MISSING !!!');
    disp('=======================================================');
    for m = 1:total_targets
        if ~found_flags(m)
            disp(['   - ', target_maps{m, 1}]);
        end
    end
    disp('=======================================================');
    disp(' ');
end

% --- 5. AUTO-SAVE BACK TO SELECTED JSON ---
if maps_updated > 0
    % Force 1D arrays to be row vectors
    axes_fields = fieldnames(config.axes);
    for i = 1:length(axes_fields)
        config.axes.(axes_fields{i}) = config.axes.(axes_fields{i})(:)';
    end
    
    json_txt = jsonencode(config, 'PrettyPrint', true); 
    fid = fopen(target_json_file, 'w');
    fwrite(fid, json_txt, 'char');
    fclose(fid);
    
    disp(['*** Success! Injected ', num2str(maps_updated), ' maps/axes into: ', json_file, ' ***']);
else
    disp('*** No matching maps found in the WinOLS export. JSON was not updated. ***');
end