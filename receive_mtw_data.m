function mainMTwRTdataViewer
%%------- HELP
%
% This script allows the user to understand the step-wise procedure to get data from devices connected to
% the Awinda station in wireless mode and collect data. It is also possible
% to use this example with a wired connected MTw device.
%
% The code is divided into two parts:
%
% 1) The first part regards the situation in which the MTw are docked to
% the Awinda station. In this part:
%
%           a) information about the MTw connected are provided
%           b) a communication channel is opened making the Awinda station
%           enabled to receive MTw connections (the user is asked to choose
%           the channel number)
%           c) at this point the user is asked to undock the MTw devices from the
%           Awinda station and wait for them to be wireless connected
%
% 2) The second part regards the situation of using the MTw in wireless
% mode, soon after the end of the part 1.
%
%           a) operational mode is activated
%           b) the user is asked to choose a specific update rate (this might depend on the number of MTw used. See
%           datasheet for this information)
%           c) measurement mode is activated
%           d) data are extracted from the devices and displayed in real-time
%           e) Awinda station is then disabled
%
%%-------- IMPORTANT NOTES
%
% - For the code to work properly, make sure the code folder is your current directory in Matlab.
%
% - This code supports multiple MTw devices connected at a time to one Awinda station (although the suggested max number of connected devices is 4).
%
% - This code supports both 32 and 64 bits Matlab version.
%
% - The code requires xsensdeviceapi_com32.dll or xsensdeviceapi_com64.dll to be registered in the Windows
%   register (this is done automatically during the Xsens MT SDK installation)
%

%% Launching activex server
switch computer
	case 'PCWIN'
		serverName = 'xsensdeviceapi_com32.IXsensDeviceApi';
	case 'PCWIN64'
		serverName = 'xsensdeviceapi_com64.IXsensDeviceApi';
end
h = actxserver(serverName);
fprintf( '\n ActiveXsens server - activated \n' );

version = h.xdaVersion;
fprintf(' XDA version: %.0f.%.0f.%.0f\n',version{1:3})
if length(version)>3
	fprintf(' XDA build: %.0f %s\n',version{4:5});
end

%% Scanning connection ports
% ports rescanned must be reopened
p_br = h.XsScanner_scanPorts(0, 100, true, true);
fprintf( '\n Connection ports - scanned \n' );

% check using device id's what kind of devices are connected.
isMtw = cellfun(@(x) h.XsDeviceId_isMtw(x),p_br(:,1));
isDongle = cellfun(@(x) h.XsDeviceId_isAwindaXDongle(x),p_br(:,1));
isStation = cellfun(@(x) h.XsDeviceId_isAwindaXStation(x),p_br(:,1));
isWirelessMaster = cellfun(@(x) h.XsDeviceId_isWirelessMaster(x),p_br(:,1));

if any(isDongle|isStation|isWirelessMaster)
	fprintf('\n Found wireless master device\n')
	dev = find(isDongle|isStation|isWirelessMaster);
	isMtw = false; % if a station or a dongle is connected give priority to it.
elseif any(isMtw)
	fprintf('\n Example MTw\n')
	dev = find(isMtw);
else
	fprintf('\n No device found. \n')
	h.XsControl_close();
	delete(h);
	return
end

% port scan gives back information about the device, use first device found.
deviceID = p_br{dev(1),1};
portS = p_br{dev(1),3};
baudRate = p_br{dev(1),4};

devTypeStr = '';
if any(isMtw)
	devTypeStr = 'MTw';
elseif any(isDongle)
	devTypeStr = 'dongle';
elseif any(isStation)
	devTypeStr = 'station';
else
	devTypeStr = 'wireless master';
end
fprintf('\n Found %s on port %s, with ID: %s and baudRate: %.0f \n',devTypeStr, portS, dec2hex(h.XsDeviceId_toInt(deviceID)), baudRate);

% call log function.
log_utils('init');

% open port
if ~h.XsControl_openPort(portS, baudRate, 0 ,true)
	fprintf('\n Unable to open port %s. \n', portS);
	h.XsControl_close();
	delete(h);
	return;
end

%% Initialize Master Device
% get device handle.
device = h.XsControl_device(deviceID);

% Go to config mode first
fprintf('\n Setting config mode...\n');
if ~h.XsDevice_gotoConfig(device)
	fprintf('\n Failed to goto config mode\n');
	stopAll;
	return;
