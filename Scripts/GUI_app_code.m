classdef MotronicTuner_GUI < matlab.apps.AppBase

    % Properties that correspond to app components
    properties (Access = public)
        UIFigure                        matlab.ui.Figure
        TabGroup                        matlab.ui.container.TabGroup
        ECUProfileTab                   matlab.ui.container.Tab
        Var_Knock_EditField             matlab.ui.control.EditField
        InjectorOntimeLabel_4           matlab.ui.control.Label
        Var_AmbientPres_EditField       matlab.ui.control.EditField
        InjectorOntimeLabel_3           matlab.ui.control.Label
        Var_Coolant_temp_EditField      matlab.ui.control.EditField
        InjectorOntimeLabel_2           matlab.ui.control.Label
        Var_Inj_OnTime_EditField        matlab.ui.control.EditField
        InjectorOntimeLabel             matlab.ui.control.Label
        MapViewerclickonamapinthetableabovetoviewitLabel  matlab.ui.control.Label
        Map_Viewer_Table                matlab.ui.control.Table
        Map_Status_Lamp                 matlab.ui.control.Lamp
        StatusLabel                     matlab.ui.control.Label
        Map_Status_Table                matlab.ui.control.Table
        WinOLS_CSV_EditField            matlab.ui.control.EditField
        WinOLSCSVExportLabel            matlab.ui.control.Label
        ImportWinOLS_Button             matlab.ui.control.Button
        ImportWinOLSCSVExportLabel      matlab.ui.control.Label
        SaveAsNewProfileButton          matlab.ui.control.Button
        LoadExistingProfileButton       matlab.ui.control.Button
        VariableProfileActionsLabel     matlab.ui.control.Label
        PressureColumnsEditFieldLabel   matlab.ui.control.Label
        Hack_5120_Switch                matlab.ui.control.Switch
        mbarHackSwitchLabel             matlab.ui.control.Label
        Align_Time_Switch               matlab.ui.control.Switch
        AlignTimestampsSwitchLabel      matlab.ui.control.Label
        Pressure_Cols_EditField         matlab.ui.control.EditField
        PreProcessingRulesLabel         matlab.ui.control.Label
        Var_LTFT_EditField              matlab.ui.control.EditField
        Var_LTFTEditFieldLabel          matlab.ui.control.Label
        Var_Time_EditField              matlab.ui.control.EditField
        Var_TimeEditFieldLabel          matlab.ui.control.Label
        Var_VVT_EditField               matlab.ui.control.EditField
        Var_VVTEditFieldLabel           matlab.ui.control.Label
        Var_STFT_EditField              matlab.ui.control.EditField
        Var_STFTEditFieldLabel          matlab.ui.control.Label
        Var_Manifold_EditField          matlab.ui.control.EditField
        Var_ManifoldEditFieldLabel      matlab.ui.control.Label
        Var_WGDC_EditField              matlab.ui.control.EditField
        Var_WGDCEditFieldLabel          matlab.ui.control.Label
        Var_Pedal_EditField             matlab.ui.control.EditField
        Var_PedalEditFieldLabel         matlab.ui.control.Label
        Var_Boost_EditField             matlab.ui.control.EditField
        Var_BoostEditFieldLabel         matlab.ui.control.Label
        Var_Load_EditField              matlab.ui.control.EditField
        Var_LoadEditFieldLabel          matlab.ui.control.Label
        LoggerVariableMappingLabel      matlab.ui.control.Label
        Var_RPM_EditField               matlab.ui.control.EditField
        Var_RPMEditFieldLabel           matlab.ui.control.Label
        DataIngestionFilteringTab       matlab.ui.container.Tab
        WOT_Min_EditField               matlab.ui.control.NumericEditField
        WOTMinimumPedalEditFieldLabel_2  matlab.ui.control.Label
        Temp_Max_EditField              matlab.ui.control.NumericEditField
        WarmupMaxTempCEditFieldLabel_2  matlab.ui.control.Label
        GeneralMathFuelSettingsLabel    matlab.ui.control.Label
        Console_TextArea                matlab.ui.control.TextArea
        OutputLabel                     matlab.ui.control.Label
        MinSamplesperCellEditFieldLabel_5  matlab.ui.control.Label
        Max_Throttle_ROC_EditField      matlab.ui.control.NumericEditField
        MinSamplesperCellEditFieldLabel_4  matlab.ui.control.Label
        Max_RPM_ROC_EditField           matlab.ui.control.NumericEditField
        Safety_Margin_EditField         matlab.ui.control.NumericEditField
        MinSamplesperCellEditFieldLabel_3  matlab.ui.control.Label
        Min_Samples_WG_EditField        matlab.ui.control.NumericEditField
        MinSamplesperCellEditFieldLabel_2  matlab.ui.control.Label
        CWLDIMX_Switch                  matlab.ui.control.Switch
        CWLDIMXSwitchLabel              matlab.ui.control.Label
        Fill_Missing_Data_Switch        matlab.ui.control.Switch
        FillMissingDataSwitchLabel      matlab.ui.control.Label
        BoostWastegateSettingsLabel     matlab.ui.control.Label
        Trim_Format_DropDown            matlab.ui.control.DropDown
        FuelTrimformatDropDownLabel     matlab.ui.control.Label
        Ambient_Pressure_EditField      matlab.ui.control.NumericEditField
        AmbientpressurehpaEditFieldLabel  matlab.ui.control.Label
        VVTSettingsLabel                matlab.ui.control.Label
        DataIngestionLabel              matlab.ui.control.Label
        DataStatus_Lamp                 matlab.ui.control.Lamp
        StatusLampLabel                 matlab.ui.control.Label
        Log_Folder_EditField            matlab.ui.control.EditField
        LogsFolderEditFieldLabel        matlab.ui.control.Label
        LoadLogs_Button                 matlab.ui.control.Button
        Min_Samples_EditField           matlab.ui.control.NumericEditField
        MinSamplesperCellEditFieldLabel  matlab.ui.control.Label
        VVT_Threshold_EditField         matlab.ui.control.NumericEditField
        VVTThresholddegEditFieldLabel   matlab.ui.control.Label
        VVT_Enabled_Switch              matlab.ui.control.Switch
        VVTSystemSwitchLabel            matlab.ui.control.Label
        CalculateTab                    matlab.ui.container.Tab
        Calc_Viewer_Table               matlab.ui.control.Table
        Calc_Status_Table               matlab.ui.control.Table
        Calc_Export_Button              matlab.ui.control.Button
        CalculationControlLabel         matlab.ui.control.Label
        KFVPDKSEMED91Tab                matlab.ui.container.Tab
        ME7_Viewer_Table                matlab.ui.control.Table
        KFVPDKSDME7equivalentAbsoluteraitoLabel  matlab.ui.control.Label
        KFVPDKSEMED9RelativeRatioLabel  matlab.ui.control.Label
        MED9_Viewer_Table               matlab.ui.control.Table
        Calc_KFVPDKSE_Button            matlab.ui.control.Button
        MED9_IAT_EditField              matlab.ui.control.NumericEditField
        MED9_IAT_EditFieldLabel         matlab.ui.control.Label
        MED9_Ambient_EditField          matlab.ui.control.NumericEditField
        MED9_Ambient_EditFieldLabel     matlab.ui.control.Label
    end

    
properties (Access = public)
    % --- Data Storage ---
    ConfigData       
    LogDataRaw       
    LogDataFull      % Generated by the split button
    LogDataWOT       % Generated by the split button
    LogDataWarmup    % Added for Temp Filter
    LogDataHot       % Added for Temp Filter
    
    % --- Engine & Environment ---
    VVT_Enabled (1,1) double = 1
    VVT_Threshold (1,1) double = 20
    Ambient_Pressure (1,1) double = 1000
    Trim_Format (1,:) char = 'ME7'
    
    % --- Calculation Rules ---
    Fill_Missing_Data (1,1) double = 0
    CWLDIMX_Active (1,1) double = 0
    Min_Samples (1,1) double = 10
    Min_Samples_Base_WG (1,1) double = 5
    Safety_Margin (1,1) double = 0
    
    % --- Transient Filters ---
    Max_RPM_ROC (1,1) double = 2000      % Max allowed RPM change per second
    Max_Pedal_ROC (1,1) double = 50      % Max allowed Pedal % change per second
    
    % --- Factory Definitions (Added to fix the error) ---
    AxesData 
    BaseMapsData 
    % --- Calculation Results ---
    CalculatedMaps struct
    % --- App Configuration ---
    TargetMaps cell  % Master list of WinOLS maps to import and track

end

    % Callbacks that handle component events
    methods (Access = private)

        % Code that executes after component creation
        function startupFcn(app)
            % Add the Utilities folder to the MATLAB path on startup
            addpath(fullfile(pwd, 'Utilities'));
    % Define the master list of all tuning maps exactly ONCE
    % Columns: 1=Name, 2=Y-Axis(Rows), 3=X-Axis(Cols), 4=Variable, 5=Calibration Area
    app.TargetMaps = {
        'KFLDIMX',  'rpm_boost',  'boost',       'base_kfldimx',  'Boost Control';    
        'KFLDRL',   'rpm_boost',  'kfldrl_x',    'base_kfldrl',   'Boost Control';
        'KFVPDKSD', 'rpm_kfvp',     'pratio_kfvp',    'base_kfvp',     'Throttle Handover';
        'FKKVS',    'rpm_fuel',   'te',          'base_fkkvs',    'Fueling';
        'KFFWLW',   'rpm_kffwlw', 'load_kffwlw', 'base_kffwlw',   'Warmup Enrichment';
        'KFFWL',    'tmot',       'kffwl_trim',  'base_kffwl',    'Warmup Enrichment';
        'KFZW',     'rpm_ign',    'load_ign',    'base_kfzw',     'Ignition Timing';
        'KFPBRK',   'rpm_pbrk',   'load_pbrk',   'base_kfpbrk',   'Saugrohrmodell';
        'KFPBRKNW', 'rpm_pbrknw', 'load_pbrknw', 'base_kfpbrknw', 'Saugrohrmodell';
        'KFPRG',    'rpm_prg',    'vvt_prg',     'base_kfprg',    'Saugrohrmodell';
        'KFURL',    'rpm_url',    'vvt_url',     'base_kfurl',    'Saugrohrmodell';
        
        % --- MED9 MAPS ---
        'KFLDHBN',  'temp_kfldhbn',   'rpm_kfldhbn',  'base_kfldhbn',  'Boost (MED9.1)';
        'KFVPDKSE', 'ratio_kfvpdkse', 'rpm_kfvpdkse', 'base_kfvpdkse', 'Throttle (MED9.1)'
    };
        end

        % Button pushed function: LoadLogs_Button
        function LoadLogs_ButtonPushed(app, event)

% 1. Verify Tab 1 is active
if isempty(app.ConfigData)
    uialert(app.UIFigure, 'Please load or create an ECU Profile in Tab 1 first!', 'Missing Configuration', 'Icon', 'warning');
    return;
end
% 1. Open the folder selection dialog
selected_folder = uigetdir(pwd, 'Select Folder Containing Raw CSV Logs');

% 2. Check if the user clicked 'Cancel'
if selected_folder == 0
    return; 
end

