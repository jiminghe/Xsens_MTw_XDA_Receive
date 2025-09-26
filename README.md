# Xsens MTw XDA Receive(Matlab)

A MATLAB-based real-time data acquisition and logging system for Xsens MTw wireless inertial measurement units (IMUs) connected through Awinda station or dongle.

## Overview

This repository provides a complete solution for:
- Real-time streaming of MTw sensor data
- Live data visualization in MATLAB console
- Automatic CSV logging of all sensor measurements
- **Heading reset functionality for orientation reference alignment**
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
├── mainMTwRTdataViewer.m     # Main script for data acquisition
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
   mainMTwRTdataViewer
   ```

4. **Follow the interactive prompts**:
   - Select update rate from supported options
   - Choose radio channel (for wireless mode)
   - Undock MTw devices when prompted (wireless mode)
   - **Choose heading reset option (recommended for orientation alignment)**
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
7. Script detects wirelessly connected devices with timeout protection
8. Prompts for heading reset option
9. User can accept/reject individual devices

#### Part 2: Data Acquisition
1. Devices enter measurement mode
2. Real-time data streaming begins
3. **If heading reset enabled**: System waits for data flow, then performs heading reset
4. Data logging starts (after heading reset if enabled)
5. Live data displayed in console (optional)
6. User presses Enter to stop acquisition
7. System cleanly shuts down and closes files

### Heading Reset Feature

The heading reset functionality allows you to set a common reference direction for all MTw devices:

#### When to Use Heading Reset
- **Recommended**: When you need consistent orientation reference across multiple devices
- **Essential**: For applications requiring synchronized heading measurements
- **Useful**: When devices are physically aligned in the same direction

#### How It Works
1. **Alignment**: Physically align all MTw devices in the desired reference direction
2. **Selection**: Choose "y" when prompted "Do you want to do heading reset?"
3. **Automatic execution**: After data streaming starts, the system:
   - Waits for stable data flow from all devices
   - Performs heading reset on each device simultaneously
   - Sets current heading as the new zero reference (yaw ≈ 0°)
4. **Data integrity**: Pre-reset data is not logged to ensure all recorded data uses the correct reference

#### Important Notes
- **Physical alignment required**: All sensors must be physically oriented in the same direction before reset
- **Timing**: Reset occurs automatically after data streaming stabilizes
- **Data logging**: Only post-reset data is logged when heading reset is enabled
- **Multiple devices**: All connected devices are reset simultaneously for synchronization

### Data Output

Each run generates a single CSV file named: `mtw_log_YYYYMMDD_HHMMSS.csv`

**CSV columns include**:
- `device_id`: Unique device identifier
- `packet_counter`: Sequential packet number
- `roll`, `pitch`, `yaw`: Euler angles (degrees) - **yaw starts from ~0° if heading reset used**
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

### Heading Reset Options
- **Yes**: Enables heading reset for synchronized orientation reference
- **No**: Uses default device orientation (may vary between devices)

### Performance Tips

- Use lower update rates for multiple devices
- Close unnecessary applications to reduce interference
- Position Awinda station away from WiFi routers
- Ensure MTw devices are within 20m range of station
- **For heading reset**: Ensure all devices are physically aligned before starting

## Troubleshooting

### Common Issues

**Heading reset doesn't work**:
- Ensure devices are sending data before reset attempt
- Check that all devices are physically aligned in the same direction
- Verify devices are in measurement mode and data is flowing

**Device connection failures**:
- Check radio channel interference
- Verify MTw devices are properly undocked
- Ensure devices are within communication range

**Data logging issues**:
- Verify write permissions in the working directory
- Check available disk space
- Ensure `log_utils.m` is in the MATLAB path

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

### Heading Reset Implementation

The heading reset functionality uses the Xsens XDA API:
```matlab
h.XsDevice_resetOrientation(device, h.XsResetMethod_XRM_Heading)
```

This command resets only the heading (yaw) component while preserving roll and pitch measurements based on gravity and magnetic field references.