function [Master_Full, Master_WOT, Master_Warmup, Master_Hot] = ProcessRawLogs(log_folder, config, max_rpm_roc, max_pedal_roc, wot_min, temp_max)
    % =========================================================================
    % LOG INGESTION & TRANSIENT FILTERING (STABILIZED INTEGER-INDEX VERSION)
    % =========================================================================
    
    file_pattern = fullfile(log_folder, '*.csv');
    csv_files = dir(file_pattern);
    
    if isempty(csv_files)
        error(['No CSV files found in: ', log_folder]);
    end
    
    % Initialize empty master tables
    Master_Full   = table();
    Master_WOT    = table();
    Master_Warmup = table(); 
    Master_Hot    = table();
    global_time_offset = 0;      
    
    % Extract column names from config
    pedal_col = config.vars.pedal; 
    rpm_col   = config.vars.rpm;
    temp_col  = config.vars.tmot;
    time_col  = config.vars.time;
    
    for i = 1:length(csv_files)
        file_path = fullfile(csv_files(i).folder, csv_files(i).name);
        
        % TunerPro Header Bypass
        fid = fopen(file_path, 'r'); 
        line1 = fgetl(fid); 
        fclose(fid);
        
        if ischar(line1) && contains(line1, 'TunerPro')
            opts = detectImportOptions(file_path, 'NumHeaderLines', 1);
        else
            opts = detectImportOptions(file_path);
        end
        opts.VariableNamingRule = 'preserve'; 
        
        % Suppress variable name modification warnings
        warning('off', 'MATLAB:table:ModifiedAndSavedVarnames');
        current_log = readtable(file_path, opts);
        warning('on', 'MATLAB:table:ModifiedAndSavedVarnames');
        
        % --- STABILIZED FOOTER REMOVAL ---
        % Using explicit row slicing instead of in-place empty assignments ([])
        if height(current_log) > 1
            current_log = current_log(1:end-1, :); 
        end
        
        % Clean out any NaN rows completely
        current_log = rmmissing(current_log); 
        
        % Safety check: Skip files that don't have enough data rows
        if height(current_log) < 2
            disp(['  -> [SKIP] ', csv_files(i).name, ': Insufficient rows after cleanup.']);
            continue; 
        end
        
        all_vars = current_log.Properties.VariableNames;
        
        % -----------------------------------------------------------------
        % THE TRANSIENT (DERIVATIVE) FILTER WITH EXPLICIT NUMERIC INDEXING
        % -----------------------------------------------------------------
        if ismember(time_col, all_vars) && ismember(rpm_col, all_vars) && ismember(pedal_col, all_vars)
            
            % Force columns to 1D vertical vectors to guarantee size matching
            time_data = current_log.(time_col)(:);
            rpm_data  = current_log.(rpm_col)(:);
            pedal_data = current_log.(pedal_col)(:);
            
            % Calculate delta time (dt)
            dt = [0.1; diff(time_data)]; 
            dt(dt <= 0) = 0.001; % Prevent division by zero
            
            % Calculate Rates of Change (ROC)
            rpm_roc   = [0; diff(rpm_data)] ./ dt;
            pedal_roc = [0; diff(pedal_data)] ./ dt;
            
            % Generate stable mask and immediately convert to linear integer indices
            stable_mask = abs(rpm_roc) <= max_rpm_roc & abs(pedal_roc) <= max_pedal_roc;
            stable_row_indices = find(stable_mask); 
            
            % Slice table strictly using integers (kills row vs column vector table bugs)
            initial_rows = height(current_log);
            current_log = current_log(stable_row_indices, :);
            rows_removed = initial_rows - height(current_log);
            
            disp(['  -> [FILTER] ', csv_files(i).name, ': Removed ', num2str(rows_removed), ' transient rows.']);
        else
            disp(['  -> [WARNING] ', csv_files(i).name, ': Missing required columns. Skipping filter.']);
        end
        % -----------------------------------------------------------------
        
        % Absolute final row safety check before splitting
        if height(current_log) < 1
            disp(['  -> [SKIP] ', csv_files(i).name, ': 0 rows remaining after transient filtering.']);
            continue; 
        end
        
        % Align Timestamps Sequentially
        if config.prep.ALIGN_TIMESTAMPS == 1 && ismember(time_col, all_vars)
            current_log.(time_col) = current_log.(time_col) + global_time_offset;
            global_time_offset = max(current_log.(time_col));
        end
        
        % Apply 5120 Hack
        if config.prep.HACK_5120 == 1 && isfield(config.prep, 'pressure_columns')
            for p = 1:length(config.prep.pressure_columns)
                p_col = config.prep.pressure_columns{p};
                if ismember(p_col, all_vars)
                    current_log.(p_col) = current_log.(p_col) .* 2;
                end
            end
        end
        
        % --- STABILIZED SPLITTING ENGINE (NUMERIC LOGIC) ---
        Master_Full = vertcat(Master_Full, current_log);
        
        % Extract WOT rows safely using explicit linear indices
        if ismember(pedal_col, all_vars)
            wot_indices = find(current_log.(pedal_col) >= wot_min);
            if ~isempty(wot_indices)
                Master_WOT = vertcat(Master_WOT, current_log(wot_indices, :));
            end
        end
        
        % Extract Warmup and Hot rows safely using explicit linear indices
        if ismember(temp_col, all_vars)
            warmup_indices = find(current_log.(temp_col) < temp_max);
            hot_indices    = find(current_log.(temp_col) >= temp_max);
            
            if ~isempty(warmup_indices)
                Master_Warmup = vertcat(Master_Warmup, current_log(warmup_indices, :));
            end
            if ~isempty(hot_indices)
                Master_Hot = vertcat(Master_Hot, current_log(hot_indices, :));
            end
        end
    end
end