function KFVPDKSD_Map = GenerateKFVPDKSD(Base_Pressure_Curve, axis_rpm, axis_pratio, pu_constant)
    numCols = length(axis_rpm); numRows = length(axis_pratio); KFVPDKSD_Map = ones(numRows, numCols);
    valid_idx = ~isnan(Base_Pressure_Curve);
    if sum(valid_idx) >= 2, filled_curve = interp1(axis_rpm(valid_idx), Base_Pressure_Curve(valid_idx), axis_rpm, 'linear', 'extrap');
    else, filled_curve = Base_Pressure_Curve; end
    for c = 1:numCols
        if isnan(filled_curve(c)), KFVPDKSD_Map(:, c) = NaN; continue; end
        base_ratio = filled_curve(c) / pu_constant;
        for r = 1:numRows
            if base_ratio > axis_pratio(r), KFVPDKSD_Map(r, c) = 0.95; else, KFVPDKSD_Map(r, c) = 1.0; end
        end
    end
    valid_mask = ~isnan(KFVPDKSD_Map);
    if any(valid_mask(:))
        padded = [KFVPDKSD_Map(1,:); KFVPDKSD_Map; KFVPDKSD_Map(end,:)]; padded = [padded(:,1), padded, padded(:,end)];
        smoothed = conv2(padded, ones(3,3)/9, 'valid'); smoothed(smoothed > 1.0) = 1.0; smoothed(smoothed < 0.95) = 0.95;
        smoothed(~valid_mask) = NaN; KFVPDKSD_Map = smoothed;
    end
end
