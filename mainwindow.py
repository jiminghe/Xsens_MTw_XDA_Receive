"""
Main application window logic
Coordinates XDA, callbacks, and data collection
"""

import os
import csv
import time
import logging
import signal
import atexit
from datetime import datetime

import xsensdeviceapi as xda
import keyboard

from myxda import MyXda
from callbacks import WirelessMasterCallback, MtwCallback
from connected_mtw_data import ConnectedMTwData
from timestamp_manager import TimestampManager, get_high_accuracy_timestamp
from duplicate_filter import DuplicatePacketFilter


class State:
    """Application state machine (similar to C++ enum)"""
    DETECTING = "DETECTING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ENABLED = "ENABLED"
    OPERATIONAL = "OPERATIONAL"
    AWAIT_MEASUREMENT_START = "AWAIT_MEASUREMENT_START"
    MEASURING = "MEASURING"
    AWAIT_RECORDING_START = "AWAIT_RECORDING_START"
    RECORDING = "RECORDING"
    FLUSHING = "FLUSHING"


class MainWindow:
    """
    Main application class
    Manages the overall application flow and state machine
    """
    
    def __init__(self, desired_update_rate=60, desired_radio_channel=11):
        """
        Initialize MainWindow
        
        Args:
            desired_update_rate: Desired update rate in Hz
            desired_radio_channel: Radio channel (11-25)
        """
        self.desired_update_rate = desired_update_rate
        self.desired_radio_channel = desired_radio_channel
        self.actual_data_rate = desired_update_rate
        
        # State
        self.state = State.DETECTING
        
        # XDA components
        self.my_xda = None
        self.wireless_master_callback = None
        self.wireless_master_device = None
        self.mtw_callbacks = []
        
        # Data management
        self.sensor_data = []
        self.timestamp_managers = []
        self.duplicate_filter = None
        
        # File handles
        self.csv_file = None
        self.csv_writer = None
        
        # Cleanup flag
        self.cleanup_done = False
        
        # Register cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle CTRL+C interrupt"""
        logging.info(f"Signal {sig} received")
        print("\n\nInterrupt received, cleaning up...")
        self.cleanup()
        logging.info("Cleanup complete. Exiting.")
        print("Cleanup complete. Exiting.")
        os._exit(0)
    
    def cleanup(self):
        """Cleanup resources on exit"""
        if self.cleanup_done:
            logging.info("Cleanup already performed, skipping...")
            return
        
        self.cleanup_done = True
        logging.info("Cleanup function called")
        
        try:
            # Close CSV file
            if self.csv_file is not None:
                logging.info("Closing CSV file...")
                self.csv_file.close()
            
            # Stop wireless master
            if self.wireless_master_device is not None:
                logging.info("Setting config mode...")
                try:
                    self.wireless_master_device.gotoConfig()
                except Exception as e:
                    logging.debug(f"Error in gotoConfig: {e}")
                
                logging.info("Disabling radio...")
                try:
                    self.wireless_master_device.disableRadio()
                except Exception as e:
                    logging.debug(f"Error in disableRadio: {e}")
            
            # Close XDA
            if self.my_xda is not None:
                logging.info("Closing XDA...")
                try:
                    self.my_xda.reset()
                except Exception as e:
                    logging.debug(f"Error in reset: {e}")
        
        except Exception as e:
            logging.error(f"Error during cleanup: {e}", exc_info=True)
    
    def find_closest_update_rate(self, supported_rates, desired_rate):
        """Find closest supported update rate to desired rate"""
        if not supported_rates:
            return 0
        if len(supported_rates) == 1:
            return supported_rates[0]
        return min(supported_rates, key=lambda x: abs(x - desired_rate))
    
    def generate_log_filename(self, station_id):
        """
        Generate log filename based on station ID and timestamp
        Format: STATIONID_YYMMDD_HHMMSS
        """
        now = datetime.now()
        timestamp_str = now.strftime("%y%m%d_%H%M%S")
        return f"{station_id}_{timestamp_str}"
    
    def create_csv_file(self, csv_filename):
        """Create CSV file with header"""
        self.csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file, delimiter=',')
        
        # Write CSV header
        header = [
            'Sensor_ID', 'Time', 'PacketCounter', 'Status',
            'Gyro_X(rad/s)', 'Gyro_Y(rad/s)', 'Gyro_Z(rad/s)',
            'Acc_X(m/s^2)', 'Acc_Y(m/s^2)', 'Acc_Z(m/s^2)',
            'Mag_X', 'Mag_Y', 'Mag_Z',
            'Roll(deg)', 'Pitch(deg)', 'Yaw(deg)',
            'Q0', 'Q1', 'Q2', 'Q3',
            'FreeAcc_X', 'FreeAcc_Y', 'FreeAcc_Z',
            'Pressure(Pa)'
        ]
        self.csv_writer.writerow(header)
        logging.info(f"Created CSV file: {csv_filename}")
    
    def initialize_xda(self):
        """Initialize XDA and find wireless master"""
        # Create XDA instance
        self.my_xda = MyXda()
        
        # Find wireless master
        wireless_master_port = self.my_xda.find_wireless_master()
        if wireless_master_port is None:
            raise RuntimeError("No wireless masters found")
        
        # Open port
        if not self.my_xda.open_port(wireless_master_port):
            raise RuntimeError(f"Failed to open port {wireless_master_port.portName()}")
        
        # Get wireless master device
        self.wireless_master_device = self.my_xda.get_device(wireless_master_port.deviceId())
        if self.wireless_master_device is None:
            raise RuntimeError("Failed to get wireless master device")
        
        logging.info(f"Wireless master device: {self.wireless_master_device.deviceId()}")
        
        # Set config mode
        if not self.wireless_master_device.gotoConfig():
            raise RuntimeError("Failed to goto config mode")
        
        # Attach callback
        self.wireless_master_callback = WirelessMasterCallback()
        self.wireless_master_device.addCallbackHandler(self.wireless_master_callback)
        
        self.state = State.CONNECTED
    
    def configure_wireless_master(self):
        """Configure wireless master (update rate and radio channel)"""
        # Get supported update rates
        supported_rates = xda.XsDevice.supportedUpdateRates(
            self.wireless_master_device, xda.XDI_None
        )
        logging.info(f"Supported update rates: {list(supported_rates)}")
        
        # Find closest update rate
        new_update_rate = self.find_closest_update_rate(
            list(supported_rates), self.desired_update_rate
        )
        logging.info(f"Setting update rate to {new_update_rate} Hz...")
        
        if not self.wireless_master_device.setUpdateRate(new_update_rate):
            raise RuntimeError("Failed to set update rate")
        
        self.actual_data_rate = new_update_rate
        
        # Disable radio if enabled
        if self.wireless_master_device.isRadioEnabled():
            if not self.wireless_master_device.disableRadio():
                raise RuntimeError("Failed to disable radio")
        
        # Enable radio on desired channel
        logging.info(f"Enabling radio on channel {self.desired_radio_channel}...")
        if not self.wireless_master_device.enableRadio(self.desired_radio_channel):
            raise RuntimeError("Failed to enable radio")
        
        self.state = State.ENABLED
    
    def wait_for_mtw_connections(self):
        """Wait for MTW devices to connect wirelessly"""
        logging.info("Waiting for MTW to wirelessly connect...")
        logging.info("Press 'Y' to start measurement when ready.\n")
        
        connected_mtw_count = 0
        wait_for_connections = True
        
        while wait_for_connections:
            time.sleep(0.1)
            next_count = len(self.wireless_master_callback.get_connected_mtws())
            
            if next_count != connected_mtw_count:
                logging.info(f"Number of connected MTWs: {next_count}")
                connected_mtw_count = next_count
            
            wait_for_connections = not keyboard.is_pressed('y')
        
        logging.info(f"Starting with {connected_mtw_count} connected MTWs")
    
    def start_measurement(self):
        """Start measurement mode"""
        logging.info("Starting measurement...")
        
        if not self.wireless_master_device.gotoMeasurement():
            raise RuntimeError("Failed to goto measurement mode")
        
        # Get MTW devices and create callbacks
        mtw_devices = self.my_xda.get_mtw_devices()
        
        logging.info("Attaching callback handlers to MTWs...")
        self.mtw_callbacks = [
            MtwCallback(i, mtw_devices[i]) for i in range(len(mtw_devices))
        ]
        
        for i in range(len(mtw_devices)):
            mtw_devices[i].addCallbackHandler(self.mtw_callbacks[i])
        
        # Initialize data structures
        self.sensor_data = [ConnectedMTwData() for _ in range(len(self.mtw_callbacks))]
        for i, callback in enumerate(self.mtw_callbacks):
            self.sensor_data[i].device_id = str(callback.device().deviceId())
        
        # Initialize timestamp managers
        self.timestamp_managers = [
            TimestampManager(self.actual_data_rate) for _ in range(len(self.mtw_callbacks))
        ]
        
        # Initialize duplicate filter
        self.duplicate_filter = DuplicatePacketFilter(len(self.mtw_callbacks))
        
        self.state = State.MEASURING
    
    def start_recording(self):
        """Start recording to files"""
        # Generate filenames
        station_id = self.wireless_master_device.deviceId().toXsString()
        base_filename = self.generate_log_filename(station_id)
        
        # Create logs directory
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            logging.info(f"Created logs directory: {logs_dir}")
        
        # Full file paths
        mtb_filename = os.path.join(logs_dir, f"{base_filename}.mtb")
        csv_filename = os.path.join(logs_dir, f"{base_filename}.csv")
        
        logging.info(f"Log files: {base_filename}.mtb and {base_filename}.csv")
        
        # Create MTB log file
        if self.wireless_master_device.createLogFile(mtb_filename) != xda.XRV_OK:
            raise RuntimeError("Failed to create MTB log file")
        logging.info(f"Created MTB log file: {mtb_filename}")
        
        # Create CSV file
        self.create_csv_file(csv_filename)
        
        # Wait for data available
        logging.info("Waiting for data available from all MTWs...")
        ready_to_record = False
        while not ready_to_record:
            ready_to_record = all([
                self.mtw_callbacks[i].data_available() 
                for i in range(len(self.mtw_callbacks))
            ])
            if not ready_to_record:
                time.sleep(0.5)
        
        # Start recording
        if not self.wireless_master_device.startRecording():
            raise RuntimeError("Failed to start recording")
        
        logging.info("Recording started")
        self.state = State.RECORDING
    
    def collect_sensor_data(self):
        """Main data collection loop"""
        logging.info("\nMain loop. Press CTRL+C to quit\n")
        
        print_counter = 0
        loop_counter = 0
        
        while True:
            try:
                loop_counter += 1
                if loop_counter % 1000 == 0:
                    logging.debug(f"Loop iteration: {loop_counter}")
                
                time.sleep(0.001)  # Small sleep to prevent 100% CPU
                
                new_data_available = False
                sensors_updated = [False] * len(self.mtw_callbacks)
                
                # Process packets from each MTW
                for i in range(len(self.mtw_callbacks)):
                    try:
                        if self.mtw_callbacks[i].data_available():
                            new_data_available = True
                            packet = self.mtw_callbacks[i].get_oldest_packet()
                            
                            if packet is not None:
                                try:
                                    # Extract packet counter
                                    packet_counter = packet.packetCounter()
                                    
                                    # Check for duplicates
                                    is_duplicate = self.duplicate_filter.is_duplicate(i, packet_counter)
                                    
                                    if not is_duplicate:
                                        # Get PC timestamp
                                        pc_timestamp = get_high_accuracy_timestamp()
                                        
                                        # Compute timestamp
                                        computed_timestamp = self.timestamp_managers[i].get_timestamp(
                                            packet_counter, pc_timestamp
                                        )
                                        
                                        # Extract orientation (Euler)
                                        if packet.containsOrientation():
                                            euler = packet.orientationEuler()
                                            self.sensor_data[i].set_orientation_euler(
                                                float(euler.x()),
                                                float(euler.y()),
                                                float(euler.z())
                                            )
                                        
                                        # Extract quaternion
                                        q = packet.orientationQuaternion()
                                        self.sensor_data[i].set_orientation_quaternion(
                                            float(q[0]), float(q[1]), float(q[2]), float(q[3])
                                        )
                                        
                                        # Store timestamp and packet counter
                                        self.sensor_data[i].timestamp = float(computed_timestamp)
                                        self.sensor_data[i].packet_counter = int(packet_counter)
                                        
                                        # Extract gyroscope
                                        if packet.containsCalibratedGyroscopeData():
                                            gyr = packet.calibratedGyroscopeData()
                                            self.sensor_data[i].gyr_x = float(gyr[0])
                                            self.sensor_data[i].gyr_y = float(gyr[1])
                                            self.sensor_data[i].gyr_z = float(gyr[2])
                                        
                                        # Extract accelerometer
                                        if packet.containsCalibratedAcceleration():
                                            acc = packet.calibratedAcceleration()
                                            self.sensor_data[i].acc_x = float(acc[0])
                                            self.sensor_data[i].acc_y = float(acc[1])
                                            self.sensor_data[i].acc_z = float(acc[2])
                                        
                                        # Extract magnetometer
                                        if packet.containsCalibratedMagneticField():
                                            mag = packet.calibratedMagneticField()
                                            self.sensor_data[i].mag_x = float(mag[0])
                                            self.sensor_data[i].mag_y = float(mag[1])
                                            self.sensor_data[i].mag_z = float(mag[2])
                                        
                                        # Extract free acceleration
                                        if packet.containsFreeAcceleration():
                                            free_acc = packet.freeAcceleration()
                                            self.sensor_data[i].free_acc_x = float(free_acc[0])
                                            self.sensor_data[i].free_acc_y = float(free_acc[1])
                                            self.sensor_data[i].free_acc_z = float(free_acc[2])
                                        
                                        # Extract pressure
                                        if packet.containsPressure():
                                            pressure_obj = packet.pressure()
                                            self.sensor_data[i].pressure = int(pressure_obj.m_pressure)
                                        
                                        # Extract status
                                        if packet.containsStatus():
                                            self.sensor_data[i].status = int(packet.status())
                                        
                                        # Write to CSV
                                        self.csv_writer.writerow(self.sensor_data[i].to_csv_row())
                                        
                                        # Mark sensor as updated
                                        sensors_updated[i] = True
                                
                                except Exception as e:
                                    logging.error(f"Error extracting packet data {i}: {e}", exc_info=True)
                                
                                # Delete packet
                                self.mtw_callbacks[i].delete_oldest_packet()
                    
                    except Exception as e:
                        logging.error(f"Error processing callback {i}: {e}", exc_info=True)
                
                # Print data periodically
                if new_data_available and print_counter % 1 == 0:
                    try:
                        for i in range(len(self.mtw_callbacks)):
                            if sensors_updated[i]:
                                data = self.sensor_data[i]
                                print(f"[{i}]: ID: {data.device_id}, "
                                      f"Time: {data.timestamp:.5f}, "
                                      f"Pkt: {data.packet_counter:5d}, "
                                      f"Status: 0x{data.status:08X}, "
                                      f"Euler: [{data.roll:7.2f}, {data.pitch:7.2f}, {data.yaw:7.2f}]")
                    except Exception as e:
                        logging.error(f"Error printing data: {e}", exc_info=True)
                
                if new_data_available:
                    print_counter += 1
            
            except KeyboardInterrupt:
                logging.info("Keyboard interrupt in main loop")
                break
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(0.1)
        
        # Log statistics
        total_duplicates = self.duplicate_filter.get_duplicate_count()
        logging.info(f"Total duplicate packets filtered: {total_duplicates}")
    
    def run(self):
        """Main application run method"""
        try:
            # Initialize XDA
            self.initialize_xda()
            
            # Configure wireless master
            self.configure_wireless_master()
            
            # Wait for MTW connections
            self.wait_for_mtw_connections()
            
            # Start measurement
            self.start_measurement()
            
            # Start recording
            self.start_recording()
            
            # Collect data
            self.collect_sensor_data()
            
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt detected")
            print("\n****ABORT****")
        except Exception as ex:
            logging.error(f"Exception: {ex}", exc_info=True)
            print("****ABORT****")
        finally:
            if not self.cleanup_done:
                self.cleanup()