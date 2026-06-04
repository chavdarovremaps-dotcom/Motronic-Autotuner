function [KFFWL_Map, KFFWL_Counts, KFFWLW_Map, KFFWLW_Counts, FKKVS_RL_Map] = GenerateWarmupMaps(data_warmup, data_full, min_samples, axis_tmot, axis_load, axis_rpm, log_vars, trim_format)
    req_vars = {log_vars.tmot, log_vars.stft, log_vars.ltft, log_vars.load, log_vars.rpm};
    for v = 1:length(req_vars)
        if ~ismember(req_vars{v}, data_warmup.Properties.VariableNames) || ~ismember(req_vars{v}, data_full.Properties.VariableNames)
            error(['Missing required variable for Warmup: ', req_vars{v}]);
        end
    end
    
    % 1. Calculate Raw Trims for Hot and Cold data
    if trim_format == 0
        Raw_Trim_Hot = (data_full.(log_vars.stft) .* data_full.(log_vars.ltft) - 1.0) .* 100;
        Raw_Trim_Cold = (data_warmup.(log_vars.stft) .* data_warmup.(log_vars.ltft) - 1.0) .* 100;
    else
        Raw_Trim_Hot = data_full.(log_vars.stft) + data_full.(log_vars.ltft);
        Raw_Trim_Cold = data_warmup.(log_vars.stft) + data_warmup.(log_vars.ltft);
    end
    
    % 2. Filter Hot Data (tmot >= 80) and find global baseline fallback
    hot_mask = data_full.(log_vars.tmot) >= 80;
    data_hot = data_full(hot_mask, :);
    Raw_Trim_Hot_Filtered = Raw_Trim_Hot(hot_mask);
    
    if sum(hot_mask) > 10
        Base_Hot_Trim = mean(Raw_Trim_Hot_Filtered, 'omitnan');
    else
        Base_Hot_Trim = 0;
        disp('Warning: Not enough data > 80C to calculate hot trims. Assuming base fueling is perfect.');
    end
    
    % 3. Generate FKKVS_RL (Hot Trims mapped onto Load vs RPM axes)
    [FKKVS_RL_Map, ~] = BilinearSplatting(data_hot.(log_vars.load), data_hot.(log_vars.rpm), Raw_Trim_Hot_Filtered, axis_load, axis_rpm, min_samples);
    
    % Fallback: If a Load/RPM cell wasn't hit while hot, fill it with the global average hot trim
    FKKVS_RL_Filled = FKKVS_RL_Map;
    FKKVS_RL_Filled(isnan(FKKVS_RL_Filled)) = Base_Hot_Trim;
    
    % 4. 1D Splatting for KFFWL (Temp vs Trim)
    Net_Warmup_Trim_Pct = Raw_Trim_Cold - Base_Hot_Trim;
    [KFFWL_Map, KFFWL_Counts] = LinearSplatting1D(data_warmup.(log_vars.tmot), Net_Warmup_Trim_Pct, axis_tmot, min_samples);
    
    % Force the operating temp cells to exactly 0.00%
    for i = 1:length(axis_tmot)
        if axis_tmot(i) >= 80 && ~isnan(KFFWL_Map(i))
            KFFWL_Map(i) = 0.00;
        end
    end

    % 5. Generate Raw KFFWLW (Cold Trims mapped onto Load vs RPM)
    [KFFWLW_Raw, KFFWLW_Counts] = BilinearSplatting(data_warmup.(log_vars.load), data_warmup.(log_vars.rpm), Raw_Trim_Cold, axis_load, axis_rpm, min_samples);
    
    % 6. True KFFWLW calculation: Subtract the base hot correction (FKKVS_RL) from the raw cold trims
    KFFWLW_Map = KFFWLW_Raw - FKKVS_RL_Filled;
end
