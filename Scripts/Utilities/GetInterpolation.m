function [lowerIdx, fraction] = GetInterpolation(val, axisArray)
    maxIdx = length(axisArray);
    if val <= axisArray(1), lowerIdx = 1; fraction = 0; return; end
    if val >= axisArray(maxIdx), lowerIdx = maxIdx; fraction = 0; return; end
    for i = 1:maxIdx-1
        if val >= axisArray(i) && val < axisArray(i+1), lowerIdx = i; fraction = (val - axisArray(i)) / (axisArray(i+1) - axisArray(i)); return; end
    end
end