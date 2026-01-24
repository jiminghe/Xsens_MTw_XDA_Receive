# MIT License
# -----------
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice
# and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS",
# WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE,
# ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# -----------
# Description: This script is used to receive data from Xsens MTw Awinda wireless motion trackers.
# Author: Bryan He



import sys
import os #for ubuntu only
import time
from collections import deque
from threading import Lock
import signal
import atexit
import logging
import copy

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('xsens_debug.log'),
        logging.StreamHandler()
    ]
)

#---------Ubuntu may need to set up the pacakge location for XDA and keyboard-----#
#module_path = "/home/<yourusername>/.local/lib/python3.8/site-packages/"
#sys.path.insert(0, module_path)
#import xsensdeviceapi.xsensdeviceapi_py38_64 as xda
#---------------------------------------------------------------------------------#
import xsensdeviceapi as xda #for windows only
import keyboard

#remove the added path after importing(optional)
#sys.path.pop(0)


def get_high_accuracy_timestamp_datetime():
    """
    Get the most accurate timestamp as a datetime object.
    Converts from time.time_ns() to preserve maximum precision.
    
    Returns:
        datetime: Timezone-aware datetime with microsecond precision
    """
    from datetime import datetime, timezone, timedelta
    
    nanoseconds = time.time_ns()
    microseconds = nanoseconds // 1000
    
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return epoch + timedelta(microseconds=microseconds)


def get_high_accuracy_timestamp():
    """
    Get the most accurate timestamp as a float (seconds since epoch).
    Uses time.time_ns() for nanosecond precision.
    
    Returns:
        float: Timestamp in seconds with nanosecond precision
    """
    return time.time_ns() / 1_000_000_000.0


class TimestampManager:
    """
    Manages timestamp computation based on packet counter and data rate.
    Handles packet counter wraparound and missing packets.
    """
    
    def __init__(self, data_rate):
        """
        Initialize timestamp manager.
        
        Args:
            data_rate: Data rate in Hz (e.g., 80 for 80Hz)
        """
        self.data_rate = data_rate
        self.dt = 1.0 / data_rate  # Time between packets in seconds
        
        self.first_timestamp = None
        self.first_packet_counter = None
        self.last_packet_counter = None
        
        # uint32 max value for wraparound detection
        self.UINT32_MAX = 0xFFFFFFFF
        
    def get_timestamp(self, packet_counter, pc_timestamp=None):
        """
        Get computed timestamp for a packet.
        
        Args:
            packet_counter: Current packet counter (uint32)
            pc_timestamp: PC timestamp when packet was received (optional, used for first packet)
            
        Returns:
            float: Computed timestamp in seconds since epoch
        """
        # First packet - initialize
        if self.first_timestamp is None:
            if pc_timestamp is None:
                pc_timestamp = get_high_accuracy_timestamp()
            
            self.first_timestamp = pc_timestamp
            self.first_packet_counter = packet_counter
            self.last_packet_counter = packet_counter
            
            return self.first_timestamp
        
        # Compute packet counter difference, handling wraparound
        counter_diff = self._compute_counter_diff(packet_counter, self.first_packet_counter)
        
        # Computed timestamp = first_timestamp + (counter_diff * dt)
        computed_timestamp = self.first_timestamp + (counter_diff * self.dt)
        
        # Update last packet counter
        self.last_packet_counter = packet_counter
        
        return computed_timestamp
    
    def _compute_counter_diff(self, current_counter, reference_counter):
        """
        Compute difference between two packet counters, handling uint32 wraparound.
        
        Args:
            current_counter: Current packet counter
            reference_counter: Reference packet counter
            
        Returns:
            int: Number of packets between reference and current
        """
        if current_counter >= reference_counter:
            # Normal case - no wraparound
            return current_counter - reference_counter
        else:
            # Wraparound occurred
            # From reference to UINT32_MAX, then from 0 to current
            return (self.UINT32_MAX - reference_counter + 1) + current_counter
    
    def reset(self):
        """Reset the timestamp manager."""
        self.first_timestamp = None
        self.first_packet_counter = None
        self.last_packet_counter = None



class XsPortInfoStr:
    def __str__(self, p):
        return f"Port: {p.portNumber():>2} ({p.portName()}) @ {p.baudrate():>7} Bd, ID: {p.deviceId().toString()}"