% 3. Push the chosen folder path into the text box so the Execution button can see it
app.Log_Folder_EditField.Value = selected_folder;
% 2. Verify Log Folder
log_folder = app.Log_Folder_EditField.Value;
if isempty(log_folder) || ~isfolder(log_folder)
    uialert(app.UIFigure, 'Please select a valid folder containing your raw CSV logs.', 'Missing Data', 'Icon', 'warning');
    return;
end

% 3. Update UI to show processing state
app.DataStatus_Lamp.Color = [1 1 0]; % Yellow
app.Console_TextArea.Value = {'Starting log ingestion...'; 'Applying transient filters... please wait.'};
drawnow; 

% 4. Grab dynamic session filters & Live Math Rules
max_rpm_rate = app.Max_RPM_ROC_EditField.Value;
max_throttle_rate = app.Max_Throttle_ROC_EditField.Value;
wot_min = app.WOT_Min_EditField.Value;
temp_max = app.Temp_Max_EditField.Value;

% Update the ambient pressure in memory before saving the backup
app.ConfigData.params.ambient_pressure = app.Ambient_Pressure_EditField.Value;

% 5. Save a backup of the profile to the log folder (Traceability!)
try
    backup_path = fullfile(log_folder, 'Used_ECU_Profile.json');
    json_txt = jsonencode(app.ConfigData, 'PrettyPrint', true);
    fid = fopen(backup_path, 'w');
    fwrite(fid, json_txt, 'char');
    fclose(fid);
catch ME
    disp(['Could not save backup JSON: ', ME.message]); % Non-fatal warning
end

% 6. Execute the ProcessRawLogs function
try
    [app.LogDataFull, app.LogDataWOT, app.LogDataWarmup, app.LogDataHot] = ...
        ProcessRawLogs(log_folder, app.ConfigData, max_rpm_rate, max_throttle_rate, wot_min, temp_max);
    
    % Build a success message for the Console
    success_msg = {
        '--- SUCCESS: Logs Split & Filtered ---';
        sprintf('FULL Data: %d rows', height(app.LogDataFull));
        sprintf('WOT Data: %d rows', height(app.LogDataWOT));
        sprintf('WARMUP Data: %d rows', height(app.LogDataWarmup));
        sprintf('HOT Data: %d rows', height(app.LogDataHot));
        'Saved backup JSON profile to log folder.';
        'Ready for Calibration Math.'
    };
    
    app.Console_TextArea.Value = success_msg;
    app.DataStatus_Lamp.Color = [0 1 0]; % Green
    
catch ME
    app.DataStatus_Lamp.Color = [1 0 0]; % Red
    app.Console_TextArea.Value = {'ERROR PROCESSING LOGS:'; ME.message};
end
        end

        % Button pushed function: SaveAsNewProfileButton
        function SaveAsNewProfileButtonPushed(app, event)
         % 1. Rebuild the config structure
config = struct();

% --- Files ---
config.files.raw_log_folder   = ''; % Left blank intentionally
config.files.filename_wot     = 'ME_Logs_WOT.csv';    
config.files.filename_full    = 'ME_Logs_Full.csv';   
config.files.filename_warmup  = 'ME_Logs_Warmup.csv'; 
config.files.filename_hot     = 'ME_Logs_Hot.csv';
config.files.excel_filename   = 'ME_Tuning_Maps.xlsx';

% --- Logger Variables (Pulled from UI) ---
config.vars.rpm     = app.Var_RPM_EditField.Value;      
config.vars.wgdc    = app.Var_WGDC_EditField.Value;       
config.vars.boost   = app.Var_Boost_EditField.Value;     
config.vars.pu      = app.Var_AmbientPres_EditField.Value;         
config.vars.inj     = app.Var_Inj_OnTime_EditField.Value;  
config.vars.stft    = app.Var_STFT_EditField.Value;       
config.vars.ltft    = app.Var_LTFT_EditField.Value;       
config.vars.load    = app.Var_Load_EditField.Value;        
config.vars.knock   = app.Var_Knock_EditField.Value;      
config.vars.vvt     = app.Var_VVT_EditField.Value;      
config.vars.tmot    = app.Var_Coolant_temp_EditField.Value; 
config.vars.pedal   = app.Var_Pedal_EditField.Value;
config.vars.ps_w    = app.Var_Manifold_EditField.Value;
config.vars.time    = app.Var_Time_EditField.Value;

% --- Hardware Prep Settings ---
if strcmp(app.Align_Time_Switch.Value, 'On')
    config.prep.ALIGN_TIMESTAMPS = 1; 
else
    config.prep.ALIGN_TIMESTAMPS = 0; 
end

if strcmp(app.Hack_5120_Switch.Value, 'On')
    config.prep.HACK_5120 = 1; 
else
    config.prep.HACK_5120 = 0; 
end

raw_pressures = app.Pressure_Cols_EditField.Value;
config.prep.pressure_columns = strtrim(strsplit(raw_pressures, ','));

% --- Global Parameters ---
config.params.min_samples         = app.Min_Samples_EditField.Value;          
config.params.min_samples_base_wg = app.Min_Samples_WG_EditField.Value;          
config.params.trim_format         = app.Trim_Format_DropDown.Value;          
% Pull WGDC axis from imported KFLDRL, or fallback to default if not yet imported
if isfield(app.AxesData, 'axis_kfldrl_x')
    config.params.axis_wgdc_splat = app.AxesData.axis_kfldrl_x;
else
    config.params.axis_wgdc_splat = 0:5:95; % Safe fallback
end
config.params.ambient_pressure    = app.Ambient_Pressure_EditField.Value;       
config.params.safety_margin       = app.Safety_Margin_EditField.Value;  
config.params.vvt_threshold       = app.VVT_Threshold_EditField.Value;
config.params.max_rpm_roc         = app.Max_RPM_ROC_EditField.Value;
config.params.max_throttle_roc    = app.Max_Throttle_ROC_EditField.Value;
config.params.temp_max            = app.Temp_Max_EditField.Value;
config.params.wot_min             = app.WOT_Min_EditField.Value;

% Switches (Saving as 1 or 0 boolean logic for JSON cleanliness)
config.params.VVT_ENABLED         = strcmp(app.VVT_Enabled_Switch.Value, 'On');
config.params.CWLDIMX             = strcmp(app.CWLDIMX_Switch.Value, 'On');
config.params.FILL_MISSING_DATA   = strcmp(app.Fill_Missing_Data_Switch.Value, 'On'); 

% --- Map Axes and Base Maps ---
if isempty(app.AxesData)
    config.axes = struct(); 
else
    config.axes = app.AxesData;
end

if isempty(app.BaseMapsData)
    config.base_maps = struct();
else
    config.base_maps = app.BaseMapsData;
end

% 2. Open Save Dialog
[save_file, save_path] = uiputfile('*.json', 'Save New ECU Template As');
if isequal(save_file, 0), return; end

% 3. Write to JSON
json_txt = jsonencode(config, 'PrettyPrint', true); 
fid = fopen(fullfile(save_path, save_file), 'w'); 
fwrite(fid, json_txt, 'char'); 
fclose(fid);

app.ConfigData = config; % Instantly activates the new profile for Tab 2!

uialert(app.UIFigure, ['Successfully created Template: ', save_file], 'Success', 'Icon', 'success');
        end

        % Button pushed function: ImportWinOLS_Button
        function ImportWinOLS_ButtonPushed(app, event)
    % 1. Ask user to select the master WinOLS CSV Export
    [win_file, win_path] = uigetfile('*.csv', 'Select the WinOLS Export File');
    if isequal(win_file, 0), return; end % User canceled
    winols_export_file = fullfile(win_path, win_file);
    app.WinOLS_CSV_EditField.Value = winols_export_file;
    app.Map_Status_Lamp.Color = [1 1 0]; % Yellow (Processing)
    drawnow;
    
    % 2. Define the Target Maps (WinOLS Name -> Y-axis, X-axis, Base Map)
    % definition moved to startup of the app
    
    % 3. Initialize fresh memory structs
    app.AxesData = struct();
    app.BaseMapsData = struct();
    
    % 4. Initialize Table Data Array
    total_targets = size(app.TargetMaps, 1);
    found_flags = false(total_targets, 1);
    maps_updated = 0;
    
    % Pre-fill the table data with "Missing" as the default state
    table_data = cell(total_targets, 4);
    for m = 1:total_targets
        table_data{m, 1} = app.TargetMaps{m, 1};  % Map Name
        table_data{m, 2} = '❌ Missing';           % Default Status
        table_data{m, 3} = '-';                   % Default Dimensions
        table_data{m, 4} = app.TargetMaps{m, 5};  % Calibration Area
    end
    
    % 5. The Smart-Match Engine
    try
        fid = fopen(winols_export_file, 'r');
        lines = {};
        while ~feof(fid)
            lines{end+1} = fgetl(fid); %#ok<SAGROW>
        end
        fclose(fid);
        
        for m = 1:total_targets
            target_winols_name = app.TargetMaps{m, 1};
            json_y_axis_name   = app.TargetMaps{m, 2};
            json_x_axis_name   = app.TargetMaps{m, 3};
            json_map_name      = app.TargetMaps{m, 4};
            
            for L = 1:length(lines)
                current_line = lines{L};
                parts = strsplit(current_line, ';');
                
                if length(parts) > 15 
                    map_name = strtrim(parts{2});
                    is_match = strcmp(map_name, target_winols_name) || startsWith(map_name, [target_winols_name, '_']);
                    
                    if is_match
                        found_flags(m) = true; 
                        
                        num_cols = str2double(parts{14});
                        num_rows = str2double(parts{15});
                        
                        x_array = str2num(parts{end-1}); %#ok<ST2NM>
                        y_array = str2num(parts{end});   %#ok<ST2NM>
                        z_array_1d = str2num(parts{end-2}); %#ok<ST2NM>
                        
                        if isempty(y_array) && num_rows == 1, y_array = 0; end
                        
                        if ~isempty(x_array) && ~isempty(y_array) && ~isempty(z_array_1d)
                            len_x = length(x_array);
                            len_y = length(y_array);
                            
                            % 1. Detect if WinOLS structurally messed up the array lengths
                            is_size_mismatch = (len_x ~= num_cols) || (len_y ~= num_rows);
                            can_size_heal = (len_x == num_rows) && (len_y == num_cols) && (num_rows ~= num_cols);
                            
                            % 2. THE EXPLICIT SEMANTIC CHECK
                            x_name = lower(strtrim(parts{8}));
                            x_unit = lower(strtrim(parts{9}));
                            
                            name_has_rpm = contains(x_name, 'motordrehzahl') || contains(x_name, 'rpm') || contains(x_name, 'giri');
                            unit_has_rpm = contains(x_unit, 'u/min') || contains(x_unit, 'rpm') || contains(x_unit, '1/min') || contains(x_unit, 'giri');
                            x_is_rpm_text = name_has_rpm || unit_has_rpm;
                                                    
                            json_expects_rpm_y = contains(lower(json_y_axis_name), 'rpm');
                            needs_semantic_flip = json_expects_rpm_y && x_is_rpm_text;
                            
                          try
                                % Base structural reshape (Yields [num_rows, num_cols])
                                z_matrix = reshape(z_array_1d, [num_cols, num_rows])';
                                
                                % =========================================================
                                % --- THE THROTTLE / MED9 INTERCEPT ---
                                % =========================================================
                                if strcmp(target_winols_name, 'KFVPDKSE') || strcmp(target_winols_name, 'KFLDHBN') || strcmp(target_winols_name, 'KFVPDKSD')
                                    
                                    app.BaseMapsData.(json_map_name) = z_matrix;
                                    
                                    % Direct logical assignment:
                                    % x_array natively holds the Columns (e.g., 12 RPMs)
                                    % y_array natively holds the Rows (e.g., 8 Ratios/Temps)
                                    app.AxesData.(json_x_axis_name) = x_array(:)'; 
                                    app.AxesData.(json_y_axis_name) = y_array(:)'; 
                                    
                                    table_data{m, 2} = '✅ Loaded (Direct)';
                                    table_data{m, 3} = sprintf('%d x %d', num_rows, num_cols);
                                    maps_updated = maps_updated + 1;
                                    
                                    % Skip the legacy ME7 transpose logic entirely!
                                    break; 
                                end
                                % =========================================================
                                
                                % --- ROUTING ENGINE (Legacy ME7) ---
                                if needs_semantic_flip
                                    % WinOLS put RPM on X. We MUST physically transpose the matrix and swap axes!
                                    app.BaseMapsData.(json_map_name) = z_matrix'; % Transpose!
                                    app.AxesData.(json_x_axis_name) = y_array(:)';
                                    app.AxesData.(json_y_axis_name) = x_array(:)';
                                    
                                    table_data{m, 2} = '🔄 RPM Flipped';
                                    table_data{m, 3} = sprintf('%d x %d', num_cols, num_rows); 
                                    maps_updated = maps_updated + 1;
                                    
                                elseif is_size_mismatch
                                    if can_size_heal
                                        % The lengths were backward (WinOLS exported it sideways).
                                        % RULE: Never swap the axes variables. Transpose the map instead!
                                        app.BaseMapsData.(json_map_name) = z_matrix'; % Transpose the map data
                                        
                                        % Safely assign X to X, and Y to Y
                                        app.AxesData.(json_x_axis_name) = x_array(:)';
                                        app.AxesData.(json_y_axis_name) = y_array(:)';
                                        
                                        table_data{m, 2} = '🔄 Size Auto-Transposed';
                                        table_data{m, 3} = sprintf('%d x %d', num_cols, num_rows); % Display the new rotated size
                                        maps_updated = maps_updated + 1;
                                    else
                                        table_data{m, 2} = '⚠️ Axis Size Mismatch';
                                    end
                                else
                                    % Standard perfect load
                                    app.BaseMapsData.(json_map_name) = z_matrix;
                                    app.AxesData.(json_x_axis_name) = x_array(:)';
                                    app.AxesData.(json_y_axis_name) = y_array(:)';
                                    
                                    table_data{m, 2} = '✅ Loaded';
                                    table_data{m, 3} = sprintf('%d x %d', num_rows, num_cols);
                                    maps_updated = maps_updated + 1;
                                end
                                
                            catch
                                table_data{m, 2} = '⚠️ Matrix Error';
                            end
                        end
                        break; 
                    end
                end
            end
        end
        
        % 6. Push data to the UI Table
        % Note: Set to push all 4 columns including Calibration Area
        app.Map_Status_Table.Data = table_data;
        
        % 7. Overall Status Lamp
        if any(~found_flags)
            app.Map_Status_Lamp.Color = [1 0.5 0]; % Orange/Warning if maps are missing
        else
            app.Map_Status_Lamp.Color = [0 1 0]; % Solid Green if perfect
        end
    catch ME
        app.Map_Status_Lamp.Color = [1 0 0]; % Red
        uialert(app.UIFigure, ['Failed to read CSV: ', ME.message], 'Error', 'Icon', 'error');
    end

        end

        % Cell selection callback: Map_Status_Table
        function Map_Status_TableCellSelection(app, event)
