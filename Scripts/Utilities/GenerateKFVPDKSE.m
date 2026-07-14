function KFVPDKSE_Map = GenerateKFVPDKSE(KFVPDKSD_ME7_Map, axis_pratio_me7, axis_rpm_me7, ...
                                         axis_ratio_med9, axis_rpm_med9, ...
                                         plxs_w, axis_rpm_plxs, ...
                                         plgru_w, axis_rpm_plgru, ambient_p)
    % =========================================================================
    % MED9.1 KFVPDKSE TRANSFORMATION ENGINE
    % Translates ME7 Throttle Handover mapping into MED9 Normalized Ratios
    % =========================================================================

    num_rows = length(axis_ratio_med9);
    num_cols = length(axis_rpm_med9);
    KFVPDKSE_Map = NaN(num_rows, num_cols);

    % 1. Interpolate physical pressure curves to perfectly match the MED9 RPM axis
    plxs_interp = interp1(axis_rpm_plxs, plxs_w, axis_rpm_med9, 'linear', 'extrap');

    valid_plgru = ~isnan(plgru_w);
    if sum(valid_plgru) >= 2
        plgru_interp = interp1(axis_rpm_plgru(valid_plgru), plgru_w(valid_plgru), axis_rpm_med9, 'linear', 'extrap');
    else
        plgru_interp = repmat(ambient_p, 1, num_cols); % Safety Fallback
    end

    % 2. Create a 2D Interpolant of the ME7 Map so we can sample it anywhere
    [X_me7, Y_me7] = meshgrid(axis_rpm_me7, axis_pratio_me7);
    F_me7 = scatteredInterpolant(X_me7(:), Y_me7(:), KFVPDKSD_ME7_Map(:), 'linear', 'nearest');

    % 3. Execute the Coordinate Transformation
    for c = 1:num_cols
        current_rpm = axis_rpm_med9(c);
        P_base = plgru_interp(c);  % plgru_w
        P_max  = plxs_interp(c);   % plxs_w

        for r = 1:num_rows
            R_med9 = axis_ratio_med9(r);

            % A. Calculate the physical Target Pressure (mbar) required for this MED9 cell
            P_target = R_med9 * (P_max - P_base) + P_base;

            % B. Convert physical pressure into the ME7 Pressure Ratio
            R_me7 = P_target / ambient_p;

            % C. Lookup the ME7 throttle value for this RPM and Ratio
            KFVPDKSE_Map(r, c) = F_me7(current_rpm, R_me7);
        end
    end

    % 4. Clean up the map (Throttle cannot open more than 100%)
    KFVPDKSE_Map(KFVPDKSE_Map > 1.0) = 1.0;
end