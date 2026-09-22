function ExportAllMapsToExcel(filename, KFLDIMX_Map, KFLDRL_Map, KFLDRL_Counts, Abs_WGDC_Map, Abs_WGDC_Counts, ...
                              Base_Pressure_Curve, Base_Pressure_Counts, KFVPDKSD_Map, ...
                              KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map, ...
                              FKKVS_Map, FKKVS_Counts, KFZW_Map, KFZW_Counts, KFZW2_Map, KFZW2_Counts, ...
                              KFURL_Map, KFPRG_Map, Saugrohr_Counts, ...
                              axis_rpm_boost, axis_boost, axis_boost_abs, axis_kfldrl_x, axis_rpm_kfvp, axis_pratio_kfvp, axis_tmot, axis_load_kffwlw, axis_rpm_kffwlw, axis_rpm_fuel, axis_te, axis_rpm_ign, axis_load_ign, axis_rpm_url, axis_vvt_url)
% FUNCTION: Side-By-Side Excel Exporter
% ========================================================================    
output_cells = {};
    
function add_linked_maps_to_sheet(title_str1, map_data1, title_str2, map_data2, x_axis, y_axis, secondary_x_label, secondary_x_data)
        if isempty(map_data1), return; end
        
        % =================================================================
        % BULLETPROOF DIMENSION ALIGNMENT
        % Auto-transposes or pads matrices to prevent array bound crashes
        % =================================================================
        if size(map_data1, 1) ~= length(y_axis) || size(map_data1, 2) ~= length(x_axis)
            % Check if it just needs to be flipped
            if size(map_data1, 1) == length(x_axis) && size(map_data1, 2) == length(y_axis)
                map_data1 = map_data1';
                if nargin > 3 && ~isempty(map_data2), map_data2 = map_data2'; end
            else
                % If sizes are completely mismatched, safely resize to prevent crash
                new_map1 = NaN(length(y_axis), length(x_axis));
                r_max = min(size(map_data1, 1), length(y_axis));
                c_max = min(size(map_data1, 2), length(x_axis));
                new_map1(1:r_max, 1:c_max) = map_data1(1:r_max, 1:c_max);
                map_data1 = new_map1;
                
                if nargin > 3 && ~isempty(map_data2)
                    new_map2 = NaN(length(y_axis), length(x_axis));
                    r_max2 = min(size(map_data2, 1), length(y_axis));
                    c_max2 = min(size(map_data2, 2), length(x_axis));
                    new_map2(1:r_max2, 1:c_max2) = map_data2(1:r_max2, 1:c_max2);
                    map_data2 = new_map2;
                end
            end
        end
        % =================================================================

        start_row = size(output_cells, 1) + 1; gap_cols = 2; col_offset = length(x_axis) + 1 + gap_cols; 
        
        output_cells{start_row, 1} = title_str1;
        if nargin > 3 && ~isempty(map_data2), output_cells{start_row, 1 + col_offset} = title_str2; end
        
        header_row = cell(1, length(x_axis) + 1); header_row{1} = 'Y-Axis \ X-Axis'; 
        for c = 1:length(x_axis), header_row{c+1} = x_axis(c); end
        output_cells(start_row + 1, 1:length(header_row)) = header_row;
        if nargin > 3 && ~isempty(map_data2), output_cells(start_row + 1, (1 + col_offset):(length(header_row) + col_offset)) = header_row; end
        
        current_r = start_row + 2;
        if nargin > 6 && ~isempty(secondary_x_data)
            header_row_2 = cell(1, length(x_axis) + 1); header_row_2{1} = secondary_x_label;
            for c = 1:length(secondary_x_data), header_row_2{c+1} = round(secondary_x_data(c), 1); end
            output_cells(current_r, 1:length(header_row_2)) = header_row_2;
            if nargin > 3 && ~isempty(map_data2), output_cells(current_r, (1 + col_offset):(length(header_row_2) + col_offset)) = header_row_2; end
            current_r = current_r + 1;
        end
        
        for r = 1:length(y_axis)
            data_row1 = cell(1, length(x_axis) + 1);
            if iscell(y_axis) || isstring(y_axis), data_row1{1} = char(y_axis(r)); else, data_row1{1} = y_axis(r); end
            data_row2 = data_row1; 
            for c = 1:length(x_axis)
                if isnan(map_data1(r,c)), data_row1{c+1} = ''; else, data_row1{c+1} = round(map_data1(r,c), 5); end
                if nargin > 3 && ~isempty(map_data2)
                    if isnan(map_data2(r,c)), data_row2{c+1} = ''; else, data_row2{c+1} = round(map_data2(r,c), 5); end
                end
            end
            output_cells(current_r, 1:length(data_row1)) = data_row1;
            if nargin > 3 && ~isempty(map_data2), output_cells(current_r, (1 + col_offset):(length(data_row2) + col_offset)) = data_row2; end
            current_r = current_r + 1;
        end
        output_cells{current_r, 1} = ''; 
    end

    add_linked_maps_to_sheet('KFLDIMX (Linear Converter Map)', KFLDIMX_Map, '', [], axis_boost, axis_rpm_boost);
    
    min_boost_axis = axis_boost(1); max_boost_axis = axis_boost(end);
    physical_boost_axis = min_boost_axis + (axis_kfldrl_x / 100) .* (max_boost_axis - min_boost_axis);
    add_linked_maps_to_sheet('KFLDRL (Base Linearization - WGDC %)', KFLDRL_Map, 'KFLDRL - SAMPLE WEIGHTS', KFLDRL_Counts, axis_kfldrl_x, axis_rpm_boost, 'Target Rel Boost (mbar)', physical_boost_axis);
    
    add_linked_maps_to_sheet('ABSOLUTE WGDC MAP (Abs Boost vs RPM)', Abs_WGDC_Map, 'ABS WGDC - SAMPLE WEIGHTS', Abs_WGDC_Counts, axis_boost_abs, axis_rpm_boost);
    add_linked_maps_to_sheet('Base WG Pressure (Abs mbar)', Base_Pressure_Curve, 'Base WG - SAMPLE WEIGHTS', Base_Pressure_Counts, axis_rpm_kfvp, {'Base Boost'});
    add_linked_maps_to_sheet('KFVPDKSD (Steady State Throttle Handover)', KFVPDKSD_Map, '', [], axis_rpm_kfvp, axis_pratio_kfvp);
    
    % New Warmup Maps
    add_linked_maps_to_sheet('KFFWL (Warmup Enrichment % vs Temp)', KFFWL_Map, 'KFFWL - SAMPLE WEIGHTS', KFFWL_Counts, axis_tmot, {'Trim %'});
    add_linked_maps_to_sheet('FKKVS_RL (Hot Trims mapped to Load/RPM)', FKKVS_RL_Map, '', [], axis_load_kffwlw, axis_rpm_kffwlw);
    add_linked_maps_to_sheet('KFFWLW (Warmup Weighting % vs Load/RPM)', KFFWLW_Map, 'KFFWLW - SAMPLE WEIGHTS', KFFWLW_Counts, axis_load_kffwlw, axis_rpm_kffwlw);

    add_linked_maps_to_sheet('FKKVS (Fuel Trim Correction %)', FKKVS_Map, 'FKKVS - SAMPLE WEIGHTS', FKKVS_Counts, axis_te, axis_rpm_fuel);
    add_linked_maps_to_sheet('KFZW (Ignition Knock Correction - VVT OFF)', KFZW_Map, 'KFZW - SAMPLE WEIGHTS', KFZW_Counts, axis_load_ign, axis_rpm_ign);
    add_linked_maps_to_sheet('KFZW2 (Ignition Knock Correction - VVT ON)', KFZW2_Map, 'KFZW2 - SAMPLE WEIGHTS', KFZW2_Counts, axis_load_ign, axis_rpm_ign);
    

% =========================================================================
    % SAUGROHRMODELL EXPORT (2D KFURL & KFPRG)
    % =========================================================================
    if ~isempty(KFURL_Map)
        add_linked_maps_to_sheet('KFURL: Volumetric Efficiency Slope (% / hPa)', KFURL_Map, 'KFURL - SAMPLE WEIGHTS', Saugrohr_Counts, axis_vvt_url, axis_rpm_url);
        add_linked_maps_to_sheet('KFPRG: Residual Exhaust Gas Pressure (hPa)', KFPRG_Map, 'KFPRG - SAMPLE WEIGHTS', Saugrohr_Counts, axis_vvt_url, axis_rpm_url);
    end
    




    if ~isempty(output_cells)
        writecell(output_cells, filename, 'Sheet', 'Tuning Maps');
        disp(['Success! All generated maps saved to: ', filename]);
    end
end