% 1. Get the row the user just clicked
indices = event.Indices;
if isempty(indices)
    return; % User clicked empty space
end
selected_row = indices(1, 1);

% 2. Get the WinOLS name of the map they clicked (e.g., 'KFURL')
clicked_map_name = app.Map_Status_Table.Data{selected_row, 1};

% 3. The Dictionary (To translate WinOLS name to your memory structs)
% Definition of the maps is moved into startup

% Find the matching row in our dictionary
dict_idx = find(strcmp(app.TargetMaps(:, 1), clicked_map_name));
if isempty(dict_idx)
    return; 
end

json_y_axis_name = app.TargetMaps{dict_idx, 2};
json_x_axis_name = app.TargetMaps{dict_idx, 3};
json_map_name    = app.TargetMaps{dict_idx, 4};

% 4. Push the Data to the Viewer Table
try
    % Check if the map actually loaded successfully
    if isfield(app.BaseMapsData, json_map_name) && ~isempty(app.BaseMapsData.(json_map_name))
        
        % Send the Z-Matrix to the table
        app.Map_Viewer_Table.Data = app.BaseMapsData.(json_map_name);
        
        % --- Apply the X and Y Axes as Table Headers ---
        % Check if X-Axis exists
        if isfield(app.AxesData, json_x_axis_name)
            x_axis = app.AxesData.(json_x_axis_name);
            app.Map_Viewer_Table.ColumnName = string(num2cell(x_axis));
        else
            app.Map_Viewer_Table.ColumnName = 'numbered';
        end
        
        % Check if Y-Axis exists
        if isfield(app.AxesData, json_y_axis_name)
            y_axis = app.AxesData.(json_y_axis_name);
            app.Map_Viewer_Table.RowName = string(num2cell(y_axis));
        else
            app.Map_Viewer_Table.RowName = 'numbered';
        end
        
    else
        % Clear the table if they click a map that failed to load
        app.Map_Viewer_Table.Data = [];
        app.Map_Viewer_Table.ColumnName = 'numbered';
        app.Map_Viewer_Table.RowName = 'numbered';
    end
catch ME
    disp(['Viewer Error: ', ME.message]);
end
            
        end

        % Button pushed function: LoadExistingProfileButton
        function LoadExistingProfileButtonPushed(app, event)
            % 1. Ask user to select the JSON Profile
[json_file, json_path] = uigetfile('*.json', 'Select ECU Profile to Load');
if isequal(json_file, 0), return; end % User canceled

target_file = fullfile(json_path, json_file);

try
    % 2. Read and decode the JSON file
    raw_text = fileread(target_file);
    config = jsondecode(raw_text);
    
    % Save to app memory globally
    app.ConfigData = config; 
    
    % 3. Populate Panel 1: Logger Variables
    if isfield(config, 'vars')
        app.Var_RPM_EditField.Value = config.vars.rpm;
        app.Var_Load_EditField.Value = config.vars.load;
        app.Var_Pedal_EditField.Value = config.vars.pedal;
        app.Var_Boost_EditField.Value = config.vars.boost;
        app.Var_Manifold_EditField.Value = config.vars.ps_w;
        app.Var_WGDC_EditField.Value = config.vars.wgdc;
        app.Var_VVT_EditField.Value = config.vars.vvt;
        app.Var_Inj_OnTime_EditField.Value = config.vars.inj;
        app.Var_STFT_EditField.Value = config.vars.stft;
        app.Var_LTFT_EditField.Value = config.vars.ltft;
        app.Var_Coolant_temp_EditField.Value = config.vars.tmot;
        app.Var_AmbientPres_EditField.Value = config.vars.pu;
        app.Var_Knock_EditField.Value = config.vars.knock;
        app.Var_Time_EditField.Value = config.vars.time;
    end
    
    % 4. Populate Panel 2: Pre-Processing Rules
    if isfield(config, 'prep')
        if config.prep.ALIGN_TIMESTAMPS
            app.Align_Time_Switch.Value = 'On';
        else
            app.Align_Time_Switch.Value = 'Off';
        end
        
        if config.prep.HACK_5120
            app.Hack_5120_Switch.Value = 'On';
        else
            app.Hack_5120_Switch.Value = 'Off';
        end
        
        % Convert cell array back to comma-separated string
        if iscell(config.prep.pressure_columns)
            app.Pressure_Cols_EditField.Value = strjoin(config.prep.pressure_columns, ', ');
        end
    end

    % 4.5. Populate Global Parameters / Data Ingestion Tab
    if isfield(config, 'params')
        % Restore Numeric and DropDown Fields
        if isfield(config.params, 'min_samples'), app.Min_Samples_EditField.Value = config.params.min_samples; end
        if isfield(config.params, 'min_samples_base_wg'), app.Min_Samples_WG_EditField.Value = config.params.min_samples_base_wg; end
        if isfield(config.params, 'trim_format'), app.Trim_Format_DropDown.Value = config.params.trim_format; end
        if isfield(config.params, 'ambient_pressure'), app.Ambient_Pressure_EditField.Value = config.params.ambient_pressure; end
        if isfield(config.params, 'safety_margin'), app.Safety_Margin_EditField.Value = config.params.safety_margin; end
        if isfield(config.params, 'vvt_threshold'), app.VVT_Threshold_EditField.Value = config.params.vvt_threshold; end
        if isfield(config.params, 'max_rpm_roc'), app.Max_RPM_ROC_EditField.Value = config.params.max_rpm_roc; end
        if isfield(config.params, 'max_throttle_roc'), app.Max_Throttle_ROC_EditField.Value = config.params.max_throttle_roc; end
        if isfield(config.params, 'temp_max'), app.Temp_Max_EditField.Value = config.params.temp_max; end
        if isfield(config.params, 'wot_min'), app.WOT_Min_EditField.Value = config.params.wot_min; end

        % Restore Switch Fields (Convert 1/0 or true/false back to 'On'/'Off' Strings)
        if isfield(config.params, 'VVT_ENABLED')
            if config.params.VVT_ENABLED, app.VVT_Enabled_Switch.Value = 'On'; else, app.VVT_Enabled_Switch.Value = 'Off'; end
        end
        if isfield(config.params, 'CWLDIMX')
            if config.params.CWLDIMX, app.CWLDIMX_Switch.Value = 'On'; else, app.CWLDIMX_Switch.Value = 'Off'; end
        end
        if isfield(config.params, 'FILL_MISSING_DATA')
            if config.params.FILL_MISSING_DATA, app.Fill_Missing_Data_Switch.Value = 'On'; else, app.Fill_Missing_Data_Switch.Value = 'Off'; end
        end
    end
    
    % 5. Load Maps into Internal Memory
    if isfield(config, 'axes')
        app.AxesData = config.axes;
    else
        app.AxesData = struct();
    end
    
    if isfield(config, 'base_maps')
        app.BaseMapsData = config.base_maps;
    else
        app.BaseMapsData = struct();
    end
    
    % 6. Rebuild the Map Status Table (Panel 4)
    % Definition of the maps is moved into the startup 

    total_targets = size(app.TargetMaps, 1);
    table_data = cell(total_targets, 3);
    maps_loaded = 0;

    for m = 1:total_targets
        winols_name = app.TargetMaps{m, 1};
        json_map_name = app.TargetMaps{m, 4};
        
        table_data{m, 1} = winols_name;
        
        % Check if this map actually exists inside the loaded JSON
        if isfield(app.BaseMapsData, json_map_name) && ~isempty(app.BaseMapsData.(json_map_name))
            map_matrix = app.BaseMapsData.(json_map_name);
            [rows, cols] = size(map_matrix);
            
            table_data{m, 2} = '✅ Loaded (From JSON)';
            table_data{m, 3} = sprintf('%d x %d', rows, cols);
            maps_loaded = maps_loaded + 1;
        else
            table_data{m, 2} = '❌ Missing';
            table_data{m, 3} = '-';
        end
    end
    
    % Push data to UI
    app.Map_Status_Table.Data = table_data;
    
    % Update Status Lamp
    if maps_loaded == total_targets
        app.Map_Status_Lamp.Color = [0 1 0]; % Green
    elseif maps_loaded > 0
        app.Map_Status_Lamp.Color = [1 0.5 0]; % Orange (Partial)
    else
        app.Map_Status_Lamp.Color = [1 0 0]; % Red (Empty)
    end
    
    % Clear the viewer table so it doesn't show ghost data from a previous profile
    app.Map_Viewer_Table.Data = [];
    app.Map_Viewer_Table.ColumnName = 'numbered';
    app.Map_Viewer_Table.RowName = 'numbered';
    
    % Show Success Alert
    uialert(app.UIFigure, ['Successfully loaded Profile: ', json_file], 'Load Complete', 'Icon', 'success');

