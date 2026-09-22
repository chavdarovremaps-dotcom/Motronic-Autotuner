function [KFURL_Map, KFPRG_Map, Points_Count, axis_vvt_out] = GenerateSaugrohrmodell(data, axis_rpm, log_vars, min_samples, vvt_enabled, vvt_threshold)
    % =========================================================================
    % SAUGROHRMODELL CALIBRATION (Strict Binary VVT Regression)
    % Layout: RPM (Y-Axis / Rows) x VVT (X-Axis / Columns)
    % =========================================================================
    
    % 1. Force the Digital VVT Axis
    if vvt_enabled == 1
        axis_vvt_out = [0, vvt_threshold]; % Strictly 2 Columns (OFF and ON)
    else
        axis_vvt_out = [0];                % Strictly 1 Column (Disabled)
    end
    
    % 2. Pre-allocate pure NaN maps (No factory fallback)
    KFURL_Map = NaN(length(axis_rpm), length(axis_vvt_out));
    KFPRG_Map = NaN(length(axis_rpm), length(axis_vvt_out));
    Points_Count = zeros(length(axis_rpm), length(axis_vvt_out)); 
    
    % 3. Extract Data columns
    rpm_col = log_vars.rpm;
    load_col = log_vars.load;
    ps_col = log_vars.ps_w; 
    vvt_col = log_vars.vvt;
    
    if ~ismember(ps_col, data.Properties.VariableNames)
        error(['Intake pressure column (', ps_col, ') not found in logs.']);
    end
    
    rpm_data = data.(rpm_col);
    load_data = data.(load_col);
    ps_data = data.(ps_col);
    
    if ~ismember(vvt_col, data.Properties.VariableNames) || vvt_enabled == 0
        disp(['  [INFO] VVT Disabled or missing. Forcing single-column calculation.']);
        vvt_data = zeros(height(data), 1);
    else
        vvt_data = data.(vvt_col);
    end
    
    % 4. Iterate through RPM (Rows) and strict Binary VVT (Columns)
    for r = 1:length(axis_rpm)
        target_rpm = axis_rpm(r);
        
        if r == 1, rpm_min = target_rpm - 200; rpm_max = (axis_rpm(r) + axis_rpm(r+1)) / 2;
        elseif r == length(axis_rpm), rpm_min = (axis_rpm(r-1) + axis_rpm(r)) / 2; rpm_max = target_rpm + 200;
        else, rpm_min = (axis_rpm(r-1) + axis_rpm(r)) / 2; rpm_max = (axis_rpm(r) + axis_rpm(r+1)) / 2;
        end
        
        for c = 1:length(axis_vvt_out)
            target_vvt = axis_vvt_out(c);
            % Strict ON/OFF Routing based on column index
            if vvt_enabled == 1
                if c == 1 % VVT OFF Column (0)
                    vvt_min = -inf;
                    vvt_max = vvt_threshold;
                else      % VVT ON Column (Threshold value)
                    vvt_min = vvt_threshold;
                    vvt_max = inf;
                end
            else
                % VVT Disabled Catch-All
                vvt_min = -inf;
                vvt_max = inf;
            end
            
            idx = rpm_data >= rpm_min & rpm_data < rpm_max & vvt_data >= vvt_min & vvt_data < vvt_max;
            bin_ps = ps_data(idx);
            bin_load = load_data(idx);
            
            valid_idx = bin_load > 15;
            bin_ps = bin_ps(valid_idx);
            bin_load = bin_load(valid_idx);
            
            Points_Count(r, c) = length(bin_ps);
            
            % =========================================================================
            % --- SMART REGRESSION ENGINE (WITH HIGH-RPM ANCHORING) ---
            % =========================================================================
            if length(bin_ps) >= min_samples && (max(bin_ps) - min(bin_ps)) > 20
                
                % 1. Run the initial standard regression
                p = polyfit(bin_ps, bin_load, 1);
                m = p(1); 
                b = p(2); 
                x_intercept = -b / m; 
                
                % 2. Catch the Extrapolation Trap (Negative KFPRG)
                if x_intercept < 0
                    
                    % Keep the original values for the notification
                    orig_intercept = x_intercept;
                    orig_slope = m;
                    
                    % Apply the Anchor: Force KFPRG to a safe, positive physical value
                    x_intercept = 20; 
                    
                    % Recalculate the slope (KFURL) originating from our 20 hPa anchor,
                    % passing exactly through the center of mass of our WOT data cluster.
                    m = mean(bin_load) / (mean(bin_ps) - x_intercept);
                    
                    % Notify the user in the console
                    disp(['  [ANCHOR APPLIED] RPM: ', num2str(target_rpm), ' | VVT: ', num2str(target_vvt), ...
                          ' | KFPRG was ', num2str(round(orig_intercept,1)), ' -> Anchored to 20 hPa. ', ...
                          'KFURL recalculated from ', num2str(round(orig_slope,4)), ' to ', num2str(round(m,4))]);
                end
                
                % 3. RELAXED PHYSICS BOUNDS (Sanity Check)
                if m > 0 && x_intercept >= -200 && x_intercept <= 800
                    KFURL_Map(r, c) = m;
                    KFPRG_Map(r, c) = x_intercept;
                else
                    % Print exactly what impossible numbers it tried to calculate
                    disp(['  [REJECTED] RPM: ', num2str(target_rpm), ' | VVT: ', num2str(target_vvt), ...
                          ' | Slope: ', num2str(round(m,5)), ' | Intercept (PRG): ', num2str(round(x_intercept,1))]);
                end
            end
            % =========================================================================
        end
    end
end