% OP-COM Log Cleaner for ME1.5.5
% 1. Removes decimal points from Engine Speed.
% 2. Converts all kPa pressures to mbar.
% 3. Renames the second 'Boost Pressure Command' to 'Boost Pressure'.
% 4. Renames the first 'Coolant Temperature' (Voltage) to 'Coolant Temp Voltage'.
% 5. Converts Fuel Trims (LTFT & STFT) from percentage to Lambda.
% 6. Batch processes all CSVs in a selected directory.

function fix_opcom_logs()
    % Prompt user to select a folder
    folderPath = uigetdir('', 'Select the folder containing your OP-COM CSV logs');
    
    if folderPath == 0
        disp('Folder selection canceled. Exiting...');
        return;
    end
    
    % Get all CSV files in the folder
    csvFiles = dir(fullfile(folderPath, '*.csv'));
    if isempty(csvFiles)
        disp('No CSV files found in the selected folder.');
        return;
    end
    
    fprintf('Found %d CSV file(s). Starting processing...\n', length(csvFiles));
    
    for i = 1:length(csvFiles)
        filePath = fullfile(csvFiles(i).folder, csvFiles(i).name);
        [~, fileName, ext] = fileparts(csvFiles(i).name);
        
        % Prevent processing files that have already been fixed
        if contains(fileName, '_fixed')
            continue;
        end
        
        try
            % Read the raw CSV data
            data = readcell(filePath);
            
            headers = data(1, :);
            units = data(2, :);
            
            % --- 1. Fix Engine Speed Decimal Point ---
            engineSpeedCols = find(strcmp(headers, 'Engine Speed'));
            for col = engineSpeedCols
                for row = 3:size(data, 1)
                    val = data{row, col};
                    if ischar(val) || isstring(val)
                        val = strrep(string(val), '.', '');
                        data{row, col} = str2double(val);
                    elseif isnumeric(val)
                        valStr = strrep(num2str(val), '.', '');
                        data{row, col} = str2double(valStr);
                    end
                end
            end
            
            % --- 2. Convert kPa to mbar ---
            kpaCols = find(strcmp(units, 'kPa'));
            for col = kpaCols
                data{2, col} = 'mbar'; % Update the unit row text
                for row = 3:size(data, 1)
                    val = data{row, col};
                    if isnumeric(val)
                        data{row, col} = val * 10;
                    elseif ischar(val) || isstring(val)
                        numVal = str2double(val);
                        if ~isnan(numVal)
                            data{row, col} = numVal * 10;
                        end
                    end
                end
            end
            
            % --- 3. Fix Duplicate Boost Pressure Command ---
            boostCols = find(strcmp(headers, 'Boost Pressure Command'));
            if length(boostCols) >= 2
                data{1, boostCols(2)} = 'Boost Pressure';
            end
            
            % --- 4. Fix Duplicate Coolant Temperature ---
            coolantCols = find(strcmp(headers, 'Coolant Temperature'));
            if length(coolantCols) >= 2
                data{1, coolantCols(1)} = 'Coolant Temp Voltage';
            end
            
            % --- 5. Convert Fuel Trims to Lambda ---
            trimHeaders = {'B1 Long Term Fuel Trim (Bank 1)', 'B1 Short Term Fuel Trim (Bank 1)'};
            for t = 1:length(trimHeaders)
                trimCols = find(strcmp(headers, trimHeaders{t}));
                for col = trimCols
                    data{2, col} = 'Lambda'; % Change unit from % to Lambda
                    for row = 3:size(data, 1)
                        val = data{row, col};
                        if isnumeric(val)
                            data{row, col} = (val / 100) + 1;
                        elseif ischar(val) || isstring(val)
                            numVal = str2double(val);
                            if ~isnan(numVal)
                                data{row, col} = (numVal / 100) + 1;
                            end
                        end
                    end
                end
            end
            
            % --- Clean Up ---
            % Convert 'missing' (NaN) back to empty strings
            data(cellfun(@(x) any(ismissing(x)), data)) = {''};
            
            % Save file with a suffix
            newFilePath = fullfile(csvFiles(i).folder, [fileName, '_fixed', ext]);
            writecell(data, newFilePath);
            
            fprintf('Successfully processed: %s\n', [fileName, ext]);
            
        catch ME
            fprintf('Error processing file %s: %s\n', csvFiles(i).name, ME.message);
        end
    end
    
    disp('Done! All OP-COM logs have been fixed.');
end