catch ME
    uialert(app.UIFigure, ['Error loading JSON Profile: ', ME.message], 'Error', 'Icon', 'error');
end
        end

        % Button pushed function: Calc_Export_Button
        function Calc_Export_ButtonPushed(app, event)
        % 1. SAFETY CHECK
if isempty(app.ConfigData) || isempty(app.LogDataFull)
    uialert(app.UIFigure, 'Please process raw logs in Tab 2 first.', 'Missing Data', 'Icon', 'warning');
    return;
end

app.Calc_Export_Button.Text = 'Calculating Maps... Please Wait';
drawnow;

% 2. INITIALIZE ALL VARIABLES & MEMORY
app.CalculatedMaps = struct();
status_data = {};
row_count = 1;

KFLDIMX_Map=[]; KFLDRL_Map=[]; KFLDRL_Counts=[]; Abs_WGDC_Map=[]; Abs_WGDC_Counts=[]; 
Base_Pressure_Curve=[]; Base_Pressure_Counts=[]; KFVPDKSD_Map=[]; 
KFFWL_Map=[]; KFFWL_Counts=[]; KFFWLW_Map=[]; KFFWLW_Counts=[]; FKKVS_RL_Map=[]; 
FKKVS_Map=[]; FKKVS_Counts=[]; KFZW_Map=[]; KFZW_Counts=[]; KFZW2_Map=[]; KFZW2_Counts=[]; 
KFURL_Map=[]; KFPRG_Map=[]; Saugrohr_Counts=[]; axis_vvt_out=[];

% 3. EXTRACT MATH RULES (From Tab 2)
log_vars = app.ConfigData.vars;
min_samples = app.Min_Samples_EditField.Value;
min_samples_wg = app.Min_Samples_WG_EditField.Value;

% 1 = Percent (Inputs are e.g., 5, -10)
% 0 = Lambda/Factor (Inputs are e.g., 1.05, 0.90)
trim_format_str = app.Trim_Format_DropDown.Value;
if strcmp(trim_format_str, 'Percent')
    trim_fmt_num = 1; 
else
    trim_fmt_num = 0; 
end

ambient_press = app.Ambient_Pressure_EditField.Value;
cwldimx = strcmp(app.CWLDIMX_Switch.Value, 'On');
fill_missing = strcmp(app.Fill_Missing_Data_Switch.Value, 'On');
safety_margin = app.Safety_Margin_EditField.Value;
vvt_enabled = strcmp(app.VVT_Enabled_Switch.Value, 'On');
vvt_threshold = app.VVT_Threshold_EditField.Value;

% 4. EXTRACT AXES (With Fallbacks)
ax = app.AxesData;
if isfield(ax, 'rpm_boost'), axis_rpm_boost = ax.rpm_boost; else, axis_rpm_boost = []; end
if isfield(ax, 'boost'), axis_boost = ax.boost; else, axis_boost = []; end
if isfield(ax, 'kfldrl_x'), axis_kfldrl_x = ax.kfldrl_x; else, axis_kfldrl_x = []; end
if isfield(ax, 'rpm_kfvp'), axis_rpm_kfvp = ax.rpm_kfvp; else, axis_rpm_kfvp = []; end
if isfield(ax, 'pratio_kfvp'), axis_pratio_kfvp = ax.pratio_kfvp; else, axis_pratio_kfvp = []; end
if isfield(ax, 'rpm_fuel'), axis_rpm_fuel = ax.rpm_fuel; else, axis_rpm_fuel = []; end
if isfield(ax, 'te'), axis_te = ax.te; else, axis_te = []; end
if isfield(ax, 'tmot'), axis_tmot = ax.tmot; else, axis_tmot = []; end
if isfield(ax, 'rpm_kffwlw'), axis_rpm_kffwlw = ax.rpm_kffwlw; else, axis_rpm_kffwlw = []; end
if isfield(ax, 'load_kffwlw'), axis_load_kffwlw = ax.load_kffwlw; else, axis_load_kffwlw = []; end
if isfield(ax, 'rpm_ign'), axis_rpm_ign = ax.rpm_ign; else, axis_rpm_ign = []; end
if isfield(ax, 'load_ign'), axis_load_ign = ax.load_ign; else, axis_load_ign = []; end
if isfield(ax, 'rpm_url'), axis_rpm_url = ax.rpm_url; else, axis_rpm_url = []; end
if isfield(ax, 'vvt_url'), axis_vvt_url = ax.vvt_url; else, axis_vvt_url = []; end

if ~isempty(axis_boost), axis_boost_abs = axis_boost + ambient_press; else, axis_boost_abs = []; end

% GATEKEEPERS
READY_BOOST  = ~isempty(axis_rpm_boost) && ~isempty(axis_boost);
READY_KFVP   = ~isempty(axis_rpm_kfvp) && ~isempty(axis_pratio_kfvp);
READY_FUEL   = ~isempty(axis_rpm_fuel) && ~isempty(axis_te);
READY_IGN    = ~isempty(axis_rpm_ign) && ~isempty(axis_load_ign);
READY_WARMUP = ~isempty(axis_rpm_kffwlw) && ~isempty(axis_load_kffwlw);
READY_SAUGROHR = ~isempty(axis_rpm_url);

% =========================================================================
% EXECUTION BLOCK (Expanded for full map extraction)
% =========================================================================

% --- 1. Boost Calibration ---
if READY_BOOST && ~isempty(app.LogDataWOT)
    try
        [KFLDIMX_Map, KFLDRL_Map, Abs_WGDC_Map, axis_boost_abs, KFLDRL_Counts, Abs_WGDC_Counts] = GenerateBoostMaps(app.LogDataWOT, cwldimx, ambient_press, safety_margin, fill_missing, min_samples_wg, axis_rpm_boost, axis_boost, axis_kfldrl_x, log_vars);
        
        app.CalculatedMaps.kfldimx = KFLDIMX_Map;
        app.CalculatedMaps.kfldrl = KFLDRL_Map;
        app.CalculatedMaps.abs_wgdc = Abs_WGDC_Map;
        
        status_data(row_count, :) = {'KFLDIMX (PID Limit)', '✅ Calculated', sprintf('%dx%d', size(KFLDIMX_Map,1), size(KFLDIMX_Map,2))}; row_count = row_count+1;
        status_data(row_count, :) = {'KFLDRL (Base WGDC)', '✅ Calculated', sprintf('%dx%d', size(KFLDRL_Map,1), size(KFLDRL_Map,2))}; row_count = row_count+1;
        status_data(row_count, :) = {'Absolute WGDC', '✅ Calculated', sprintf('%dx%d', size(Abs_WGDC_Map,1), size(Abs_WGDC_Map,2))}; row_count = row_count+1;
    catch ME, disp(['Boost Map Error: ', ME.message]); end
end

% --- 2. Throttle Handover ---
if READY_KFVP && ~isempty(app.LogDataWOT)
    try
        [Base_Pressure_Curve, Base_Pressure_Counts] = GenerateBaseWGPressure(app.LogDataWOT, min_samples_wg, axis_rpm_kfvp, log_vars);
        KFVPDKSD_Map = GenerateKFVPDKSD(Base_Pressure_Curve, axis_rpm_kfvp, axis_pratio_kfvp, ambient_press);
        
        app.CalculatedMaps.base_press = Base_Pressure_Curve(:)'; % Force row vector for 1D maps
        app.CalculatedMaps.kfvp = KFVPDKSD_Map;
        
        status_data(row_count, :) = {'Base Pressure Curve', '✅ Calculated', sprintf('1x%d', length(Base_Pressure_Curve))}; row_count = row_count+1;
        status_data(row_count, :) = {'KFVPDKSD (Handover)', '✅ Calculated', sprintf('%dx%d', size(KFVPDKSD_Map,1), size(KFVPDKSD_Map,2))}; row_count = row_count+1;
    catch ME, disp(['KFVPDKSD Map Error: ', ME.message]); end
end

% --- 3. Warmup Enrichment ---
if READY_WARMUP && ~isempty(app.LogDataWarmup)
    try
        [KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map] = GenerateWarmupMaps(app.LogDataWarmup, app.LogDataFull, min_samples, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, log_vars, trim_fmt_num);
        
        app.CalculatedMaps.kffwl = KFFWL_Map(:)'; % Force row vector
        app.CalculatedMaps.kffwlw = KFFWLW_Map;
        app.CalculatedMaps.fkkvs_rl = FKKVS_RL_Map;
        
        status_data(row_count, :) = {'KFFWL (Temp Trim)', '✅ Calculated', sprintf('1x%d', length(KFFWL_Map))}; row_count = row_count+1;
        status_data(row_count, :) = {'KFFWLW (Warmup Map)', '✅ Calculated', sprintf('%dx%d', size(KFFWLW_Map,1), size(KFFWLW_Map,2))}; row_count = row_count+1;
        status_data(row_count, :) = {'FKKVS_RL (Hot Trims)', '✅ Calculated', sprintf('%dx%d', size(FKKVS_RL_Map,1), size(FKKVS_RL_Map,2))}; row_count = row_count+1;
    catch ME, disp(['Warmup Map Error: ', ME.message]); end
end

% --- 4. Fuel Trim (FKKVS) ---
if READY_FUEL && ~isempty(app.LogDataHot)
    try
        [FKKVS_Map, FKKVS_Counts] = GenerateFKKVS(app.LogDataHot, min_samples, axis_rpm_fuel, axis_te, log_vars, trim_fmt_num);
        app.CalculatedMaps.fkkvs = FKKVS_Map;
        status_data(row_count, :) = {'FKKVS (Fuel Trim)', '✅ Calculated', sprintf('%dx%d', size(FKKVS_Map,1), size(FKKVS_Map,2))}; row_count = row_count+1;
    catch ME, disp(['Fuel Map Error: ', ME.message]); end
