function [FKKVS_Map, FKKVS_Counts] = GenerateFKKVS(data, min_samples, axis_rpm, axis_te, log_vars, trim_format)
    if trim_format == 0
        Trim_Pct_log = (data.(log_vars.stft) .* data.(log_vars.ltft) - 1.0) .* 100;
    else
        Trim_Pct_log = data.(log_vars.stft) + data.(log_vars.ltft);
    end
    [FKKVS_Map, FKKVS_Counts] = BilinearSplatting(data.(log_vars.inj), data.(log_vars.rpm), Trim_Pct_log, axis_te, axis_rpm, min_samples);
    FKKVS_Map(isnan(FKKVS_Map)) = 0;
end
