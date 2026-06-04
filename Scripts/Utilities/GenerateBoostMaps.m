function [KFLDIMX_Map, KFLDRL_Map, Abs_WGDC_Map, axis_boost_abs, KFLDRL_Counts, Abs_WGDC_Counts] = GenerateBoostMaps(data, CWLDIMX, ambient_pressure, safety_margin, FILL_MISSING_DATA, min_samples, axis_rpm, axis_boost, axis_kfldrl_x, log_vars)
    if CWLDIMX == 1, Relative_Boost_log = data.(log_vars.boost) - data.(log_vars.pu);
    else, Relative_Boost_log = data.(log_vars.boost) - ambient_pressure; end

    numRows = length(axis_rpm); max_boost_axis = max(axis_boost); min_boost_axis = axis_boost(1); max_pid_limit = 100; 
    
    KFLDIMX_Map = zeros(numRows, length(axis_boost));
    for c = 1:length(axis_boost), KFLDIMX_Map(:, c) = ((axis_boost(c) - min_boost_axis) / (max_boost_axis - min_boost_axis)) * max_pid_limit; end

    physical_boost_axis = min_boost_axis + (axis_kfldrl_x / max_pid_limit) .* (max_boost_axis - min_boost_axis);
    [KFLDRL_Map, KFLDRL_Counts] = BilinearSplatting(Relative_Boost_log, data.(log_vars.rpm), data.(log_vars.wgdc), physical_boost_axis, axis_rpm, min_samples);

    if FILL_MISSING_DATA == 1
        valid_mask = ~isnan(KFLDRL_Map); 
        [X_grid_drl, Y_grid_drl] = meshgrid(physical_boost_axis, axis_rpm);
        if sum(valid_mask(:)) > 4
            F_drl = scatteredInterpolant(X_grid_drl(valid_mask), Y_grid_drl(valid_mask), KFLDRL_Map(valid_mask), 'linear', 'nearest');
            KFLDRL_Map = F_drl(X_grid_drl, Y_grid_drl);
        end
        KFLDRL_Map(:, end) = max_pid_limit; 
    end
    KFLDRL_Map(KFLDRL_Map < 0) = 0; KFLDRL_Map(KFLDRL_Map > 95) = 95;
    
    axis_boost_abs = axis_boost + ambient_pressure;
    [Abs_WGDC_Map, Abs_WGDC_Counts] = BilinearSplatting(data.(log_vars.boost), data.(log_vars.rpm), data.(log_vars.wgdc), axis_boost_abs, axis_rpm, min_samples);
end
