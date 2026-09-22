function [Z_Curve, countArray] = LinearSplatting1D(X_data, Z_data, x_axis, min_samples)
    numCols = length(x_axis); sumArray = zeros(1, numCols); countArray = zeros(1, numCols);
    for i = 1:length(X_data)
        xVal = X_data(i); zVal = Z_data(i);
        if ~isnan(xVal) && ~isnan(zVal)
            [xIdx, xFrac] = GetInterpolation(xVal, x_axis); w0 = 1 - xFrac; w1 = xFrac;
            sumArray(xIdx) = sumArray(xIdx) + (w0 * zVal); countArray(xIdx) = countArray(xIdx) + w0;
            if xIdx < numCols, sumArray(xIdx+1) = sumArray(xIdx+1) + (w1 * zVal); countArray(xIdx+1) = countArray(xIdx+1) + w1; end
        end
    end
    Z_Curve = NaN(1, numCols);
    for c = 1:numCols
        if countArray(c) >= min_samples, Z_Curve(c) = sumArray(c) / countArray(c); end
    end
end
