function [Base_Pressure_Curve, Base_Pressure_Counts] = GenerateBaseWGPressure(data, min_samples, axis_rpm, log_vars)
    base_wg_mask = (data.(log_vars.wgdc) < 10); 
    RPM_base   = data.(log_vars.rpm)(base_wg_mask);
    Boost_base = data.(log_vars.boost)(base_wg_mask);
    [Base_Pressure_Curve, Base_Pressure_Counts] = LinearSplatting1D(RPM_base, Boost_base, axis_rpm, min_samples);
end
