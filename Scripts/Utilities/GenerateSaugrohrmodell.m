function [KFURL_Map, KFPRG_Map, Points_Count] = GenerateSaugrohrmodell(data, axis_rpm, axis_vvt, base_kfurl, base_kfprg, log_vars, min_samples)
    % =========================================================================
    % SAUGROHRMODELL CALIBRATION (2D Linear Regression)
    % Layout: RPM (Y-Axis / Rows) x VVT (X-Axis / Columns)
    % =========================================================================
    
    KFURL_Map = base_kfurl;
    KFPRG_Map = base_kfprg;
    Points_Count = zeros(length(axis_rpm), length(axis_vvt)); 
    
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
    
    if ~ismember(vvt_col, data.Properties.VariableNames)
        disp(['  [INFO] VVT column (', vvt_col, ') not found. Assuming 0 cam angle.']);
        vvt_data = zeros(height(data), 1);
    else
        vvt_data = data.(vvt_col);
    end
    
    % 3. Iterate through RPM (Rows) and VVT (Columns)
    for r = 1:length(axis_rpm)
        target_rpm = axis_rpm(r);
        
        if r == 1, rpm_min = target_rpm - 200; rpm_max = (axis_rpm(r) + axis_rpm(r+1)) / 2;
        elseif r == length(axis_rpm), rpm_min = (axis_rpm(r-1) + axis_rpm(r)) / 2; rpm_max = target_rpm + 200;
        else, rpm_min = (axis_rpm(r-1) + axis_rpm(r)) / 2; rpm_max = (axis_rpm(r) + axis_rpm(r+1)) / 2;
        end
        
        for c = 1:length(axis_vvt)
            target_vvt = axis_vvt(c);
            
            if length(axis_vvt) == 1, vvt_min = -100; vvt_max = 100; 
            elseif c == 1, vvt_min = target_vvt - 10; vvt_max = (axis_vvt(c) + axis_vvt(c+1)) / 2;
            elseif c == length(axis_vvt), vvt_min = (axis_vvt(c-1) + axis_vvt(c)) / 2; vvt_max = target_vvt + 10;
            else, vvt_min = (axis_vvt(c-1) + axis_vvt(c)) / 2; vvt_max = (axis_vvt(c) + axis_vvt(c+1)) / 2;
            end
            
            idx = rpm_data >= rpm_min & rpm_data < rpm_max & vvt_data >= vvt_min & vvt_data < vvt_max;
            bin_ps = ps_data(idx);
            bin_load = load_data(idx);
            
            valid_idx = bin_load > 15;
            bin_ps = bin_ps(valid_idx);
            bin_load = bin_load(valid_idx);
            
            Points_Count(r, c) = length(bin_ps);
            
            if length(bin_ps) >= min_samples && (max(bin_ps) - min(bin_ps)) > 200
                p = polyfit(bin_ps, bin_load, 1);
                m = p(1); 
                b = p(2); 
                x_intercept = -b / m; 
                
                if m > 0 && x_intercept >= 0 && x_intercept <= 400
                    KFURL_Map(r, c) = m;
                    KFPRG_Map(r, c) = x_intercept;
                end
            end
        end
    end
end