class XsDeviceStr:
    def __str__(self, d):
        return f"ID: {d.deviceId().toString()} ({d.productCode()})"

def find_closest_update_rate(supported_update_rates, desired_update_rate):
    if not supported_update_rates:
        return 0

    if len(supported_update_rates) == 1:
        return supported_update_rates[0]

    closest_update_rate = min(supported_update_rates, key=lambda x: abs(x - desired_update_rate))
    return closest_update_rate

class WirelessMasterCallback(xda.XsCallback):
    def __init__(self):
        super().__init__()
        self.m_connectedMTWs = set()
        self.m_mutex = Lock()

    def getWirelessMTWs(self):
        with self.m_mutex:
            return self.m_connectedMTWs.copy()

    def onConnectivityChanged(self, dev, newState):
        try:
            with self.m_mutex:
                if newState == xda.XCS_Disconnected:
                    logging.info(f"EVENT: MTW Disconnected -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
                elif newState == xda.XCS_Rejected:
                    logging.info(f"EVENT: MTW Rejected -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
                elif newState == xda.XCS_PluggedIn:
                    logging.info(f"EVENT: MTW PluggedIn -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
                elif newState == xda.XCS_Wireless:
                    logging.info(f"EVENT: MTW Connected -> {dev.deviceId()}")
                    self.m_connectedMTWs.add(dev)
                elif newState == xda.XCS_File:
                    logging.info(f"EVENT: MTW File -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
                elif newState == xda.XCS_Unknown:
                    logging.info(f"EVENT: MTW Unknown -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
                else:
                    logging.info(f"EVENT: MTW Error -> {dev.deviceId()}")
                    self.m_connectedMTWs.discard(dev)
        except Exception as e:
            logging.error(f"Error in onConnectivityChanged: {e}", exc_info=True)

class MtwCallback(xda.XsCallback):
    def __init__(self, mtwIndex, device):
        super().__init__()
        self.m_packetBuffer = deque(maxlen=300)
        self.m_mutex = Lock()
        self.m_mtwIndex = mtwIndex
        self.m_device = device
        self.packet_count = 0

    def dataAvailable(self):
        try:
            with self.m_mutex:
                return bool(self.m_packetBuffer)
        except Exception as e:
            logging.error(f"Error in dataAvailable: {e}", exc_info=True)
            return False

    def getOldestPacket(self):
        try:
            with self.m_mutex:
                if len(self.m_packetBuffer) > 0:
                    packet = self.m_packetBuffer[0]
                    return packet
                return None
        except Exception as e:
            logging.error(f"Error in getOldestPacket: {e}", exc_info=True)
            return None

    def deleteOldestPacket(self):
        try:
            with self.m_mutex:
                if len(self.m_packetBuffer) > 0:
                    self.m_packetBuffer.popleft()
        except Exception as e:
            logging.error(f"Error in deleteOldestPacket: {e}", exc_info=True)

    def getMtwIndex(self):
        return self.m_mtwIndex

    def device(self):
        assert self.m_device is not None
        return self.m_device

    def onLiveDataAvailable(self, _, packet):
        try:
            with self.m_mutex:
                # NOTE: Processing of packets should not be done in this thread.
                self.m_packetBuffer.append(packet)
                self.packet_count += 1
                if len(self.m_packetBuffer) > 300:
                    self.deleteOldestPacket()
        except Exception as e:
            logging.error(f"Error in onLiveDataAvailable: {e}", exc_info=True)


def collect_sensor_data(mtw_callbacks, data_rate):
    """
    Main data collection loop - runs until CTRL+C
    
    Args:
        mtw_callbacks: List of MtwCallback objects
        data_rate: Data rate in Hz (e.g., 80 for 80Hz)
    """
    logging.info("\nMain loop. Press CTRL+C to quit\n")
    logging.info("Waiting for data available...")

    # Create timestamp managers for each sensor
    timestamp_managers = [TimestampManager(data_rate) for _ in range(len(mtw_callbacks))]

    # Store as simple Python values to avoid object reference issues
    # This approach is safer than holding C++ object references
    sensor_data = []
    for i in range(len(mtw_callbacks)):
        sensor_data.append({
            'device_id': str(mtw_callbacks[i].device().deviceId()),
            'timestamp': 0.0,
            'packet_counter': 0,
            'roll': 0.0,
            'pitch': 0.0,
            'yaw': 0.0,
            'gyr_x': 0.0,
            'gyr_y': 0.0,
            'gyr_z': 0.0,
            'acc_x': 0.0,
            'acc_y': 0.0,
            'acc_z': 0.0,
            'mag_x': 0.0,
            'mag_y': 0.0,
            'mag_z': 0.0,
            'status': 0
        })
    
    print_counter = 0
    loop_counter = 0
    
    # Main loop - runs until CTRL+C
    while True:
        try:
            loop_counter += 1
            if loop_counter % 1000 == 0:
                logging.debug(f"Loop iteration: {loop_counter}")
            
            time.sleep(0.001)  # Small sleep to prevent 100% CPU usage

            new_data_available = False
            
            for i in range(len(mtw_callbacks)):
                try:
                    if mtw_callbacks[i].dataAvailable():
                        new_data_available = True
                        packet = mtw_callbacks[i].getOldestPacket()
                        if packet is not None:
                            try:
                                # Capture PC timestamp when packet is received
                                pc_timestamp = get_high_accuracy_timestamp()
                                
                                # CRITICAL: Extract data immediately like in the reference code
                                # Get the euler object temporarily
                                euler = packet.orientationEuler()
                                
                                # Immediately extract values as Python primitives
                                # This prevents holding references to C++ objects
                                packet_counter = packet.packetCounter()
                                roll = euler.x()
                                pitch = euler.y()
                                yaw = euler.z()
                                
                                # Compute timestamp based on packet counter and data rate
                                computed_timestamp = timestamp_managers[i].get_timestamp(
                                    packet_counter, pc_timestamp
                                )
                                
                                # Store timestamp and euler angles as Python types
                                sensor_data[i]['timestamp'] = float(computed_timestamp)
                                sensor_data[i]['packet_counter'] = int(packet_counter)
                                sensor_data[i]['roll'] = float(roll)
                                sensor_data[i]['pitch'] = float(pitch)
                                sensor_data[i]['yaw'] = float(yaw)
                                
                                # Extract gyroscope data (calibrated)
                                if packet.containsCalibratedGyroscopeData():
                                    gyr = packet.calibratedGyroscopeData()
                                    sensor_data[i]['gyr_x'] = float(gyr[0])
                                    sensor_data[i]['gyr_y'] = float(gyr[1])
                                    sensor_data[i]['gyr_z'] = float(gyr[2])
                                
                                # Extract accelerometer data (calibrated)
                                if packet.containsCalibratedAcceleration():
                                    acc = packet.calibratedAcceleration()
                                    sensor_data[i]['acc_x'] = float(acc[0])
                                    sensor_data[i]['acc_y'] = float(acc[1])
                                    sensor_data[i]['acc_z'] = float(acc[2])
                                
                                # Extract magnetometer data (calibrated)
                                if packet.containsCalibratedMagneticField():
                                    mag = packet.calibratedMagneticField()
                                    sensor_data[i]['mag_x'] = float(mag[0])
                                    sensor_data[i]['mag_y'] = float(mag[1])
                                    sensor_data[i]['mag_z'] = float(mag[2])
                                
                                # Extract status word
                                if packet.containsStatus():
                                    status = packet.status()
                                    sensor_data[i]['status'] = int(status)
                                
                            except Exception as e:
                                logging.error(f"Error extracting data from packet {i}: {e}", exc_info=True)
                            
                            # Delete packet immediately after processing
                            mtw_callbacks[i].deleteOldestPacket()
                        else:
                            logging.warning(f"Received None packet from callback {i}")
                except Exception as e:
                    logging.error(f"Error processing callback {i}: {e}", exc_info=True)

            if new_data_available:
                # print only 1/x of the data in the screen.
                if print_counter % 1 == 0:
                    try:
                        for i in range(len(mtw_callbacks)):
                            data = sensor_data[i]
                            print(f"[{i}]: ID: {data['device_id']}, "
                                f"Time: {data['timestamp']:.5f}, "
                                f"Pkt: {data['packet_counter']:5d}, "
                                f"Status: 0x{data['status']:08X}, "
                                f"Gyr: [{data['gyr_x']:7.2f}, {data['gyr_y']:7.2f}, {data['gyr_z']:7.2f}], "
                                f"Acc: [{data['acc_x']:7.2f}, {data['acc_y']:7.2f}, {data['acc_z']:7.2f}], "
                                f"Mag: [{data['mag_x']:7.2f}, {data['mag_y']:7.2f}, {data['mag_z']:7.2f}], "
                                f"Euler: [{data['roll']:7.2f}, {data['pitch']:7.2f}, {data['yaw']:7.2f}]")
                    except Exception as e:
                        logging.error(f"Error printing data: {e}", exc_info=True)
            
                print_counter += 1
                
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt detected in main loop. Exiting...")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(0.1)  # Pause briefly before continuing


# Global variable for cleanup
control_global = None
wireless_master_device_global = None
cleanup_done = False

def cleanup():
    """Cleanup function to be called on exit"""
    global cleanup_done
    
    if cleanup_done:
        logging.info("Cleanup already performed, skipping...")
        return
    
    cleanup_done = True
    logging.info("Cleanup function called")
    
    try:
        if wireless_master_device_global is not None:
            logging.info("Setting config mode in cleanup...")
            try:
                wireless_master_device_global.gotoConfig()
            except Exception as e:
                logging.debug(f"Error in gotoConfig: {e}")
            
            logging.info("Disabling radio in cleanup...")
            try:
                wireless_master_device_global.disableRadio()
            except Exception as e:
                logging.debug(f"Error in disableRadio: {e}")
        
        if control_global is not None:
            logging.info("Closing XsControl in cleanup...")
            try:
                control_global.close()
            except Exception as e:
                logging.debug(f"Error in close: {e}")
    except Exception as e:
        logging.error(f"Error during cleanup: {e}", exc_info=True)

def signal_handler(sig, frame):
    """Handle CTRL+C"""
    global cleanup_done
    
    logging.info(f"Signal {sig} received")
    print("\n\nInterrupt received, cleaning up...")
    
    cleanup()
    
    logging.info("Cleanup complete. Exiting.")
    print("Cleanup complete. Exiting.")
    
    # Exit immediately without calling atexit handlers again
    os._exit(0)

# Register cleanup and signal handlers
atexit.register(cleanup)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == '__main__':
    desired_update_rate = 75
    desired_radio_channel = 19

    wireless_master_callback = WirelessMasterCallback()
    mtw_callbacks = []

    logging.info("Constructing XsControl...")
    control = xda.XsControl.construct()
    control_global = control
    
    if control is None:
        logging.error("Failed to construct XsControl instance.")
        sys.exit(1)

    try:
        logging.info("Scanning ports...")

        detected_devices = xda.XsScanner_scanPorts()

        logging.info("Finding wireless master...")
        wireless_master_port = next((port for port in detected_devices if port.deviceId().isWirelessMaster()), None)
        if wireless_master_port is None:
            raise RuntimeError("No wireless masters found")

        logging.info(f"Wireless master found @ {wireless_master_port}")

        logging.info("Opening port...")
        if not control.openPort(wireless_master_port.portName(), wireless_master_port.baudrate()):
            raise RuntimeError(f"Failed to open port {wireless_master_port}")

        logging.info("Getting XsDevice instance for wireless master...")
        wireless_master_device = control.device(wireless_master_port.deviceId())
        wireless_master_device_global = wireless_master_device
        
        if wireless_master_device is None:
            raise RuntimeError(f"Failed to construct XsDevice instance: {wireless_master_port}")

        logging.info(f"XsDevice instance created @ {wireless_master_device}")

        logging.info("Setting config mode...")
        if not wireless_master_device.gotoConfig():
            raise RuntimeError(f"Failed to goto config mode: {wireless_master_device}")

        logging.info("Attaching callback handler...")
        wireless_master_device.addCallbackHandler(wireless_master_callback)

        logging.info("Getting the list of the supported update rates...")
        supportUpdateRates = xda.XsDevice.supportedUpdateRates(wireless_master_device, xda.XDI_None)

        logging.info(f"Supported update rates: {supportUpdateRates}")

        new_update_rate = find_closest_update_rate(supportUpdateRates, desired_update_rate)

        logging.info(f"Setting update rate to {new_update_rate} Hz...")

        if not wireless_master_device.setUpdateRate(new_update_rate):
            raise RuntimeError(f"Failed to set update rate: {wireless_master_device}")
        
        # Store the actual update rate for timestamp computation
        actual_data_rate = new_update_rate

        logging.info("Disabling radio channel if previously enabled...")

        if wireless_master_device.isRadioEnabled():
            if not wireless_master_device.disableRadio():
                raise RuntimeError(f"Failed to disable radio channel: {wireless_master_device}")

        logging.info(f"Setting radio channel to {desired_radio_channel} and enabling radio...")
        if not wireless_master_device.enableRadio(desired_radio_channel):
            raise RuntimeError(f"Failed to set radio channel: {wireless_master_device}")

        logging.info("Waiting for MTW to wirelessly connect...\n")


        wait_for_connections = True
        connected_mtw_count = len(wireless_master_callback.getWirelessMTWs())
        while wait_for_connections:
            time.sleep(0.1)
            next_count = len(wireless_master_callback.getWirelessMTWs())
            if next_count != connected_mtw_count:
                logging.info(f"Number of connected MTWs: {next_count}. Press 'Y' to start measurement.")
                connected_mtw_count = next_count

            wait_for_connections = not keyboard.is_pressed('y')



        logging.info("Starting measurement...")
        if not wireless_master_device.gotoMeasurement():
            raise RuntimeError(f"Failed to goto measurement mode: {wireless_master_device}")

        logging.info("Getting XsDevice instances for all MTWs...")
        all_device_ids = control.deviceIds()
        mtw_device_ids = [device_id for device_id in all_device_ids if device_id.isMtw()]
        mtw_devices = []
        for device_id in mtw_device_ids:
            mtw_device = control.device(device_id)
            if mtw_device is not None:
                mtw_devices.append(mtw_device)
            else:
                raise RuntimeError("Failed to create an MTW XsDevice instance")

        logging.info("Attaching callback handlers to MTWs...")
        mtw_callbacks = [MtwCallback(i, mtw_devices[i]) for i in range(len(mtw_devices))]
        for i in range(len(mtw_devices)):
            mtw_devices[i].addCallbackHandler(mtw_callbacks[i])

        logging.info("Creating a log file...")
        logFileName = "logfile.mtb"
        if wireless_master_device.createLogFile(logFileName) != xda.XRV_OK:
            raise RuntimeError("Failed to create a log file. Aborting.")
        else:
            logging.info("Created a log file: %s" % logFileName)

        logging.info("Starting recording...")
        ready_to_record = False

        while not ready_to_record:
            ready_to_record = all([mtw_callbacks[i].dataAvailable() for i in range(len(mtw_callbacks))])
            if not ready_to_record:
                logging.info("Waiting for data available...")
                time.sleep(0.5)

        if not wireless_master_device.startRecording():
            raise RuntimeError("Failed to start recording. Aborting.")

        # Start the main data collection loop
        collect_sensor_data(mtw_callbacks, actual_data_rate)

        logging.info("Exited main loop")
        logging.info("Setting config mode...")
        try:
            if not wireless_master_device.gotoConfig():
                logging.error("Failed to goto config mode")
        except Exception as e:
            logging.error(f"Error in gotoConfig: {e}")

        logging.info("Disabling radio...")
        try:
            if not wireless_master_device.disableRadio():
                logging.error("Failed to disable radio")
        except Exception as e:
            logging.error(f"Error in disableRadio: {e}")

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected in main try block.")
        print("\n****ABORT****")
    except Exception as ex:
        logging.error(f"Exception: {ex}", exc_info=True)
        print("****ABORT****")
    finally:
        # Perform cleanup if not already done
        if not cleanup_done:
            logging.info("Performing final cleanup...")
            
            logging.info("Closing XsControl...")
            try:
                control.close()
            except Exception as e:
                logging.error(f"Error closing control: {e}")

    if not cleanup_done:
        logging.info("Successful exit.")
        print("Press [ENTER] to continue.")
        input()