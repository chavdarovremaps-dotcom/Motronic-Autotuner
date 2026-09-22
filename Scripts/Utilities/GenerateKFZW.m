function [KFZW_Map, KFZW2_Map, KFZW_Counts, KFZW2_Counts] = GenerateKFZW(data, min_samples, axis_rpm, axis_load, log_vars)
    RPM_log = data.(log_vars.rpm); Load_log = data.(log_vars.load); Knock_log = data.(log_vars.knock);
    vars = data.Properties.VariableNames; vvt_idx = find(strcmpi(vars, log_vars.vvt), 1);
    if ~isempty(vvt_idx)
        VVT_log = data.(vars{vvt_idx}); mask_vvt_off = VVT_log <= 18; mask_vvt_on  = VVT_log > 18;
        [KFZW_Map, KFZW_Counts] = BilinearSplatting(Load_log(mask_vvt_off), RPM_log(mask_vvt_off), Knock_log(mask_vvt_off), axis_load, axis_rpm, min_samples);
        [KFZW2_Map, KFZW2_Counts] = BilinearSplatting(Load_log(mask_vvt_on), RPM_log(mask_vvt_on), Knock_log(mask_vvt_on), axis_load, axis_rpm, min_samples);
    else
        [KFZW_Map, KFZW_Counts] = BilinearSplatting(Load_log, RPM_log, Knock_log, axis_load, axis_rpm, min_samples); 
        KFZW2_Map = []; KFZW2_Counts = [];
    end
    KFZW_Map(isnan(KFZW_Map)) = 0; if ~isempty(KFZW2_Map), KFZW2_Map(isnan(KFZW2_Map)) = 0; end
end