end

% To be able to get orientation data from a MTw, the filter in the
% software needs to be turned on:
h.XsDevice_setOptions(device, h.XsOption_XSO_Orientation + h.XsOption_XSO_Calibrate, 0);

% Get the list of supported update rates and let the user choose the
% one to set
supportUpdateRates = h.XsDevice_supportedUpdateRates(device, h.XsDataIdentifier_XDI_None);
upRateIndex = [];
while(isempty(upRateIndex))
	fprintf('\n The supported update rates are: ');
	fprintf('%i, ',supportUpdateRates{:});
	fprintf('\n');
	selectedUpdateRate = input(' Which update rate do you want to use ? ');
	if (isempty(selectedUpdateRate))
		continue;
	end
	upRateIndex = find([supportUpdateRates{:}] == selectedUpdateRate);
end

% set the choosen update rate
h.XsDevice_setUpdateRate(device, supportUpdateRates{upRateIndex});

if(any(isDongle|isStation|isWirelessMaster))
	% Disable radio if previously enabled (important step)
	fprintf('\n Disabling radio channel if previously enabled...\n');
	if h.XsDevice_isRadioEnabled(device)
		try
			h.XsDevice_disableRadio(device);
			pause(1); % Wait a moment for radio to disable
		catch
			fprintf(' Warning: Could not disable radio\n');
		end
	end
	
	% Let the user choose the desired radio channel
	availableRadioChannels = [11 12 13 14 15 16 17 18 19 20 21 22 23 24 25];
	upRadioChIndex = [];
	while(isempty(upRadioChIndex))
		fprintf('\n The available radio channels are: ');
		fprintf('%i, ',availableRadioChannels);
		fprintf('\n');
		selectedRadioCh = input(' Which radio channel do you want to use ? ');
		if (isempty(selectedRadioCh))
			continue;
		end
		upRadioChIndex = find(availableRadioChannels == selectedRadioCh);
	end
	
	% enable radio with selected channel
	fprintf('\n Enabling radio on channel %d...\n', availableRadioChannels(upRadioChIndex));
	try
		if ~h.XsDevice_enableRadio(device, availableRadioChannels(upRadioChIndex))
			fprintf(' Failed to enable radio\n');
			stopAll;
			return;
		end
	catch ME
		fprintf(' Error enabling radio: %s\n', ME.message);
		stopAll;
		return;
	end
	
	input('\n Undock the MTw devices from the Awinda station and wait until the devices are connected (synced leds), then press enter... \n');
	
	% Wait for wireless connections with better timeout handling
	fprintf('\n Waiting for MTw devices to connect wirelessly...\n');
	maxWaitTime = 30; % seconds
	waitStart = tic;
	connectedDevices = [];
	
	while toc(waitStart) < maxWaitTime
		% Get children devices from the master device (this is the correct approach)
		children = h.XsDevice_children(device);
		
		% Filter for wirelessly connected MTw devices
		connectedDevices = [];
		for i = 1:length(children)
			try
				% Check connectivity state first
				connState = h.XsDevice_connectivityState(children{i});
				if connState == h.XsConnectivityState_XCS_Wireless
					% Double-check it's an MTw device
					childDeviceId = h.XsDevice_deviceId(children{i});
					if h.XsDeviceId_isMtw(childDeviceId)
						connectedDevices{end+1} = children{i};
					end
				end
			catch
				% Skip devices that cause errors
				continue;
			end
		end
		
		if ~isempty(connectedDevices)
			fprintf(' Found %d wirelessly connected MTw device(s)\n', length(connectedDevices));
			break;
		end
		
		pause(0.5);
		fprintf('.');
	end
	
	if isempty(connectedDevices)
		fprintf('\n No MTw devices connected wirelessly within timeout period\n');
		stopAll;
		return;
	end
	
	% Use the connected devices
	children = connectedDevices;
	
	% Get device IDs for connected devices
	devIdAll = cell(size(children));
	for i = 1:length(children)
		devIdAll{i} = dec2hex(h.XsDeviceId_toInt(h.XsDevice_deviceId(children{i})));
	end
	
	% check connected sensors, see which are accepted and which are
	% rejected.
	[devicesUsed, devIdUsed, nDevs] = checkConnectedSensors(devIdAll, children, h);
	fprintf(' Used device: %s \n',devIdUsed{:});
