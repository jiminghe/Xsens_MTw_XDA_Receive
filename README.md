# Xsens MTw XDA Receive(Matlab)

A MATLAB-based real-time data acquisition and logging system for Xsens MTw wireless inertial measurement units (IMUs) connected through Awinda station or dongle.

## Overview

This repository provides a complete solution for:
- Real-time streaming of MTw sensor data
- Live data visualization in MATLAB console
- Automatic CSV logging of all sensor measurements
- Support for multiple MTw devices simultaneously


## System Requirements

### Hardware
- Xsens MTw wireless IMU devices
- Xsens Awinda station or Awinda dongle
- Windows PC (32-bit or 64-bit)

### Software
- MATLAB (32-bit or 64-bit)
- Xsens MT SDK installed and registered
- Required DLL files:
  - `xsensdeviceapi_com32.dll` (for 32-bit MATLAB)
  - `xsensdeviceapi_com64.dll` (for 64-bit MATLAB)

## Installation

1. **Install Xsens MT SDK**
   - Download and install the Xsens MT SDK from the official Xsens website
   - The installation process will automatically register the required DLL files

2. **Clone or download this repository**
   ```bash
   git clone --branch matlab https://github.com/jiminghe/Xsens_MTw_XDA_Receive.git
   cd Xsens_MTw_XDA_Receive
   ```

3. **Verify MATLAB setup**
   - Ensure MATLAB can access the Xsens COM objects
   - The code automatically detects 32-bit vs 64-bit MATLAB

## File Structure

```
Xsens_MTw_XDA_Receive/
├── receive_mtw_data.m        # Main script for data acquisition
├── log_utils.m               # Utility functions for CSV logging
└── README.md                 # This file
```

## Usage

### Quick Start

1. **Connect your hardware**:
   - Connect Awinda station/dongle to USB port


2. **Set MATLAB working directory**:
   ```matlab
   cd('path/to/Xsens_MTw_XDA_Receive')
   ```

3. **Run the main script**:
   ```matlab
   receive_mtw_data
   ```

4. **Follow the interactive prompts**:
   - Select update rate from supported options
   - Choose radio channel (for wireless mode)
   - Undock MTw devices when prompted (wireless mode)
   - Accept/reject connected devices
   - Press Enter to stop data collection

### Step-by-Step Process

#### Part 1: Device Setup (Wireless Mode)
1. Script scans for connected devices
2. Displays found Awinda station/dongle information
3. Prompts for update rate selection
4. Prompts for radio channel selection
5. Enables radio communication
6. User undocks MTw devices from station
7. Script detects wirelessly connected devices
8. User can accept/reject individual devices

#### Part 2: Data Acquisition
1. Devices enter measurement mode
2. Real-time data streaming begins
3. Data automatically logged to CSV file
4. Live data displayed in console (optional)
5. User presses Enter to stop acquisition
6. System cleanly shuts down and closes files

### Data Output

Each run generates a single CSV file named: `mtw_log_YYYYMMDD_HHMMSS.csv`

**CSV columns include**:
- `device_id`: Unique device identifier
- `packet_counter`: Sequential packet number
- `roll`, `pitch`, `yaw`: Euler angles (degrees)
- `q_w`, `q_x`, `q_y`, `q_z`: Quaternion components
- `acc_x`, `acc_y`, `acc_z`: Calibrated acceleration (m/s²)
- `gyr_x`, `gyr_y`, `gyr_z`: Calibrated gyroscope (deg/s)
- `mag_x`, `mag_y`, `mag_z`: Calibrated magnetometer (a.u.)
- `free_acc_x`, `free_acc_y`, `free_acc_z`: Free acceleration (m/s²)
- `status`: Device status code

## Configuration Options

### Update Rates
Common supported rates include: 40, 60, 80, 100, 120 Hz

### Radio Channels
Available channels: 11-25
Choose a channel with minimal interference in your environment.

### Performance Tips

- Use lower update rates for multiple devices
- Close unnecessary applications to reduce interference
- Position Awinda station away from WiFi routers
- Ensure MTw devices are within 20m range of station

## API Reference

### log_utils.m Functions

```matlab
% Initialize logging
log_utils('init')                    % Auto-generated filename
log_utils('init', 'custom_name.csv') % Custom filename

% Log data point
log_utils('log', deviceId, packetCounter, eulerAngles, quat, acc, gyr, mag, freeAcc, status)

% Close log file
log_utils('close')

% Get current filename
filename = log_utils('get_filename')
```