end

% --- 5. Ignition Timing ---
if READY_IGN && ~isempty(app.LogDataFull)
    try
        [KFZW_Map, KFZW2_Map, KFZW_Counts, KFZW2_Counts] = GenerateKFZW(app.LogDataFull, min_samples, axis_rpm_ign, axis_load_ign, log_vars);
        
        app.CalculatedMaps.kfzw = KFZW_Map;
        status_data(row_count, :) = {'KFZW (Ignition VVT Off)', '✅ Calculated', sprintf('%dx%d', size(KFZW_Map,1), size(KFZW_Map,2))}; row_count = row_count+1;
        
        if ~isempty(KFZW2_Map)
            app.CalculatedMaps.kfzw2 = KFZW2_Map;
            status_data(row_count, :) = {'KFZW2 (Ignition VVT On)', '✅ Calculated', sprintf('%dx%d', size(KFZW2_Map,1), size(KFZW2_Map,2))}; row_count = row_count+1;
        end
    catch ME, disp(['Ignition Map Error: ', ME.message]); end
end

% --- 6. Intake Manifold Model ---
if READY_SAUGROHR && ~isempty(app.LogDataFull)
    try
        [KFURL_Map, KFPRG_Map, Saugrohr_Counts, axis_vvt_out] = GenerateSaugrohrmodell(app.LogDataFull, axis_rpm_url, log_vars, min_samples, vvt_enabled, vvt_threshold);
        
        % =========================================================
        % --- 5120 HACK INTERCEPT & SCALING ---
        % =========================================================
        % Check if switch is 'On' (String) or 1 (Numeric/Logical)
        if strcmpi(string(app.Hack_5120_Switch.Value), 'On') || isequal(app.Hack_5120_Switch.Value, 1)
            % Scale for 5120: 
            % KFURL (Slope = Load/Pressure) is multiplied by 2 because internal pressure is halved.
            % KFPRG (Pressure intercept) is divided by 2 because internal pressure is halved.
            KFURL_Map = KFURL_Map * 2;
            KFPRG_Map = KFPRG_Map / 2;
            
            % Notify the user in the command window
            disp('  [INFO] 5120 Hack Enabled: KFURL multiplied by 2, KFPRG divided by 2.');
            
            % Add a visual warning/notification row directly into the UI status table
            status_data(row_count, :) = {'5120 Patch', '⚠️ Applied', 'KFURL*2, KFPRG/2'}; 
            row_count = row_count + 1;
        end
        % =========================================================

        app.CalculatedMaps.kfurl = KFURL_Map;
        app.CalculatedMaps.kfprg = KFPRG_Map;
        
        status_data(row_count, :) = {'KFURL (VE Slope)', '✅ Calculated', sprintf('%dx%d', size(KFURL_Map,1), size(KFURL_Map,2))}; row_count = row_count+1;
        status_data(row_count, :) = {'KFPRG (Residual Gas)', '✅ Calculated', sprintf('%dx%d', size(KFPRG_Map,1), size(KFPRG_Map,2))}; row_count = row_count+1;
    catch ME
        disp(['Saugrohr Map Error: ', ME.message]); 
    end
end

% --- UPDATE THE STATUS TABLE UI ---
if ~isempty(status_data)
    app.Calc_Status_Table.Data = status_data;
end
% =========================================================================
% EXCEL EXPORT
% =========================================================================
app.Calc_Export_Button.Text = 'Awaiting Excel Save Location...';
drawnow;

default_name = fullfile(app.Log_Folder_EditField.Value, 'ME_Tuning_Maps.xlsx');
[file, path] = uiputfile('*.xlsx', 'Save Calculated Maps to Excel', default_name);

if isequal(file, 0)
    app.Calc_Export_Button.Text = 'Calculate Maps & Export to Excel';
    uialert(app.UIFigure, 'Calculation complete, but Excel export was canceled.', 'Notice');
    return;
end

export_path = fullfile(path, file);

try
    ExportAllMapsToExcel(export_path, KFLDIMX_Map, KFLDRL_Map, KFLDRL_Counts, Abs_WGDC_Map, Abs_WGDC_Counts, ...
                         Base_Pressure_Curve, Base_Pressure_Counts, KFVPDKSD_Map, ...
                         KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map, ...
                         FKKVS_Map, FKKVS_Counts, KFZW_Map, KFZW_Counts, KFZW2_Map, KFZW2_Counts, ...
                         KFURL_Map, KFPRG_Map, Saugrohr_Counts, ... 
                         axis_rpm_boost, axis_boost, axis_boost_abs, axis_kfldrl_x, axis_rpm_kfvp, axis_pratio_kfvp, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, axis_rpm_fuel, axis_te, axis_rpm_ign, axis_load_ign, axis_rpm_url, axis_vvt_out);
                         
    uialert(app.UIFigure, ['Successfully exported to: ', file], 'Export Complete', 'Icon', 'success');
catch ME
    uialert(app.UIFigure, ['Excel Export Error: ', ME.message], 'Error', 'Icon', 'error');
end

app.Calc_Export_Button.Text = 'Calculate Maps & Export to Excel';
        end

        % Cell selection callback: Calc_Status_Table
        function Calc_Status_TableCellSelection(app, event)
            indices = event.Indices;
% 1. Ignore empty clicks, column header clicks, or if data is missing
if isempty(event.Indices) || isempty(app.Calc_Status_Table.Data)
    return;
end

% 2. Get the name of the map from the clicked row (Column 1)
row = event.Indices(1);
selected_map = app.Calc_Status_Table.Data{row, 1};

display_matrix = [];

% 3. Expanded Routing Logic for all 13 maps
if contains(selected_map, 'KFLDIMX') && isfield(app.CalculatedMaps, 'kfldimx')
    display_matrix = app.CalculatedMaps.kfldimx;
elseif contains(selected_map, 'KFLDRL') && isfield(app.CalculatedMaps, 'kfldrl')
    display_matrix = app.CalculatedMaps.kfldrl;
elseif contains(selected_map, 'Absolute WGDC') && isfield(app.CalculatedMaps, 'abs_wgdc')
    display_matrix = app.CalculatedMaps.abs_wgdc;
elseif contains(selected_map, 'Base Pressure') && isfield(app.CalculatedMaps, 'base_press')
    display_matrix = app.CalculatedMaps.base_press;
elseif contains(selected_map, 'KFVPDKSD') && isfield(app.CalculatedMaps, 'kfvp')
    display_matrix = app.CalculatedMaps.kfvp;
elseif contains(selected_map, 'KFFWL (') && isfield(app.CalculatedMaps, 'kffwl')
    display_matrix = app.CalculatedMaps.kffwl;
elseif contains(selected_map, 'KFFWLW') && isfield(app.CalculatedMaps, 'kffwlw')
    display_matrix = app.CalculatedMaps.kffwlw;
elseif contains(selected_map, 'FKKVS_RL') && isfield(app.CalculatedMaps, 'fkkvs_rl')
    display_matrix = app.CalculatedMaps.fkkvs_rl;
elseif contains(selected_map, 'FKKVS (') && isfield(app.CalculatedMaps, 'fkkvs')
    display_matrix = app.CalculatedMaps.fkkvs;
elseif contains(selected_map, 'KFZW (') && isfield(app.CalculatedMaps, 'kfzw')
    display_matrix = app.CalculatedMaps.kfzw;
elseif contains(selected_map, 'KFZW2') && isfield(app.CalculatedMaps, 'kfzw2')
    display_matrix = app.CalculatedMaps.kfzw2;
elseif contains(selected_map, 'KFURL') && isfield(app.CalculatedMaps, 'kfurl')
    display_matrix = app.CalculatedMaps.kfurl;
elseif contains(selected_map, 'KFPRG') && isfield(app.CalculatedMaps, 'kfprg')
    display_matrix = app.CalculatedMaps.kfprg;
end

% 4. Push the matrix to the 2D Viewer Table
if ~isempty(display_matrix)
    app.Calc_Viewer_Table.Data = display_matrix;
    
    % Force numbered row/column headers to match WinOLS grid style perfectly
    app.Calc_Viewer_Table.ColumnName = 'numbered';
    app.Calc_Viewer_Table.RowName = 'numbered';
else
    app.Calc_Viewer_Table.Data = [];
end
        end

        % Button pushed function: Calc_KFVPDKSE_Button
        function Calc_KFVPDKSE_ButtonPushed(app, event)

% 1. Safety Checks
if isempty(app.ConfigData) || isempty(app.LogDataWOT)
    uialert(app.UIFigure, 'Please load an ECU Profile and process logs in Tab 1 & 2 first.', 'Missing Data');
    return;
end
if ~isfield(app.BaseMapsData, 'base_kfldhbn') || ~isfield(app.BaseMapsData, 'base_kfvpdkse')
    uialert(app.UIFigure, 'Please ensure KFLDHBN and KFVPDKSE are imported from WinOLS.', 'Missing Maps');
    return;
end

app.Calc_KFVPDKSE_Button.Text = 'Calculating MED9 Transform...';
drawnow;

try
    % --- 2. Extract UI Inputs & Axes ---
    ambient_p   = app.MED9_Ambient_EditField.Value;
    target_temp = app.MED9_IAT_EditField.Value;
    log_vars    = app.ConfigData.vars;
    min_samples = app.Min_Samples_WG_EditField.Value; % From Tab 2
    
    ax = app.AxesData;

    % --- 3. Step A: Calculate plxs_w (from KFLDHBN) ---
    [~, temp_idx] = min(abs(ax.temp_kfldhbn - target_temp));
    kfldhbn_slice = app.BaseMapsData.base_kfldhbn(temp_idx, :);
    plxs_w = kfldhbn_slice .* ambient_p;
    
    % --- 4. Step B: Calculate plgru_w (Base Pressure from Logs) ---
    % GenerateBaseWGPressure outputs the curve against axis_rpm_kfvp (ME7 axis)
    [plgru_w, ~] = GenerateBaseWGPressure(app.LogDataWOT, min_samples, ax.rpm_kfvp, log_vars);
    
    % --- 5. Step C: Calculate the ME7 KFVPDKSD Map ---
    KFVPDKSD_ME7_Map = GenerateKFVPDKSD(plgru_w, ax.rpm_kfvp, ax.pratio_kfvp, ambient_p);
    
    % --- 6. Step D: Transform ME7 into MED9 (KFVPDKSE) ---
    KFVPDKSE_MED9_Map = GenerateKFVPDKSE(...
        KFVPDKSD_ME7_Map, ax.pratio_kfvp, ax.rpm_kfvp, ...       % ME7 Source Data
        ax.ratio_kfvpdkse, ax.rpm_kfvpdkse, ...                  % MED9 Target Axes
        plxs_w, ax.rpm_kfldhbn, ...                              % Max Pressure Curve
        plgru_w, ax.rpm_kfvp, ...                                % Base Pressure Curve
        ambient_p);
        
    % --- 7. Save to Memory and Update Viewer ---
    % MATLAB Safety Check: Initialize the struct if it is completely empty
    if isempty(app.CalculatedMaps)
        app.CalculatedMaps = struct();
    end
    % Push the matrix (MATLAB automatically creates the exact number of rows and cols)
    app.MED9_Viewer_Table.Data = KFVPDKSE_MED9_Map;
    
