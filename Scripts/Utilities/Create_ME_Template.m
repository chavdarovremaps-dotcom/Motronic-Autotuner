% =========================================================================
% utils/Create_ME_Template.m
% Generates a clean baseline JSON template for a specific ECU family.
% =========================================================================
clear; clc;

% --- 1. DEFINE BASELINE SETTINGS ---
config.workflow.PROCESS_RAW_LOGS = 1; 
config.workflow.EXPORT_TO_EXCEL  = 1; 
config.workflow.SHOW_VISUALS     = 0; 

config.files.raw_log_folder   = 'D:\Damos files\Matlab scripts\Volvo S60';
config.files.filename_wot     = 'ME_Logs_WOT.csv';    
config.files.filename_full    = 'ME_Logs_Full.csv';   
config.files.filename_warmup  = 'ME_Logs_Warmup.csv'; 
config.files.excel_filename   = 'ME_Tuning_Maps.xlsx';

% --- LOGGER VARIABLE NAMES ---
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
config.vars.pedal   = 'wped';
config.vars.time    = 'Time';    

% --- PREP & FILTER SETTINGS ---
config.prep.wot_min          = 95; 
config.prep.temp_max         = 80;
config.prep.ALIGN_TIMESTAMPS = 1;
config.prep.HACK_5120        = 0;
config.prep.pressure_columns = {'pvdks_w', 'pu', 'pssol_w', 'pvdk_w', 'plgru_w'};

% --- GLOBAL PARAMETERS ---
config.params.min_samples         = 2;          
config.params.min_samples_base_wg = 2;          
config.params.trim_format         = 0;          
config.params.axis_wgdc_splat     = 0:5:95;     
config.params.FILL_MISSING_DATA   = 0;          
config.params.CWLDIMX             = 0;          
config.params.ambient_pressure    = 1000;       
config.params.safety_margin       = 0;  

config.axes = struct(); 
config.base_maps = struct(); 

% --- 2. SAVE AS NEW JSON TEMPLATE ---
script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir), script_dir = pwd; end
default_preset_dir = fullfile(script_dir, '..', 'presets');
if ~exist(default_preset_dir, 'dir'), mkdir(default_preset_dir); end

disp('Waiting for user to select save location and filename...');
[save_file, save_path] = uiputfile(fullfile(default_preset_dir, 'Bosch_ME_New_Family.json'), 'Save New ECU Template As');

if isequal(save_file, 0)
    disp('*** Save canceled. No template was created. ***');
    return;
end

json_txt = jsonencode(config, 'PrettyPrint', true); 
fid = fopen(fullfile(save_path, save_file), 'w'); 
fwrite(fid, json_txt, 'char'); 
fclose(fid);

disp(['*** Successfully created Base Template at: ', save_file, ' ***']);