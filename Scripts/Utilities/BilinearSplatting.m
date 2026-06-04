function [Z_Map, countArray] = BilinearSplatting(X_data, Y_data, Z_data, x_axis, y_axis, min_samples)
    numCols = length(x_axis); numRows = length(y_axis); sumArray = zeros(numRows, numCols); countArray = zeros(numRows, numCols);
    for i = 1:length(X_data)
        xVal = X_data(i); yVal = Y_data(i); zVal = Z_data(i);
        if ~isnan(xVal) && ~isnan(yVal) && ~isnan(zVal)
            [xIdx, xFrac] = GetInterpolation(xVal, x_axis); [yIdx, yFrac] = GetInterpolation(yVal, y_axis);
            w00 = (1 - yFrac) * (1 - xFrac); w10 = yFrac * (1 - xFrac); w01 = (1 - yFrac) * xFrac; w11 = yFrac * xFrac;
            sumArray(yIdx, xIdx) = sumArray(yIdx, xIdx) + (w00 * zVal); countArray(yIdx, xIdx) = countArray(yIdx, xIdx) + w00;
            if yIdx < numRows, sumArray(yIdx+1, xIdx) = sumArray(yIdx+1, xIdx) + (w10 * zVal); countArray(yIdx+1, xIdx) = countArray(yIdx+1, xIdx) + w10; end
            if xIdx < numCols, sumArray(yIdx, xIdx+1) = sumArray(yIdx, xIdx+1) + (w01 * zVal); countArray(yIdx, xIdx+1) = countArray(yIdx, xIdx+1) + w01; end
            if yIdx < numRows && xIdx < numCols, sumArray(yIdx+1, xIdx+1) = sumArray(yIdx+1, xIdx+1) + (w11 * zVal); countArray(yIdx+1, xIdx+1) = countArray(yIdx+1, xIdx+1) + w11; end
        end
    end
    Z_Map = NaN(numRows, numCols);
    for r = 1:numRows
        for c = 1:numCols
            if countArray(r, c) >= min_samples, Z_Map(r, c) = sumArray(r, c) / countArray(r, c); end
        end
    end
end