else
	assert(any(isMtw))
	nDevs = 1; % only one device available
	devIdUsed = {dec2hex(h.XsDeviceId_toInt(deviceID))};
	devicesUsed = {device};
end

%% Initialize variables BEFORE event registration
% Initialize all variables that will be used in the callback
t = cell(nDevs, 1);
for i = 1:nDevs
    t{i} = [];
end

%% Entering measurement mode
fprintf('\n Activate measurement mode \n');
% goto measurement mode
output = h.XsDevice_gotoMeasurement(device);

% display radio connection information
if(any(isDongle|isStation|isWirelessMaster))
	fprintf('\n Connection has been established on channel %i with an update rate of %i Hz\n', h.XsDevice_radioChannel(device), h.XsDevice_updateRate(device));
else
	assert(any(isMtw))
	fprintf('\n Connection has been established with an update rate of %i Hz\n', h.XsDevice_updateRate(device));
end

% check filter profiles
if ~isempty(devicesUsed)
	availableProfiles = h.XsDevice_availableXdaFilterProfiles(devicesUsed{1});
	usedProfile = h.XsDevice_xdaFilterProfile(devicesUsed{1});
	number = usedProfile{1};
	version = usedProfile{2};
	name = usedProfile{3};
	fprintf('\n Used profile: %s(%.0f), version %.0f.\n',name,number,version)
	if any([availableProfiles{:,1}] ~= number)
		fprintf('\n Other available profiles are: \n')
		for iP=1:size(availableProfiles,1)
			fprintf(' Profile: %s(%.0f), version %.0f.\n',availableProfiles{iP,3},availableProfiles{iP,1},availableProfiles{iP,2})
		end
	end
end

if output
	% register onLiveDataAvailable event
	h.registerevent({'onLiveDataAvailable',@handleData});
	h.setCallbackOption(h.XsComCallbackOptions_XSC_LivePacket, h.XsComCallbackOptions_XSC_None);
	fprintf('\n Live data streaming started...\n');
	input('\n Press enter to stop measurement. \n');
	
else
	fprintf('\n Problems with going to measurement\n')
end
stopAll;

