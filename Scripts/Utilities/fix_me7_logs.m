% ME7-Logger CSV Cleaner & 5120 Hack Applier
% 1. Strips all metadata above the "TimeStamp" header row.
% 2. Searches for 'mbar' units and applies a 2x multiplier if hack_5120 is enabled.
% 3. Batch processes all CSVs in a selected directory.

function fix_me7_logs()
    % --- CONFIGURATION ---
    % 5120 MAP Sensor Hack (1 = Enable, 0 = Disable)
    % When enabled, multiplies all variables with 'mbar' units by 2.
    hack_5120 = 0; 
    % ---------------------

    % Prompt user to select a folder
    folderPath = uigetdir('', 'Select the folder containing your ME7-Logger CSV logs');
    
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
            
            % --- 1. Strip Header Metadata ---
            % We need to find the row that starts with 'TimeStamp'
            headerRow = 0;
            for r = 1:size(data, 1)
                % Check the first column for the TimeStamp marker
                % (Using strtrim to clean up any weird ME7 Logger spaces)
                val = data{r, 1}; 
                if ischar(val) || isstring(val)
                    if contains(strtrim(string(val)), 'TimeStamp', 'IgnoreCase', true)
                        headerRow = r;
                        break;
                    end
                end
            end
            
            if headerRow == 0
                fprintf('Warning: Could not find "TimeStamp" in %s. Skipping...\n', csvFiles(i).name);
                continue;
            end
            
            % Slice the data to keep only the headers, units, and actual log values
            cleanData = data(headerRow:end, :);
            
            % --- 2. Apply the 5120 Hack ---
            if hack_5120 == 1
                % In the new cleanData, row 2 is ALWAYS the unit row
                units = cleanData(2, :);
                
                for col = 1:length(units)
                    unitVal = units{col};
                    
                    % Check if the unit is 'mbar' (ignoring spaces and casing)
                    if (ischar(unitVal) || isstring(unitVal)) && strcmpi(strtrim(string(unitVal)), 'mbar')
                        
                        % It's a pressure column! Loop through the data rows and multiply by 2
                        for row = 3:size(cleanData, 1)
                            val = cleanData{row, col};
                            if isnumeric(val)
                                cleanData{row, col} = val * 2;
                            elseif ischar(val) || isstring(val)
                                % Handle if MATLAB read it as a string for some reason
                                numVal = str2double(val);
                                if ~isnan(numVal)
                                    cleanData{row, col} = numVal * 2;
                                end
                            end
                        end
                    end
                end
            end
            
            % --- Clean Up ---
            % MATLAB readcell turns empty trailing commas into 'missing' (NaN).
            % Convert them back to empty strings for a clean export.
            cleanData(cellfun(@(x) any(ismissing(x)), cleanData)) = {''};
            
            % Save file with a suffix so the original raw log is preserved
            newFilePath = fullfile(csvFiles(i).folder, [fileName, '_fixed', ext]);
            writecell(cleanData, newFilePath);
            
            fprintf('Successfully processed: %s\n', [fileName, ext]);
            
        catch ME
            fprintf('Error processing file %s: %s\n', csvFiles(i).name, ME.message);
        end
    end
    
    if hack_5120 == 1
        disp('Done! All ME7 logs fixed and 5120 Hack (2x mbar multiplier) applied.');
    else
        disp('Done! All ME7 logs fixed. (5120 Hack was disabled).');
    end
end