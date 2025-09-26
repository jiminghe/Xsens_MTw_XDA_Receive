function varargout = log_utils(action, varargin)
    % LOG_UTILS Utility functions for MTw data logging
    %
    % Usage:
    %   log_utils('init')                    - Initialize logging (call once at start)
    %   log_utils('init', filename)          - Initialize with custom filename
    %   log_utils('log', deviceId, ...)      - Log data point
    %   log_utils('close')                   - Close log file
    %
    % Example:
    %   log_utils('init');  % Initialize logging
    %   log_utils('log', deviceId, packetCounter, eulerAngles, quat, acc, gyr, mag, freeAcc, status);
    %   log_utils('close'); % Close when done
    
    persistent fileHandle headerWritten currentFilename isInitialized
    
    switch lower(action)
        case 'init'
            % Initialize logging
            if nargin > 1
                filename = varargin{1};
            else
                timestamp = datestr(now, 'yyyymmdd_HHMMSS');
                filename = sprintf('mtw_log_%s.csv', timestamp);
            end
            
            % Close any existing file
            if ~isempty(fileHandle) && fileHandle ~= -1
                fclose(fileHandle);
            end
            
            % Open new file
            fileHandle = fopen(filename, 'w', 'n', 'UTF-8');
            if fileHandle == -1
                error('Cannot open file %s for writing', filename);
            end
            
            currentFilename = filename;
            headerWritten = false;
            isInitialized = true;
            
            fprintf('MTw data logging initialized: %s\n', filename);
            
            % Write header
            header = 'device_id,packet_counter,roll,pitch,yaw,q_w,q_x,q_y,q_z,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,free_acc_x,free_acc_y,free_acc_z,status';
            fprintf(fileHandle, '%s\n', header);
            headerWritten = true;
            
        case 'log'
            % Log data point
            if ~isInitialized || isempty(fileHandle) || fileHandle == -1
                error('Logging not initialized. Call log_utils(''init'') first.');
            end
            
            if nargin < 10
                error('Insufficient arguments for logging. Need: deviceId, packetCounter, eulerAngles, quat, acc, gyr, mag, freeAcc, status');
            end
            
            deviceId = varargin{1};
            packetCounter = varargin{2};
            eulerAngles = varargin{3};
            quat = varargin{4};
            acc = varargin{5};
            gyr = varargin{6};
            mag = varargin{7};
            freeAcc = varargin{8};
            status = varargin{9};
            
            % Write data row
            fprintf(fileHandle, '%s,%u,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%u\n', ...
                deviceId, packetCounter, ...
                eulerAngles(1), eulerAngles(2), eulerAngles(3), ...
                quat(1), quat(2), quat(3), quat(4), ...
                acc(1), acc(2), acc(3), ...
                gyr(1), gyr(2), gyr(3), ...
                mag(1), mag(2), mag(3), ...
                freeAcc(1), freeAcc(2), freeAcc(3), ...
                status);
            
        case 'close'
            % Close log file
            if ~isempty(fileHandle) && fileHandle ~= -1
                fclose(fileHandle);
                fprintf('MTw data logging closed: %s\n', currentFilename);
            end
            
            % Clear persistent variables
            fileHandle = [];
            headerWritten = [];
            currentFilename = [];
            isInitialized = false;
            
        case 'get_filename'
            % Return current filename
            if nargout > 0
                varargout{1} = currentFilename;
            end
            
        otherwise
            error('Unknown action: %s. Valid actions are: init, log, close, get_filename', action);
    end
end