%% Event handler
	function handleData(varargin)
		try
			% callback function for event: onLiveDataAvailable
			dataPacket = varargin{3}{2};
			deviceFound = varargin{3}{1};
			
			iDev = find(cellfun(@(x) x==deviceFound, devicesUsed));
			
			if isempty(iDev)
				return;
			end
			
			if isempty(t{iDev})
				t{iDev} = 1;
			else
				t{iDev} = [t{iDev} t{iDev}(end)+1];
			end
			
			if dataPacket
				if h.XsDataPacket_containsPacketCounter(dataPacket) && ...
				h.XsDataPacket_containsOrientation(dataPacket) && ...
				h.XsDataPacket_containsCalibratedData(dataPacket) && ...
				h.XsDataPacket_containsFreeAcceleration(dataPacket)
					
					deviceId = devIdUsed{iDev};
					
					% Extract all data
					packetCounter = h.XsDataPacket_packetCounter(dataPacket);
					eulerAngles = cell2mat(h.XsDataPacket_orientationEuler_1(dataPacket));
					quat = cell2mat(h.XsDataPacket_orientationQuaternion_1(dataPacket));
					acc = cell2mat(h.XsDataPacket_calibratedAcceleration(dataPacket));
					gyr = cell2mat(h.XsDataPacket_calibratedGyroscopeData(dataPacket)) * (180/pi);
					mag = cell2mat(h.XsDataPacket_calibratedMagneticField(dataPacket));
					freeAcc = cell2mat(h.XsDataPacket_freeAcceleration(dataPacket));
					status = h.XsDataPacket_status(dataPacket);
					
					% Log data using log_utils
					log_utils('log', deviceId, packetCounter, eulerAngles, quat, acc, gyr, mag, freeAcc, status);
					
					% Display data (optional - you can comment this out if you don't want console output)
					fprintf('Device %s: ', deviceId);
					fprintf('packetCounter=%u; ', packetCounter);              
					fprintf('Roll=%.2f, Pitch=%.2f, Yaw=%.2f; ', eulerAngles(1), eulerAngles(2), eulerAngles(3));
					fprintf('QuatW=%.2f, QuatX=%.2f, QuatY=%.2f, QuatZ=%.2f; ', quat(1), quat(2), quat(3), quat(4));
					fprintf('AccX=%.2f, AccY=%.2f, AccZ=%.2f; ', acc(1), acc(2), acc(3));
					fprintf('GyrX=%.4f, GyrY=%.4f, GyrZ=%.4f; ', gyr(1), gyr(2), gyr(3));
					fprintf('MagX=%.2f, MagY=%.2f, MagZ=%.2f; ', mag(1), mag(2), mag(3));
					fprintf('FreeAccX=%.2f, FreeAccY=%.2f, FreeAccZ=%.2f; ', freeAcc(1), freeAcc(2), freeAcc(3));
					fprintf('status=%u;\n', status);    
				end
				
				h.dataPacketHandled(deviceFound, dataPacket);
			end
		catch ME
			fprintf('Error in handleData callback: %s\n', ME.message);
		end
	end

	function stopAll
		% close everything in the right way
		if ~isempty(h.eventlisteners)
			h.unregisterevent({'onLiveDataAvailable',@handleData});
			h.setCallbackOption(h.XsComCallbackOptions_XSC_None, h.XsComCallbackOptions_XSC_LivePacket);
		end
		
		% Close the CSV log file using log_utils
		log_utils('close');
		
		% stop data streaming, go to config mode
		fprintf('\n Stop data streaming, go to config mode \n');
		h.XsDevice_gotoConfig(device);
		
		% disable radio for station or dongle
		if any(isStation|isDongle|isWirelessMaster)
			fprintf('\n Disabling radio...\n');
			try
				h.XsDevice_disableRadio(device);
			catch
				fprintf(' Warning: Could not disable radio\n');
			end
		end
		
		% on close, devices go to config mode.
		fprintf('\n Close port \n');
		% close port
		h.XsControl_closePort(portS);
		% close handle
		h.XsControl_close();
		% delete handle
		delete(h);
	end

	function [devicesUsed, devIdUsed, nDevs] = checkConnectedSensors(devIdAll, children, h)
		childUsed = false(size(children));
		if isempty(children)
			fprintf('\n No devices found \n')
			stopAll
			error('MTw:example:devices','No devices found')
		else
			% check which sensors are connected
			for ic=1:length(children)
				connState = h.XsDevice_connectivityState(children{ic});
				if connState == h.XsConnectivityState_XCS_Wireless
					childUsed(ic) = true;
				end
			end
			
			% show which sensors are connected
			fprintf('\n Devices rejected:\n')
			rejects = devIdAll(~childUsed);
			for i=1:length(rejects)
				I = find(strcmp(devIdAll, rejects{i}));
				fprintf(' %d - %s\n', I, rejects{i})
			end
			fprintf('\n Devices accepted:\n')
			accepted = devIdAll(childUsed);
			for i=1:length(accepted)
				I = find(strcmp(devIdAll, accepted{i}));
				fprintf(' %d - %s\n', I, accepted{i})
			end
			
			str = input('\n Keep current status?(y/n) \n','s');
			change = [];
			if strcmp(str,'n')
				str = input('\n Type the numbers of the sensors (csv list, e.g. "1,2,3") from which status should be changed \n (if accepted than reject or the other way around):\n','s');
				change = str2double(regexp(str, ',', 'split'));
				for iR=1:length(change)
					if ~isnan(change(iR)) && change(iR) <= length(children)
						if childUsed(change(iR))
							% reject sensors
							h.XsDevice_rejectConnection(children{change(iR)});
							childUsed(change(iR)) = false;
						else
							% accept sensors
							h.XsDevice_acceptConnection(children{change(iR)});
							childUsed(change(iR)) = true;
						end
					end
				end
			end
			
			% if no device is connected, give error
			if sum(childUsed) == 0
				stopAll
				error('MTw:example:devices','No devices connected')
			end
			
			% if sensors are rejected or accepted check blinking leds again
			if ~isempty(change)
				input('\n When sensors are connected (synced leds), press enter... \n');
			end
		end
		devicesUsed = children(childUsed);
		devIdUsed = devIdAll(childUsed);
		nDevs = sum(childUsed);
	end
end