% X-Axis (Columns) = RPM (Format as whole numbers)
    app.MED9_Viewer_Table.ColumnName = compose('%.0f', ax.rpm_kfvpdkse);
    
    % Y-Axis (Rows) = Pressure Ratio (Format to 3 decimal places)
    app.MED9_Viewer_Table.RowName = compose('%.3f', ax.ratio_kfvpdkse);
    
    % Auto-scale the columns so the axis values fit perfectly
    app.MED9_Viewer_Table.ColumnWidth = 'auto';
    
    display_me7 = num2cell(round(KFVPDKSD_ME7_Map, 4));
    app.ME7_Viewer_Table.Data = display_me7;
    
    % X-Axis = ME7 RPM / Y-Axis = ME7 Absolute Pressure Ratio
    app.ME7_Viewer_Table.ColumnName = compose('%.0f', ax.rpm_kfvp);
    app.ME7_Viewer_Table.RowName = compose('%.3f', ax.pratio_kfvp);
    app.ME7_Viewer_Table.ColumnWidth = 'auto';

catch ME
    app.Calc_KFVPDKSE_Button.Text = 'Step 1: Calculate KFVPDKSE';
    uialert(app.UIFigure, ['Math Error: ', ME.message], 'Error', 'Icon', 'error');
end
        end
    end

    % Component initialization
    methods (Access = private)

        % Create UIFigure and components
        function createComponents(app)

            % Create UIFigure and hide until all components are created
            app.UIFigure = uifigure('Visible', 'off');
            app.UIFigure.Position = [100 100 1538 986];
            app.UIFigure.Name = 'MATLAB App';

            % Create TabGroup
            app.TabGroup = uitabgroup(app.UIFigure);
            app.TabGroup.Position = [1 1 1539 986];

            % Create ECUProfileTab
            app.ECUProfileTab = uitab(app.TabGroup);
            app.ECUProfileTab.Title = 'ECU Profile';

            % Create Var_RPMEditFieldLabel
            app.Var_RPMEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_RPMEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_RPMEditFieldLabel.Position = [105 799 56 22];
            app.Var_RPMEditFieldLabel.Text = 'Var_RPM';

            % Create Var_RPM_EditField
            app.Var_RPM_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_RPM_EditField.Position = [176 799 100 22];
            app.Var_RPM_EditField.Value = 'nmot_w';

            % Create LoggerVariableMappingLabel
            app.LoggerVariableMappingLabel = uilabel(app.ECUProfileTab);
            app.LoggerVariableMappingLabel.FontSize = 24;
            app.LoggerVariableMappingLabel.Position = [20 834 274 32];
            app.LoggerVariableMappingLabel.Text = 'Logger Variable Mapping';

            % Create Var_LoadEditFieldLabel
            app.Var_LoadEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_LoadEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_LoadEditFieldLabel.Position = [105 769 56 22];
            app.Var_LoadEditFieldLabel.Text = 'Var_Load';

            % Create Var_Load_EditField
            app.Var_Load_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Load_EditField.Position = [176 769 100 22];
            app.Var_Load_EditField.Value = 'rl_w';

            % Create Var_BoostEditFieldLabel
            app.Var_BoostEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_BoostEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_BoostEditFieldLabel.Position = [101 709 60 22];
            app.Var_BoostEditFieldLabel.Text = 'Var_Boost';

            % Create Var_Boost_EditField
            app.Var_Boost_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Boost_EditField.Position = [176 709 100 22];
            app.Var_Boost_EditField.Value = 'pvdks_w';

            % Create Var_PedalEditFieldLabel
            app.Var_PedalEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_PedalEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_PedalEditFieldLabel.Position = [101 739 60 22];
            app.Var_PedalEditFieldLabel.Text = 'Var_Pedal';

            % Create Var_Pedal_EditField
            app.Var_Pedal_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Pedal_EditField.Position = [176 739 100 22];
            app.Var_Pedal_EditField.Value = 'wdkba';

            % Create Var_WGDCEditFieldLabel
            app.Var_WGDCEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_WGDCEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_WGDCEditFieldLabel.Position = [94 649 67 22];
            app.Var_WGDCEditFieldLabel.Text = 'Var_WGDC';

            % Create Var_WGDC_EditField
            app.Var_WGDC_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_WGDC_EditField.Position = [176 649 100 22];
            app.Var_WGDC_EditField.Value = 'ldtvm';

            % Create Var_ManifoldEditFieldLabel
            app.Var_ManifoldEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_ManifoldEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_ManifoldEditFieldLabel.Position = [86 679 75 22];
            app.Var_ManifoldEditFieldLabel.Text = 'Var_Manifold';

            % Create Var_Manifold_EditField
            app.Var_Manifold_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Manifold_EditField.Position = [176 679 100 22];
            app.Var_Manifold_EditField.Value = 'ps_w';

            % Create Var_STFTEditFieldLabel
            app.Var_STFTEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_STFTEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_STFTEditFieldLabel.Position = [102 589 59 22];
            app.Var_STFTEditFieldLabel.Text = 'Var_STFT';

            % Create Var_STFT_EditField
            app.Var_STFT_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_STFT_EditField.Position = [176 589 100 22];
            app.Var_STFT_EditField.Value = 'frm_w';

            % Create Var_VVTEditFieldLabel
            app.Var_VVTEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_VVTEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_VVTEditFieldLabel.Position = [108 619 53 22];
            app.Var_VVTEditFieldLabel.Text = 'Var_VVT';

            % Create Var_VVT_EditField
            app.Var_VVT_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_VVT_EditField.Position = [176 619 100 22];
            app.Var_VVT_EditField.Value = 'wnwi_w';

            % Create Var_TimeEditFieldLabel
            app.Var_TimeEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_TimeEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_TimeEditFieldLabel.Position = [105 409 56 22];
            app.Var_TimeEditFieldLabel.Text = 'Var_Time';

            % Create Var_Time_EditField
            app.Var_Time_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Time_EditField.Position = [176 409 100 22];
            app.Var_Time_EditField.Value = 'TimeStamp';

            % Create Var_LTFTEditFieldLabel
            app.Var_LTFTEditFieldLabel = uilabel(app.ECUProfileTab);
            app.Var_LTFTEditFieldLabel.HorizontalAlignment = 'right';
            app.Var_LTFTEditFieldLabel.Position = [104 559 57 22];
            app.Var_LTFTEditFieldLabel.Text = 'Var_LTFT';

            % Create Var_LTFT_EditField
            app.Var_LTFT_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_LTFT_EditField.Position = [176 559 100 22];
            app.Var_LTFT_EditField.Value = 'fra_w';

            % Create PreProcessingRulesLabel
            app.PreProcessingRulesLabel = uilabel(app.ECUProfileTab);
            app.PreProcessingRulesLabel.FontSize = 24;
            app.PreProcessingRulesLabel.Position = [34 257 239 32];
            app.PreProcessingRulesLabel.Text = 'Pre-Processing Rules';

            % Create Pressure_Cols_EditField
            app.Pressure_Cols_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Pressure_Cols_EditField.Position = [125 143 266 22];
            app.Pressure_Cols_EditField.Value = 'pvdks_w, pu, pssol_w, pvdk_w, plgru_w, ps_w';

            % Create AlignTimestampsSwitchLabel
            app.AlignTimestampsSwitchLabel = uilabel(app.ECUProfileTab);
            app.AlignTimestampsSwitchLabel.HorizontalAlignment = 'center';
            app.AlignTimestampsSwitchLabel.Position = [47 179 100 22];
            app.AlignTimestampsSwitchLabel.Text = 'Align Timestamps';

            % Create Align_Time_Switch
            app.Align_Time_Switch = uiswitch(app.ECUProfileTab, 'slider');
            app.Align_Time_Switch.Position = [74 216 45 20];
            app.Align_Time_Switch.Value = 'On';

            % Create mbarHackSwitchLabel
            app.mbarHackSwitchLabel = uilabel(app.ECUProfileTab);
            app.mbarHackSwitchLabel.HorizontalAlignment = 'center';
            app.mbarHackSwitchLabel.Position = [174 179 90 22];
            app.mbarHackSwitchLabel.Text = '5120mbar Hack';

            % Create Hack_5120_Switch
            app.Hack_5120_Switch = uiswitch(app.ECUProfileTab, 'slider');
            app.Hack_5120_Switch.Position = [196 216 45 20];

            % Create PressureColumnsEditFieldLabel
            app.PressureColumnsEditFieldLabel = uilabel(app.ECUProfileTab);
            app.PressureColumnsEditFieldLabel.HorizontalAlignment = 'right';
            app.PressureColumnsEditFieldLabel.Position = [12 143 104 22];
            app.PressureColumnsEditFieldLabel.Text = 'Pressure Columns';

            % Create VariableProfileActionsLabel
            app.VariableProfileActionsLabel = uilabel(app.ECUProfileTab);
            app.VariableProfileActionsLabel.FontSize = 24;
            app.VariableProfileActionsLabel.Position = [15 922 252 32];
            app.VariableProfileActionsLabel.Text = 'Variable Profile Actions';

            % Create LoadExistingProfileButton
            app.LoadExistingProfileButton = uibutton(app.ECUProfileTab, 'push');
            app.LoadExistingProfileButton.ButtonPushedFcn = createCallbackFcn(app, @LoadExistingProfileButtonPushed, true);
            app.LoadExistingProfileButton.Position = [33 886 124 23];
            app.LoadExistingProfileButton.Text = 'Load Existing Profile';

            % Create SaveAsNewProfileButton
            app.SaveAsNewProfileButton = uibutton(app.ECUProfileTab, 'push');
            app.SaveAsNewProfileButton.ButtonPushedFcn = createCallbackFcn(app, @SaveAsNewProfileButtonPushed, true);
            app.SaveAsNewProfileButton.Position = [174 886 124 23];
            app.SaveAsNewProfileButton.Text = 'Save As New Profile';

            % Create ImportWinOLSCSVExportLabel
            app.ImportWinOLSCSVExportLabel = uilabel(app.ECUProfileTab);
            app.ImportWinOLSCSVExportLabel.FontSize = 24;
            app.ImportWinOLSCSVExportLabel.Position = [438 920 305 32];
            app.ImportWinOLSCSVExportLabel.Text = 'Import WinOLS CSV Export';

            % Create ImportWinOLS_Button
            app.ImportWinOLS_Button = uibutton(app.ECUProfileTab, 'push');
            app.ImportWinOLS_Button.ButtonPushedFcn = createCallbackFcn(app, @ImportWinOLS_ButtonPushed, true);
            app.ImportWinOLS_Button.Position = [550 852 163 23];
            app.ImportWinOLS_Button.Text = 'Import WinOLS CSV Export';

            % Create WinOLSCSVExportLabel
            app.WinOLSCSVExportLabel = uilabel(app.ECUProfileTab);
            app.WinOLSCSVExportLabel.HorizontalAlignment = 'right';
            app.WinOLSCSVExportLabel.Position = [442 884 116 22];
            app.WinOLSCSVExportLabel.Text = 'WinOLS CSV Export';

            % Create WinOLS_CSV_EditField
            app.WinOLS_CSV_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.WinOLS_CSV_EditField.Position = [573 884 929 22];

            % Create Map_Status_Table
            app.Map_Status_Table = uitable(app.ECUProfileTab);
            app.Map_Status_Table.ColumnName = {'Name'; 'Status'; 'Dimensions'; 'Calibration Area'};
            app.Map_Status_Table.ColumnWidth = {'auto', 100, 150};
            app.Map_Status_Table.RowName = {};
            app.Map_Status_Table.CellSelectionCallback = createCallbackFcn(app, @Map_Status_TableCellSelection, true);
            app.Map_Status_Table.Position = [442 563 1083 290];

            % Create StatusLabel
            app.StatusLabel = uilabel(app.ECUProfileTab);
            app.StatusLabel.HorizontalAlignment = 'right';
            app.StatusLabel.Position = [776 925 39 22];
            app.StatusLabel.Text = 'Status';

            % Create Map_Status_Lamp
            app.Map_Status_Lamp = uilamp(app.ECUProfileTab);
            app.Map_Status_Lamp.Position = [830 925 20 20];
            app.Map_Status_Lamp.Color = [0 0 0];

            % Create Map_Viewer_Table
            app.Map_Viewer_Table = uitable(app.ECUProfileTab);
            app.Map_Viewer_Table.ColumnName = {'Column 1'; 'Column 2'; 'Column 3'; 'Column 4'};
            app.Map_Viewer_Table.RowName = {'custom'};
            app.Map_Viewer_Table.FontSize = 10;
            app.Map_Viewer_Table.Position = [442 20 1083 503];

            % Create MapViewerclickonamapinthetableabovetoviewitLabel
            app.MapViewerclickonamapinthetableabovetoviewitLabel = uilabel(app.ECUProfileTab);
            app.MapViewerclickonamapinthetableabovetoviewitLabel.Position = [442 521 303 22];
            app.MapViewerclickonamapinthetableabovetoviewitLabel.Text = 'Map Viewer, click on a map in the table above to view it';

            % Create InjectorOntimeLabel
            app.InjectorOntimeLabel = uilabel(app.ECUProfileTab);
            app.InjectorOntimeLabel.HorizontalAlignment = 'right';
            app.InjectorOntimeLabel.Position = [34 529 127 22];
            app.InjectorOntimeLabel.Text = 'VAR_Injector_On_time';

            % Create Var_Inj_OnTime_EditField
            app.Var_Inj_OnTime_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Inj_OnTime_EditField.Position = [176 529 100 22];
            app.Var_Inj_OnTime_EditField.Value = 'tevfakge_w';

            % Create InjectorOntimeLabel_2
            app.InjectorOntimeLabel_2 = uilabel(app.ECUProfileTab);
            app.InjectorOntimeLabel_2.HorizontalAlignment = 'right';
            app.InjectorOntimeLabel_2.Position = [48 469 113 22];
            app.InjectorOntimeLabel_2.Text = 'VAR_Coolant_Temp';

            % Create Var_Coolant_temp_EditField
            app.Var_Coolant_temp_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Coolant_temp_EditField.Position = [176 469 100 22];
            app.Var_Coolant_temp_EditField.Value = 'tmotlin';

            % Create InjectorOntimeLabel_3
            app.InjectorOntimeLabel_3 = uilabel(app.ECUProfileTab);
            app.InjectorOntimeLabel_3.HorizontalAlignment = 'right';
            app.InjectorOntimeLabel_3.Position = [50 499 111 22];
            app.InjectorOntimeLabel_3.Text = 'VAR_Ambient_Pres';

            % Create Var_AmbientPres_EditField
            app.Var_AmbientPres_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_AmbientPres_EditField.Position = [176 499 100 22];
            app.Var_AmbientPres_EditField.Value = 'pu';

            % Create InjectorOntimeLabel_4
            app.InjectorOntimeLabel_4 = uilabel(app.ECUProfileTab);
            app.InjectorOntimeLabel_4.HorizontalAlignment = 'right';
            app.InjectorOntimeLabel_4.Position = [54 439 107 22];
            app.InjectorOntimeLabel_4.Text = 'VAR_Knock_retard';

            % Create Var_Knock_EditField
            app.Var_Knock_EditField = uieditfield(app.ECUProfileTab, 'text');
            app.Var_Knock_EditField.Position = [176 439 100 22];
            app.Var_Knock_EditField.Value = 'wkrm';

            % Create DataIngestionFilteringTab
            app.DataIngestionFilteringTab = uitab(app.TabGroup);
            app.DataIngestionFilteringTab.Title = 'Data Ingestion & Filtering';

            % Create VVTSystemSwitchLabel
            app.VVTSystemSwitchLabel = uilabel(app.DataIngestionFilteringTab);
            app.VVTSystemSwitchLabel.HorizontalAlignment = 'center';
            app.VVTSystemSwitchLabel.Position = [24 756 71 22];
            app.VVTSystemSwitchLabel.Text = 'VVT System';

            % Create VVT_Enabled_Switch
            app.VVT_Enabled_Switch = uiswitch(app.DataIngestionFilteringTab, 'slider');
            app.VVT_Enabled_Switch.Position = [36 793 45 20];

            % Create VVTThresholddegEditFieldLabel
            app.VVTThresholddegEditFieldLabel = uilabel(app.DataIngestionFilteringTab);
            app.VVTThresholddegEditFieldLabel.HorizontalAlignment = 'right';
            app.VVTThresholddegEditFieldLabel.Position = [98 791 134 22];
            app.VVTThresholddegEditFieldLabel.Text = 'VVT Threshold(deg)';

            % Create VVT_Threshold_EditField
            app.VVT_Threshold_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.VVT_Threshold_EditField.Position = [247 791 100 22];
            app.VVT_Threshold_EditField.Value = 18;

            % Create MinSamplesperCellEditFieldLabel
            app.MinSamplesperCellEditFieldLabel = uilabel(app.DataIngestionFilteringTab);
            app.MinSamplesperCellEditFieldLabel.HorizontalAlignment = 'right';
            app.MinSamplesperCellEditFieldLabel.Position = [0 575 145 22];
            app.MinSamplesperCellEditFieldLabel.Text = 'Min Samples per Cell:';

            % Create Min_Samples_EditField
            app.Min_Samples_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Min_Samples_EditField.Position = [157 575 100 22];
            app.Min_Samples_EditField.Value = 1;

            % Create LoadLogs_Button
            app.LoadLogs_Button = uibutton(app.DataIngestionFilteringTab, 'push');
            app.LoadLogs_Button.ButtonPushedFcn = createCallbackFcn(app, @LoadLogs_ButtonPushed, true);
            app.LoadLogs_Button.Position = [530 872 172 23];
            app.LoadLogs_Button.Text = 'Import & Auto-Split Raw Logs';

            % Create LogsFolderEditFieldLabel
            app.LogsFolderEditFieldLabel = uilabel(app.DataIngestionFilteringTab);
            app.LogsFolderEditFieldLabel.HorizontalAlignment = 'right';
            app.LogsFolderEditFieldLabel.Position = [38 873 68 22];
            app.LogsFolderEditFieldLabel.Text = 'Logs Folder';

            % Create Log_Folder_EditField
            app.Log_Folder_EditField = uieditfield(app.DataIngestionFilteringTab, 'text');
            app.Log_Folder_EditField.Position = [121 873 391 22];

            % Create StatusLampLabel
            app.StatusLampLabel = uilabel(app.DataIngestionFilteringTab);
            app.StatusLampLabel.HorizontalAlignment = 'right';
            app.StatusLampLabel.Position = [847 930 39 22];
            app.StatusLampLabel.Text = 'Status';

            % Create DataStatus_Lamp
            app.DataStatus_Lamp = uilamp(app.DataIngestionFilteringTab);
            app.DataStatus_Lamp.Position = [901 930 20 20];
            app.DataStatus_Lamp.Color = [0 0 0];

            % Create DataIngestionLabel
            app.DataIngestionLabel = uilabel(app.DataIngestionFilteringTab);
            app.DataIngestionLabel.FontSize = 24;
            app.DataIngestionLabel.Position = [10 930 160 32];
            app.DataIngestionLabel.Text = 'Data Ingestion';

            % Create VVTSettingsLabel
            app.VVTSettingsLabel = uilabel(app.DataIngestionFilteringTab);
            app.VVTSettingsLabel.FontSize = 24;
            app.VVTSettingsLabel.Position = [10 814 145 32];
            app.VVTSettingsLabel.Text = 'VVT Settings';

            % Create AmbientpressurehpaEditFieldLabel
            app.AmbientpressurehpaEditFieldLabel = uilabel(app.DataIngestionFilteringTab);
            app.AmbientpressurehpaEditFieldLabel.HorizontalAlignment = 'right';
            app.AmbientpressurehpaEditFieldLabel.Position = [2 444 145 22];
            app.AmbientpressurehpaEditFieldLabel.Text = 'Ambient pressure hpa';

            % Create Ambient_Pressure_EditField
            app.Ambient_Pressure_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Ambient_Pressure_EditField.Position = [157 439 100 22];
            app.Ambient_Pressure_EditField.Value = 1000;

            % Create FuelTrimformatDropDownLabel
            app.FuelTrimformatDropDownLabel = uilabel(app.DataIngestionFilteringTab);
            app.FuelTrimformatDropDownLabel.HorizontalAlignment = 'right';
            app.FuelTrimformatDropDownLabel.Position = [14 542 130 22];
            app.FuelTrimformatDropDownLabel.Text = 'Fuel Trim format';

            % Create Trim_Format_DropDown
            app.Trim_Format_DropDown = uidropdown(app.DataIngestionFilteringTab);
            app.Trim_Format_DropDown.Items = {'Percent,', 'Lambda'};
            app.Trim_Format_DropDown.Position = [157 541 100 22];
            app.Trim_Format_DropDown.Value = 'Lambda';

            % Create BoostWastegateSettingsLabel
            app.BoostWastegateSettingsLabel = uilabel(app.DataIngestionFilteringTab);
            app.BoostWastegateSettingsLabel.FontSize = 24;
            app.BoostWastegateSettingsLabel.Position = [10 714 307 32];
            app.BoostWastegateSettingsLabel.Text = 'Boost & Wastegate Settings';

            % Create FillMissingDataSwitchLabel
            app.FillMissingDataSwitchLabel = uilabel(app.DataIngestionFilteringTab);
            app.FillMissingDataSwitchLabel.HorizontalAlignment = 'center';
            app.FillMissingDataSwitchLabel.Position = [301 542 93 22];
            app.FillMissingDataSwitchLabel.Text = 'Fill Missing Data';

            % Create Fill_Missing_Data_Switch
            app.Fill_Missing_Data_Switch = uiswitch(app.DataIngestionFilteringTab, 'slider');
            app.Fill_Missing_Data_Switch.Position = [324 579 45 20];

            % Create CWLDIMXSwitchLabel
            app.CWLDIMXSwitchLabel = uilabel(app.DataIngestionFilteringTab);
            app.CWLDIMXSwitchLabel.HorizontalAlignment = 'center';
            app.CWLDIMXSwitchLabel.Position = [31 654 62 22];
            app.CWLDIMXSwitchLabel.Text = 'CWLDIMX';

            % Create CWLDIMX_Switch
            app.CWLDIMX_Switch = uiswitch(app.DataIngestionFilteringTab, 'slider');
            app.CWLDIMX_Switch.Position = [38 691 45 20];

            % Create MinSamplesperCellEditFieldLabel_2
            app.MinSamplesperCellEditFieldLabel_2 = uilabel(app.DataIngestionFilteringTab);
            app.MinSamplesperCellEditFieldLabel_2.HorizontalAlignment = 'right';
            app.MinSamplesperCellEditFieldLabel_2.Position = [117 689 137 22];
            app.MinSamplesperCellEditFieldLabel_2.Text = 'Min Samples (Base WG)';

            % Create Min_Samples_WG_EditField
            app.Min_Samples_WG_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Min_Samples_WG_EditField.Position = [269 689 100 22];
            app.Min_Samples_WG_EditField.Value = 1;

            % Create MinSamplesperCellEditFieldLabel_3
            app.MinSamplesperCellEditFieldLabel_3 = uilabel(app.DataIngestionFilteringTab);
            app.MinSamplesperCellEditFieldLabel_3.HorizontalAlignment = 'right';
            app.MinSamplesperCellEditFieldLabel_3.Position = [130 660 124 22];
            app.MinSamplesperCellEditFieldLabel_3.Text = 'WGDC Safety Margin:';

            % Create Safety_Margin_EditField
            app.Safety_Margin_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Safety_Margin_EditField.Position = [269 660 100 22];
            app.Safety_Margin_EditField.Value = 1;

            % Create Max_RPM_ROC_EditField
            app.Max_RPM_ROC_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Max_RPM_ROC_EditField.Position = [157 507 100 22];
            app.Max_RPM_ROC_EditField.Value = 1000;

            % Create MinSamplesperCellEditFieldLabel_4
            app.MinSamplesperCellEditFieldLabel_4 = uilabel(app.DataIngestionFilteringTab);
            app.MinSamplesperCellEditFieldLabel_4.HorizontalAlignment = 'right';
            app.MinSamplesperCellEditFieldLabel_4.Position = [17 509 135 22];
            app.MinSamplesperCellEditFieldLabel_4.Text = 'Max RPM ROC (RPM/s)';

            % Create Max_Throttle_ROC_EditField
            app.Max_Throttle_ROC_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Max_Throttle_ROC_EditField.Position = [157 473 100 22];
            app.Max_Throttle_ROC_EditField.Value = 33;

            % Create MinSamplesperCellEditFieldLabel_5
            app.MinSamplesperCellEditFieldLabel_5 = uilabel(app.DataIngestionFilteringTab);
            app.MinSamplesperCellEditFieldLabel_5.HorizontalAlignment = 'right';
            app.MinSamplesperCellEditFieldLabel_5.Position = [24 476 120 22];
            app.MinSamplesperCellEditFieldLabel_5.Text = 'Max Pedal ROC(%/s)';

            % Create OutputLabel
            app.OutputLabel = uilabel(app.DataIngestionFilteringTab);
            app.OutputLabel.HorizontalAlignment = 'right';
            app.OutputLabel.Position = [413 709 41 22];
            app.OutputLabel.Text = 'Output';

            % Create Console_TextArea
            app.Console_TextArea = uitextarea(app.DataIngestionFilteringTab);
            app.Console_TextArea.Position = [469 332 510 401];

            % Create GeneralMathFuelSettingsLabel
            app.GeneralMathFuelSettingsLabel = uilabel(app.DataIngestionFilteringTab);
            app.GeneralMathFuelSettingsLabel.FontSize = 24;
            app.GeneralMathFuelSettingsLabel.Position = [10 608 324 32];
            app.GeneralMathFuelSettingsLabel.Text = 'General Math & Fuel Settings';

            % Create WarmupMaxTempCEditFieldLabel_2
            app.WarmupMaxTempCEditFieldLabel_2 = uilabel(app.DataIngestionFilteringTab);
            app.WarmupMaxTempCEditFieldLabel_2.HorizontalAlignment = 'right';
            app.WarmupMaxTempCEditFieldLabel_2.Position = [19 409 125 22];
            app.WarmupMaxTempCEditFieldLabel_2.Text = 'Warmup Max Temp °C';

            % Create Temp_Max_EditField
            app.Temp_Max_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.Temp_Max_EditField.Position = [157 406 100 22];
            app.Temp_Max_EditField.Value = 80;

            % Create WOTMinimumPedalEditFieldLabel_2
            app.WOTMinimumPedalEditFieldLabel_2 = uilabel(app.DataIngestionFilteringTab);
            app.WOTMinimumPedalEditFieldLabel_2.HorizontalAlignment = 'right';
            app.WOTMinimumPedalEditFieldLabel_2.Position = [9 373 133 22];
            app.WOTMinimumPedalEditFieldLabel_2.Text = 'WOT Minimum Pedal %';

            % Create WOT_Min_EditField
            app.WOT_Min_EditField = uieditfield(app.DataIngestionFilteringTab, 'numeric');
            app.WOT_Min_EditField.Position = [157 373 100 22];
            app.WOT_Min_EditField.Value = 70;

            % Create CalculateTab
            app.CalculateTab = uitab(app.TabGroup);
            app.CalculateTab.Title = 'Calculate';

            % Create CalculationControlLabel
            app.CalculationControlLabel = uilabel(app.CalculateTab);
            app.CalculationControlLabel.FontSize = 24;
            app.CalculationControlLabel.Position = [24 921 209 31];
            app.CalculationControlLabel.Text = 'Calculation Control';

            % Create Calc_Export_Button
            app.Calc_Export_Button = uibutton(app.CalculateTab, 'push');
            app.Calc_Export_Button.ButtonPushedFcn = createCallbackFcn(app, @Calc_Export_ButtonPushed, true);
            app.Calc_Export_Button.Position = [17 894 193 22];
            app.Calc_Export_Button.Text = 'Calculate Maps & Export to Excel';

            % Create Calc_Status_Table
            app.Calc_Status_Table = uitable(app.CalculateTab);
            app.Calc_Status_Table.ColumnName = {'Map Name'; 'Status'; 'Size.'; ''};
            app.Calc_Status_Table.RowName = {};
            app.Calc_Status_Table.CellSelectionCallback = createCallbackFcn(app, @Calc_Status_TableCellSelection, true);
            app.Calc_Status_Table.Position = [10 104 438 742];

            % Create Calc_Viewer_Table
            app.Calc_Viewer_Table = uitable(app.CalculateTab);
            app.Calc_Viewer_Table.ColumnName = {'Column 1'; 'Column 2'; 'Column 3'; 'Column 4'};
            app.Calc_Viewer_Table.RowName = {};
            app.Calc_Viewer_Table.Position = [453 257 1060 589];

            % Create KFVPDKSEMED91Tab
            app.KFVPDKSEMED91Tab = uitab(app.TabGroup);
            app.KFVPDKSEMED91Tab.Title = 'KFVPDKSE MED9.1';

            % Create MED9_Ambient_EditFieldLabel
            app.MED9_Ambient_EditFieldLabel = uilabel(app.KFVPDKSEMED91Tab);
            app.MED9_Ambient_EditFieldLabel.HorizontalAlignment = 'right';
            app.MED9_Ambient_EditFieldLabel.Position = [16 932 142 22];
            app.MED9_Ambient_EditFieldLabel.Text = 'MED9_Ambient_EditField';

            % Create MED9_Ambient_EditField
            app.MED9_Ambient_EditField = uieditfield(app.KFVPDKSEMED91Tab, 'numeric');
            app.MED9_Ambient_EditField.Position = [173 932 100 22];
            app.MED9_Ambient_EditField.Value = 950;

            % Create MED9_IAT_EditFieldLabel
            app.MED9_IAT_EditFieldLabel = uilabel(app.KFVPDKSEMED91Tab);
            app.MED9_IAT_EditFieldLabel.HorizontalAlignment = 'right';
            app.MED9_IAT_EditFieldLabel.Position = [42 893 116 22];
            app.MED9_IAT_EditFieldLabel.Text = 'MED9_IAT_EditField';

            % Create MED9_IAT_EditField
            app.MED9_IAT_EditField = uieditfield(app.KFVPDKSEMED91Tab, 'numeric');
            app.MED9_IAT_EditField.Position = [173 893 100 22];
            app.MED9_IAT_EditField.Value = 40;

            % Create Calc_KFVPDKSE_Button
            app.Calc_KFVPDKSE_Button = uibutton(app.KFVPDKSEMED91Tab, 'push');
            app.Calc_KFVPDKSE_Button.ButtonPushedFcn = createCallbackFcn(app, @Calc_KFVPDKSE_ButtonPushed, true);
            app.Calc_KFVPDKSE_Button.Position = [304 932 150 22];
            app.Calc_KFVPDKSE_Button.Text = 'Calc_KFVPDKSE_Button';

            % Create MED9_Viewer_Table
            app.MED9_Viewer_Table = uitable(app.KFVPDKSEMED91Tab);
            app.MED9_Viewer_Table.ColumnName = {'Column 1'; 'Column 2'; 'Column 3'; 'Column 4'};
            app.MED9_Viewer_Table.RowName = {'custom'};
            app.MED9_Viewer_Table.Position = [21 441 1471 425];

            % Create KFVPDKSEMED9RelativeRatioLabel
            app.KFVPDKSEMED9RelativeRatioLabel = uilabel(app.KFVPDKSEMED91Tab);
            app.KFVPDKSEMED9RelativeRatioLabel.Position = [24 868 187 22];
            app.KFVPDKSEMED9RelativeRatioLabel.Text = 'KFVPDKSE MED9, Relative Ratio';

            % Create KFVPDKSDME7equivalentAbsoluteraitoLabel
            app.KFVPDKSDME7equivalentAbsoluteraitoLabel = uilabel(app.KFVPDKSEMED91Tab);
            app.KFVPDKSDME7equivalentAbsoluteraitoLabel.Position = [21 412 240 22];
            app.KFVPDKSDME7equivalentAbsoluteraitoLabel.Text = 'KFVPDKSD ME7 equivalent, Absolute raito ';

            % Create ME7_Viewer_Table
            app.ME7_Viewer_Table = uitable(app.KFVPDKSEMED91Tab);
            app.ME7_Viewer_Table.ColumnName = {'Column 1'; 'Column 2'; 'Column 3'; 'Column 4'};
            app.ME7_Viewer_Table.RowName = {'custom'};
            app.ME7_Viewer_Table.Position = [21 -27 1471 425];

            % Show the figure after all components are created
            app.UIFigure.Visible = 'on';
        end
    end

    % App creation and deletion
    methods (Access = public)

        % Construct app
        function app = MotronicTuner_GUI

            % Create UIFigure and components
            createComponents(app)

            % Register the app with App Designer
            registerApp(app, app.UIFigure)

            % Execute the startup function
            runStartupFcn(app, @startupFcn)

            if nargout == 0
                clear app
            end
        end

        % Code that executes before app deletion
        function delete(app)

            % Delete UIFigure when app is deleted
            delete(app.UIFigure)
        end
    end
end