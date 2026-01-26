"""
Main application window with PyQt5 GUI
Coordinates XDA, callbacks, and data collection with GUI display
"""

import os
import csv
import time
import logging
import signal
import atexit
from datetime import datetime
from threading import Thread, Lock

from PyQt5.QtWidgets import QMainWindow, QListWidgetItem, QMessageBox
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QElapsedTimer, Qt, QVariant
from PyQt5.QtGui import QPixmap, QTextCursor

import xsensdeviceapi as xda

from mainwindow_ui import Ui_MainWindow
from myxda import MyXda
from callbacks import WirelessMasterCallback, MtwCallback
from connected_mtw_data import ConnectedMTwData
from timestamp_manager import TimestampManager, get_high_accuracy_timestamp
from duplicate_filter import DuplicatePacketFilter


class State:
    """Application state machine"""
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


class XdaThread(QThread):
    """Separate thread for XDA operations"""
    pass


class MainWindow(QMainWindow):
    """
    Main application window with PyQt5 GUI
    """
    
    # Define signals as class attributes
    wirelessMasterDetected = pyqtSignal(object)
    dockedMtwDetected = pyqtSignal(object)
    mtwUndocked = pyqtSignal(object)
    openPortSuccessful = pyqtSignal(object)
    openPortFailed = pyqtSignal(object)
    
    # Add these new signals for MTW events
    mtwWirelessSignal = pyqtSignal(object)
    mtwDisconnectedSignal = pyqtSignal(object)
    batteryLevelChangedSignal = pyqtSignal(object, int)  # NEW: device_id, battery_level
    
    def __init__(self, parent=None):
        # Call parent constructor FIRST
        super(MainWindow, self).__init__(parent)
        
        # Setup UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Set window title
        self.setWindowTitle("Awinda Monitor")
        
        # State
        self.state = State.DETECTING
        
        # XDA components
        self.my_xda = None
        self.wireless_master_callback = None
        self.wireless_master_device = None
        self.mtw_callbacks = []
        self.mtw_devices = []  # Store MTW devices for reset heading
        
        # Battery request tracking (like C++ code)
        self.next_battery_request = 0  # Index of next MTW to request battery from
        
        # Data management
        self.sensor_data = []
        self.timestamp_managers = []
        self.duplicate_filter = None
        
        # File handles
        self.csv_file = None
        self.csv_writer = None
        
        # QT components
        self.port_scan_timer = None
        self.battery_level_request_timer = None
        self.xda_thread = None
        self.timestamp = QElapsedTimer()
        
        # Mutex for thread safety
        self.mutex = Lock()
        
        # Cleanup flag
        self.cleanup_done = False
        
        # Data collection thread
        self.data_collection_active = False
        self.data_collection_thread = None
        
        # Initialize components
        self.initialize_components()

    def initialize_components(self):
            """Initialize all components after UI is set up"""
            try:
                # Create XDA instance
                self.my_xda = MyXda()
                
                # Create callback with reference to this window
                self.wireless_master_callback = WirelessMasterCallback(self)
                
                # Connect signals to slots
                self.connect_signals()
                
                # Start timestamp
                self.timestamp.start()
                
                # Create timers
                self.port_scan_timer = QTimer(self)
                self.port_scan_timer.setInterval(1000)
                self.port_scan_timer.timeout.connect(self.scan_ports)
                
                self.battery_level_request_timer = QTimer(self)
                self.battery_level_request_timer.setInterval(1000)
                self.battery_level_request_timer.timeout.connect(self.request_battery_levels)
                
                # Create XDA thread
                self.xda_thread = XdaThread(self)
                
                # Start
                self.log("Detecting...")
                self.set_widgets_states()
                
                # Start timers
                self.xda_thread.start()
                self.port_scan_timer.start()
                self.battery_level_request_timer.start()
                
                # Register cleanup handlers
                atexit.register(self.cleanup)
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)
                
            except Exception as e:
                logging.error(f"Error initializing components: {e}", exc_info=True)
                raise
    
    def __del__(self):
        """Destructor"""
        self.cleanup()

    def connect_signals(self):
        """Connect all signals to slots"""
        # User -> GUI
        self.ui.enableButton.clicked.connect(self.toggle_radio_enabled)
        self.ui.startMeasurementButton.clicked.connect(self.toggle_measurement)
        self.ui.resetHeadingButton.clicked.connect(self.reset_heading)
        self.ui.recordingButton.clicked.connect(self.toggle_recording)
        self.ui.clearLogPushButton.clicked.connect(self.clear_log_window)
        self.ui.connectedMtwList.itemClicked.connect(self.clear_connected_mtw_data_labels)
        self.ui.connectedMtwList.currentItemChanged.connect(self.on_mtw_selection_changed)
        
        # XDA -> GUI signals
        self.wirelessMasterDetected.connect(self.handle_wireless_master_detected)
        self.dockedMtwDetected.connect(self.handle_docked_mtw_detected)
        self.mtwUndocked.connect(self.handle_mtw_undocked)
        self.openPortSuccessful.connect(self.handle_open_port_successful)
        self.openPortFailed.connect(self.handle_open_port_failed)
        
        # MTW callback -> GUI signals
        self.mtwWirelessSignal.connect(self.handle_mtw_wireless)
        self.mtwDisconnectedSignal.connect(self.handle_mtw_disconnected)
        self.batteryLevelChangedSignal.connect(self.handle_battery_level_changed)  # NEW
    
    def create_signal_emitter(self, signal_name):
        """Create a signal emitter for callback events"""
        # This is a workaround since we can't directly emit signals from callbacks
        def emitter(device_id):
            if signal_name == 'mtwWireless':
                self.handle_mtw_wireless(device_id)
            elif signal_name == 'mtwDisconnected':
                self.handle_mtw_disconnected(device_id)
        return emitter
    
    def signal_handler(self, sig, frame):
        """Handle CTRL+C interrupt"""
        logging.info(f"Signal {sig} received")
        self.cleanup()
        os._exit(0)
    
    def cleanup(self):
        """Cleanup resources on exit"""
        if self.cleanup_done:
            return
        
        self.cleanup_done = True
        logging.info("Cleanup function called")
        
        try:
            # Stop data collection
            self.data_collection_active = False
            if self.data_collection_thread is not None:
                self.data_collection_thread.join(timeout=2.0)
            
            # Stop timers
            self.port_scan_timer.stop()
            self.battery_level_request_timer.stop()
            
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
            
            # Stop XDA thread
            self.xda_thread.quit()
            self.xda_thread.wait()
        
        except Exception as e:
            logging.error(f"Error during cleanup: {e}", exc_info=True)
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.cleanup()
        event.accept()
    
    def log(self, message):
        """Log message to GUI window"""
        self.ui.logWindow.moveCursor(QTextCursor.End)
        self.ui.logWindow.insertPlainText(f"[{self.timestamp.elapsed()}] {message}\n")
        logging.info(message)
    
    def clear_log_window(self):
        """Clear log window"""
        self.ui.logWindow.clear()
    
    def set_widgets_states(self):
        """Set widget states based on current state"""
        if self.state == State.DETECTING:
            self.ui.stateDiagramLabel.setText("DETECTING")
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state == State.CONNECTING:
            self.ui.enableButton.setEnabled(False)
            self.ui.stateDiagramLabel.setText("CONNECTING")
            self.log("Scanning for station.")
            self.ui.recordingButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state == State.CONNECTED:
            self.ui.startMeasurementButton.setEnabled(False)
            self.ui.channelCaptionLabel.setEnabled(True)
            self.ui.channelComboBox.setEnabled(True)
            self.ui.enableButton.setEnabled(True)
            self.ui.enableButton.setText("Enable")
            self.ui.updateRateCaptionLabel.setEnabled(False)
            self.ui.allowedUpdateRatesComboBox.setEnabled(False)
            self.ui.stateDiagramLabel.setText("CONNECTED")
            self.ui.recordingButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state == State.ENABLED:
            self.ui.startMeasurementButton.setEnabled(self.ui.connectedMtwList.count() > 0)
            self.ui.startMeasurementButton.setText("Start Measurement")
            self.ui.enableButton.setText("Disable")
            self.ui.enableButton.setEnabled(True)
            self.ui.channelCaptionLabel.setEnabled(False)
            self.ui.channelComboBox.setEnabled(False)
            self.ui.updateRateCaptionLabel.setEnabled(True)
            self.ui.allowedUpdateRatesComboBox.setEnabled(True)
            self.ui.stateDiagramLabel.setText("ENABLED")
            self.ui.recordingButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state == State.OPERATIONAL:
            self.ui.startMeasurementButton.setEnabled(self.ui.connectedMtwList.count() > 0)
            self.ui.startMeasurementButton.setText("Start Measurement")
            self.ui.enableButton.setText("Disable")
            self.ui.enableButton.setEnabled(True)
            self.ui.channelCaptionLabel.setEnabled(False)
            self.ui.channelComboBox.setEnabled(False)
            self.ui.updateRateCaptionLabel.setEnabled(True)
            self.ui.allowedUpdateRatesComboBox.setEnabled(True)
            self.ui.stateDiagramLabel.setText("OPERATIONAL")
            self.ui.recordingButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state in [State.AWAIT_MEASUREMENT_START, State.AWAIT_RECORDING_START]:
            self.ui.enableButton.setEnabled(False)
            self.ui.startMeasurementButton.setText("Waiting for start...")
            self.ui.startMeasurementButton.setEnabled(False)
            self.ui.updateRateCaptionLabel.setEnabled(False)
            self.ui.allowedUpdateRatesComboBox.setEnabled(False)
            self.ui.stateDiagramLabel.setText("AWAIT START")
            self.ui.recordingButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(False)
        
        elif self.state == State.MEASURING:
            self.ui.enableButton.setEnabled(False)
            self.ui.startMeasurementButton.setText("Stop measuring")
            self.ui.startMeasurementButton.setEnabled(True)
            self.ui.updateRateCaptionLabel.setEnabled(False)
            self.ui.allowedUpdateRatesComboBox.setEnabled(False)
            self.ui.recordingButton.setText("Start recording")
            self.ui.recordingButton.setEnabled(True)
            self.ui.resetHeadingButton.setEnabled(True)  # ENABLE when measuring
            self.ui.flushingCaptionLabel.setEnabled(False)
            self.ui.flushingProgressBar.setEnabled(False)
            self.ui.flushingProgressBar.setValue(0)
            self.ui.stateDiagramLabel.setText("MEASURING")
        
        elif self.state == State.RECORDING:
            self.ui.recordingButton.setEnabled(True)
            self.ui.recordingButton.setText("Stop recording")
            self.ui.startMeasurementButton.setEnabled(False)
            self.ui.resetHeadingButton.setEnabled(True)  # Keep enabled during recording
            self.ui.stateDiagramLabel.setText("RECORDING")
        
        elif self.state == State.FLUSHING:
            self.ui.recordingButton.setEnabled(False)
            self.ui.recordingButton.setText("Flushing")
            self.ui.flushingCaptionLabel.setEnabled(True)
            self.ui.flushingProgressBar.setEnabled(True)
            self.ui.resetHeadingButton.setEnabled(False)
            self.ui.stateDiagramLabel.setText("FLUSHING")

    def scan_ports(self):
        """Scan for ports and detect devices"""
        try:
            detected_devices = self.my_xda.scan_ports()
            
            # Check for wireless master
            for port in detected_devices:
                if port.deviceId().isWirelessMaster():
                    if self.state == State.DETECTING:
                        self.wirelessMasterDetected.emit(port)
                elif port.deviceId().isMtw():
                    self.dockedMtwDetected.emit(port)
        
        except Exception as e:
            logging.error(f"Error scanning ports: {e}", exc_info=True)
    
    def handle_wireless_master_detected(self, port):
        """Handle wireless master detected"""
        if self.state == State.DETECTING:
            self.log(f"Master Detected. Port: {port.portName()}, ID: {port.deviceId()}")
            self.state = State.CONNECTING
            self.set_widgets_states()
            
            # Open port
            if self.my_xda.open_port(port):
                self.openPortSuccessful.emit(port)
            else:
                self.openPortFailed.emit(port)
    
    def handle_docked_mtw_detected(self, port):
        """Handle docked MTw detected"""
        self.log(f"MTw Docked. Port: {port.portName()}, ID: {port.deviceId()}")
        
        mtw_id = str(port.deviceId())
        items = self.ui.dockedMtwList.findItems(mtw_id, Qt.MatchFixedString)
        if not items:
            self.ui.dockedMtwList.addItem(mtw_id)
        
        self.ui.dockedMtwListGroupBox.setTitle(
            f"Docked MTw list ({self.ui.dockedMtwList.count()}):"
        )
    
    def handle_mtw_undocked(self, port):
        """Handle MTw undocked"""
        self.log(f"MTw Undocked. Port: {port.portName()}, ID: {port.deviceId()}")
        
        mtw_id = str(port.deviceId())
        for row in range(self.ui.dockedMtwList.count()):
            item = self.ui.dockedMtwList.item(row)
            if item.text() == mtw_id:
                self.ui.dockedMtwList.takeItem(row)
                break
        
        self.ui.dockedMtwListGroupBox.setTitle(
            f"Docked MTw list ({self.ui.dockedMtwList.count()}):"
        )
    
    def handle_open_port_successful(self, port):
        """Handle port opened successfully"""
        if self.state == State.CONNECTING:
            if port.deviceId().isWirelessMaster():
                # Set station ID label
                self.ui.stationIdLabel.setText(str(port.deviceId()))
                
                # Get device
                self.wireless_master_device = self.my_xda.get_device(port.deviceId())
                if self.wireless_master_device is None:
                    self.log("ERROR: Failed to get wireless master device")
                    return
                
                # Attach callback
                self.wireless_master_device.addCallbackHandler(self.wireless_master_callback)
                
                self.state = State.CONNECTED
                self.log(f"Master Connected. Port: {port.portName()}, ID: {port.deviceId()}")
                
                # Ensure radio is disabled initially
                if self.wireless_master_device.isRadioEnabled():
                    self.set_radio_channel(-1)
                
                self.set_widgets_states()
    
    def handle_open_port_failed(self, port):
        """Handle port open failed"""
        self.log(f"Connect to device failed. Port: {port.portName()}")
        
        if self.state == State.CONNECTING:
            self.log("Closing XDA")
            self.my_xda.reset()
            self.state = State.DETECTING
            self.set_widgets_states()
    
    def handle_mtw_wireless(self, device_id):
            """Handle MTw connected wirelessly"""
            try:
                # Convert device_id to string
                if hasattr(device_id, 'toString'):
                    mtw_id_str = device_id.toString()
                elif hasattr(device_id, 'toXsString'):
                    mtw_id_str = device_id.toXsString()
                else:
                    mtw_id_str = str(device_id)
                
                self.log(f"MTw Connected. ID: {mtw_id_str}")
                
                items = self.ui.connectedMtwList.findItems(mtw_id_str, Qt.MatchFixedString)
                if not items:
                    # New MTw - add it
                    mtw_data = ConnectedMTwData()
                    mtw_data.device_id = mtw_id_str
                    mtw_data.rssi = 0
                    
                    item = QListWidgetItem()
                    item.setText(mtw_id_str)
                    item.setData(Qt.UserRole, mtw_data)
                    
                    self.ui.connectedMtwList.addItem(item)
                    self.ui.connectedMtwList.setCurrentItem(item)
                    
                    self.ui.connectedMtwListGroupBox.setTitle(
                        f"Connected MTw list ({self.ui.connectedMtwList.count()}):"
                    )
                
                # Enable start measurement button if in ENABLED state
                if self.state == State.ENABLED:
                    self.ui.startMeasurementButton.setEnabled(self.ui.connectedMtwList.count() > 0)
                    self.log(f"Start Measurement button enabled (count: {self.ui.connectedMtwList.count()})")
            
            except Exception as e:
                logging.error(f"Error in handle_mtw_wireless: {e}", exc_info=True)
        
    def handle_mtw_disconnected(self, device_id):
        """Handle MTw disconnected"""
        try:
            # Convert device_id to string
            if hasattr(device_id, 'toString'):
                mtw_id_str = device_id.toString()
            elif hasattr(device_id, 'toXsString'):
                mtw_id_str = device_id.toXsString()
            else:
                mtw_id_str = str(device_id)
            
            self.log(f"MTw Disconnected. ID: {mtw_id_str}")
            
            items = self.ui.connectedMtwList.findItems(mtw_id_str, Qt.MatchFixedString)
            if items:
                row = self.ui.connectedMtwList.row(items[0])
                self.ui.connectedMtwList.takeItem(row)
                
                self.ui.connectedMtwListGroupBox.setTitle(
                    f"Connected MTw list ({self.ui.connectedMtwList.count()}):"
                )
                
                if self.state == State.ENABLED:
                    self.ui.startMeasurementButton.setEnabled(self.ui.connectedMtwList.count() > 0)
        
        except Exception as e:
            logging.error(f"Error in handle_mtw_disconnected: {e}", exc_info=True)
    
    def toggle_radio_enabled(self):
        """Toggle radio enabled/disabled"""
        channel = self.ui.channelComboBox.currentText()
        if self.state == State.CONNECTED:
            self.set_radio_channel(int(channel))
        else:
            self.set_radio_channel(-1)
    
    def set_radio_channel(self, channel):
        """Set radio channel"""
        if self.wireless_master_device is None:
            return
        
        if self.wireless_master_device.enableRadio(channel):
            if channel != -1:
                self.log(f"Master Enabled. ID: {self.wireless_master_device.deviceId()}, Channel: {channel}")
                
                # Get supported update rates
                supported_rates = xda.XsDevice.supportedUpdateRates(
                    self.wireless_master_device, xda.XDI_None
                )
                max_update_rate = self.wireless_master_device.maximumUpdateRate()
                
                # Populate update rate combo box
                self.ui.allowedUpdateRatesComboBox.clear()
                for rate in supported_rates:
                    if rate <= max_update_rate:
                        self.ui.allowedUpdateRatesComboBox.addItem(str(rate))
                
                # Select current update rate
                current_rate = self.wireless_master_device.updateRate()
                index = self.ui.allowedUpdateRatesComboBox.findText(str(current_rate))
                if index >= 0:
                    self.ui.allowedUpdateRatesComboBox.setCurrentIndex(index)
                
                self.state = State.ENABLED
                
                # Set default update rate of 75 Hz if available
                index_75 = self.ui.allowedUpdateRatesComboBox.findText("75")
                if index_75 >= 0:
                    self.ui.allowedUpdateRatesComboBox.setCurrentIndex(index_75)
            else:
                self.log(f"Master Disabled. ID: {self.wireless_master_device.deviceId()}")
                self.ui.connectedMtwList.clear()
                self.state = State.CONNECTED
            
            self.set_widgets_states()
        else:
            if channel != -1:
                self.log(f"Failed to enable wireless master. Channel: {channel}")
            else:
                self.log("Failed to disable wireless master")
    
    def toggle_measurement(self):
        """Toggle measurement on/off"""
        if self.wireless_master_device is None:
            return
        
        if self.state in [State.ENABLED, State.OPERATIONAL]:
            # Start measurement
            desired_rate = int(self.ui.allowedUpdateRatesComboBox.currentText())
            current_rate = self.wireless_master_device.updateRate()
            
            if desired_rate != current_rate:
                if self.wireless_master_device.setUpdateRate(desired_rate):
                    self.log(f"Update rate set to {desired_rate} Hz")
                else:
                    self.log(f"Failed to set update rate to {desired_rate} Hz")
            
            # Check if highest update rate
            if self.ui.allowedUpdateRatesComboBox.currentIndex() == 0:
                msg = QMessageBox()
                msg.setText("Note: at the highest update rate\nrecording will be at effective update rate.")
                msg.exec_()
            
            backup_state = self.state
            self.state = State.AWAIT_MEASUREMENT_START
            
            if self.wireless_master_device.gotoMeasurement():
                self.log("Starting measurement...")
                self.start_measurement()
            else:
                self.state = backup_state
                self.log("Failed to start measurement")
            
            self.set_widgets_states()
        
        elif self.state == State.MEASURING:
            # Stop measurement
            if self.wireless_master_device.gotoConfig():
                self.log("Stopping measurement...")
                self.stop_measurement()
            else:
                self.log("Failed to stop measurement")
    
    def start_measurement(self):
        """Start measurement mode"""
        # Get MTW devices and create callbacks
        mtw_devices = self.my_xda.get_mtw_devices()
        
        # Store reference to MTW devices for reset heading functionality
        self.mtw_devices = mtw_devices
        
        self.log("Attaching callback handlers to MTWs...")
        self.mtw_callbacks = [
            MtwCallback(i, mtw_devices[i], self) for i in range(len(mtw_devices))  # Pass self
        ]
        
        for i in range(len(mtw_devices)):
            mtw_devices[i].addCallbackHandler(self.mtw_callbacks[i])
        
        # Initialize data structures
        self.sensor_data = [ConnectedMTwData() for _ in range(len(self.mtw_callbacks))]
        for i, callback in enumerate(self.mtw_callbacks):
            self.sensor_data[i].device_id = str(callback.device().deviceId())
        
        # Get actual data rate
        actual_data_rate = self.wireless_master_device.updateRate()
        
        # Initialize timestamp managers
        self.timestamp_managers = [
            TimestampManager(actual_data_rate) for _ in range(len(self.mtw_callbacks))
        ]
        
        # Initialize duplicate filter
        self.duplicate_filter = DuplicatePacketFilter(len(self.mtw_callbacks))
        
        # Reset battery request iterator
        self.next_battery_request = 0
        
        self.state = State.MEASURING
        self.set_widgets_states()
        
        # Start data collection in background thread
        self.data_collection_active = True
        self.data_collection_thread = Thread(target=self.collect_sensor_data, daemon=True)
        self.data_collection_thread.start()
    
    def stop_measurement(self):
        """Stop measurement mode"""
        # Stop data collection
        self.data_collection_active = False
        if self.data_collection_thread is not None:
            self.data_collection_thread.join(timeout=2.0)
        
        # Clear callbacks
        for callback in self.mtw_callbacks:
            callback.device().clearCallbackHandlers()
        
        self.mtw_callbacks.clear()
        
        # Clear device reference
        self.mtw_devices = []
        
        # Reset battery request iterator
        self.next_battery_request = 0
        
        self.state = State.OPERATIONAL
        self.set_widgets_states()
    
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.state == State.MEASURING:
            # Start recording
            self.start_recording()
        elif self.state == State.RECORDING:
            # Stop recording
            self.stop_recording()
    
    def start_recording(self):
        """Start recording to files"""
        # Generate filenames
        station_id = self.wireless_master_device.deviceId().toXsString()
        base_filename = self.generate_log_filename(station_id)
        
        # Create logs directory
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        # Full file paths
        mtb_filename = os.path.join(logs_dir, f"{base_filename}.mtb")
        csv_filename = os.path.join(logs_dir, f"{base_filename}.csv")
        
        self.log(f"Creating log files: {base_filename}")
        
        # Create MTB log file
        if self.wireless_master_device.createLogFile(mtb_filename) != xda.XRV_OK:
            self.log("Failed to create MTB log file")
            return
        
        self.log(f"Created MTB log file: {mtb_filename}")
        
        # Create CSV file
        self.create_csv_file(csv_filename)
        
        # Start recording
        if self.wireless_master_device.startRecording():
            self.log("Recording started")
            self.state = State.RECORDING
            self.set_widgets_states()
        else:
            self.log("Failed to start recording")
    
    def stop_recording(self):
        """Stop recording"""
        self.state = State.FLUSHING
        self.wireless_master_device.stopRecording()
        self.log("Stopping recording...")
        
        # Close CSV file
        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
        
        # Close MTB file
        self.wireless_master_device.closeLogFile()
        
        self.state = State.MEASURING
        self.set_widgets_states()
    
    def generate_log_filename(self, station_id):
        """Generate log filename"""
        now = datetime.now()
        timestamp_str = now.strftime("%y%m%d_%H%M%S")
        return f"{station_id}_{timestamp_str}"
    
    def create_csv_file(self, csv_filename):
        """Create CSV file with header"""
        self.csv_file = open(csv_filename, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file, delimiter=',')
        
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
        self.log(f"Created CSV file: {csv_filename}")
    
    def collect_sensor_data(self):
        """Background thread for collecting sensor data"""
        while self.data_collection_active:
            try:
                time.sleep(0.001)
                
                for i in range(len(self.mtw_callbacks)):
                    if self.mtw_callbacks[i].data_available():
                        packet = self.mtw_callbacks[i].get_oldest_packet()
                        
                        if packet is not None:
                            try:
                                packet_counter = packet.packetCounter()
                                
                                # Check for duplicates
                                is_duplicate = self.duplicate_filter.is_duplicate(i, packet_counter)
                                
                                if not is_duplicate:
                                    pc_timestamp = get_high_accuracy_timestamp()
                                    computed_timestamp = self.timestamp_managers[i].get_timestamp(
                                        packet_counter, pc_timestamp
                                    )
                                    
                                    # Extract all data
                                    if packet.containsOrientation():
                                        euler = packet.orientationEuler()
                                        self.sensor_data[i].set_orientation_euler(
                                            float(euler.x()), float(euler.y()), float(euler.z())
                                        )
                                    
                                    q = packet.orientationQuaternion()
                                    self.sensor_data[i].set_orientation_quaternion(
                                        float(q[0]), float(q[1]), float(q[2]), float(q[3])
                                    )
                                    
                                    self.sensor_data[i].timestamp = float(computed_timestamp)
                                    self.sensor_data[i].packet_counter = int(packet_counter)
                                    
                                    if packet.containsCalibratedGyroscopeData():
                                        gyr = packet.calibratedGyroscopeData()
                                        self.sensor_data[i].gyr_x = float(gyr[0])
                                        self.sensor_data[i].gyr_y = float(gyr[1])
                                        self.sensor_data[i].gyr_z = float(gyr[2])
                                    
                                    if packet.containsCalibratedAcceleration():
                                        acc = packet.calibratedAcceleration()
                                        self.sensor_data[i].acc_x = float(acc[0])
                                        self.sensor_data[i].acc_y = float(acc[1])
                                        self.sensor_data[i].acc_z = float(acc[2])
                                    
                                    if packet.containsCalibratedMagneticField():
                                        mag = packet.calibratedMagneticField()
                                        self.sensor_data[i].mag_x = float(mag[0])
                                        self.sensor_data[i].mag_y = float(mag[1])
                                        self.sensor_data[i].mag_z = float(mag[2])
                                    
                                    if packet.containsFreeAcceleration():
                                        free_acc = packet.freeAcceleration()
                                        self.sensor_data[i].free_acc_x = float(free_acc[0])
                                        self.sensor_data[i].free_acc_y = float(free_acc[1])
                                        self.sensor_data[i].free_acc_z = float(free_acc[2])
                                    
                                    if packet.containsPressure():
                                        pressure_obj = packet.pressure()
                                        self.sensor_data[i].pressure = int(pressure_obj.m_pressure)
                                    
                                    if packet.containsStatus():
                                        self.sensor_data[i].status = int(packet.status())
                                    
                                    # RSSI
                                    self.sensor_data[i].rssi = packet.rssi()
                                    
                                    # Write to CSV if recording
                                    if self.state == State.RECORDING and self.csv_writer is not None:
                                        self.csv_writer.writerow(self.sensor_data[i].to_csv_row())
                                    
                                    # Update GUI for selected MTw
                                    self.update_mtw_display(i)
                            
                            except Exception as e:
                                logging.error(f"Error extracting packet data: {e}", exc_info=True)
                            
                            self.mtw_callbacks[i].delete_oldest_packet()
            
            except Exception as e:
                logging.error(f"Error in data collection: {e}", exc_info=True)
    
    def update_mtw_display(self, mtw_index):
        """Update MTw display in GUI"""
        try:
            # Find MTw in list
            device_id = self.sensor_data[mtw_index].device_id
            items = self.ui.connectedMtwList.findItems(device_id, Qt.MatchFixedString)
            
            if items:
                item = items[0]
                # Update stored data
                item.setData(Qt.UserRole, self.sensor_data[mtw_index])
                
                # If this MTw is selected, update display
                if self.ui.connectedMtwList.currentItem() == item:
                    self.display_mtw_data(self.sensor_data[mtw_index])
        
        except Exception as e:
            logging.error(f"Error updating MTw display: {e}", exc_info=True)
    
    def display_mtw_data(self, mtw_data):
        """Display MTw data in properties panel"""
        try:
            self.ui.batteryLevelLabel.setText(f"{mtw_data.battery_level} [%]")
            self.ui.rssiLabel.setText(f"{mtw_data.rssi} [dBm]")
            self.ui.effUpdateRateLabel.setText(f"{mtw_data.effective_update_rate:.1f} [%]")
            
            if mtw_data.contains_orientation:
                self.ui.rollLabel.setText(f"{mtw_data.roll:7.2f} [deg]")
                self.ui.pitchLabel.setText(f"{mtw_data.pitch:7.2f} [deg]")
                self.ui.yawLabel.setText(f"{mtw_data.yaw:7.2f} [deg]")
        
        except Exception as e:
            logging.error(f"Error displaying MTw data: {e}", exc_info=True)
    
    def clear_connected_mtw_data_labels(self):
        """Clear MTw data labels"""
        self.ui.batteryLevelLabel.setText("-")
        self.ui.rssiLabel.setText("-")
        self.ui.effUpdateRateLabel.setText("-")
        self.ui.rollLabel.setText("-")
        self.ui.pitchLabel.setText("-")
        self.ui.yawLabel.setText("-")
    
    def on_mtw_selection_changed(self, current, previous):
        """Handle MTw selection change"""
        if current is not None:
            mtw_data = current.data(Qt.UserRole)
            if mtw_data is not None and isinstance(mtw_data, ConnectedMTwData):
                self.display_mtw_data(mtw_data)
    
    def request_battery_levels(self):
            """
            Request battery levels from MTWs (cycle through them one at a time)
            This mimics the C++ implementation
            """
            try:
                with self.mutex:
                    # Only request battery if we're measuring
                    if self.state not in [State.MEASURING, State.RECORDING]:
                        return
                    
                    # Check if we have any MTW callbacks
                    if not self.mtw_callbacks or len(self.mtw_callbacks) == 0:
                        return
                    
                    # Reset iterator if needed
                    if self.next_battery_request >= len(self.mtw_callbacks):
                        self.next_battery_request = 0
                    
                    # Request battery from next MTW
                    if self.next_battery_request < len(self.mtw_callbacks):
                        device = self.mtw_callbacks[self.next_battery_request].device()
                        device.requestBatteryLevel()
                        logging.debug(f"Requested battery level from MTW {self.next_battery_request}")
                        
                        # Move to next MTW for next request
                        self.next_battery_request += 1
            
            except Exception as e:
                logging.error(f"Error requesting battery levels: {e}", exc_info=True)

    def handle_battery_level_changed(self, device_id, battery_level):
        """Handle battery level changed event"""
        try:
            # Convert device_id to string
            if hasattr(device_id, 'toString'):
                mtw_id_str = device_id.toString()
            elif hasattr(device_id, 'toXsString'):
                mtw_id_str = device_id.toXsString()
            else:
                mtw_id_str = str(device_id)
            
            logging.debug(f"Battery level changed: {mtw_id_str} = {battery_level}%")
            
            # Find MTw in list
            items = self.ui.connectedMtwList.findItems(mtw_id_str, Qt.MatchFixedString)
            
            if items:
                item = items[0]
                mtw_data = item.data(Qt.UserRole)
                
                if mtw_data is not None and isinstance(mtw_data, ConnectedMTwData):
                    # Update battery level
                    mtw_data.battery_level = battery_level
                    
                    # Store back in item
                    item.setData(Qt.UserRole, mtw_data)
                    
                    # If this MTw is currently selected, update display
                    if self.ui.connectedMtwList.currentItem() == item:
                        self.display_mtw_data(mtw_data)
        
        except Exception as e:
            logging.error(f"Error handling battery level changed: {e}", exc_info=True)

    def reset_heading(self):
            """Reset heading (yaw) for all MTW sensors"""
            try:
                if not hasattr(self, 'mtw_devices') or len(self.mtw_devices) == 0:
                    self.log("ERROR: No MTW devices available for heading reset")
                    return
                
                self.log("Resetting heading for all MTW sensors...")
                
                # Reset heading for all MTW devices
                success_count = 0
                for i, device in enumerate(self.mtw_devices):
                    try:
                        if device.resetOrientation(xda.XRM_Heading):
                            success_count += 1
                            logging.debug(f"Reset heading for MTW {i}: {device.deviceId()}")
                        else:
                            logging.warning(f"Failed to reset heading for MTW {i}: {device.deviceId()}")
                    except Exception as e:
                        logging.error(f"Error resetting heading for MTW {i}: {e}", exc_info=True)
                
                if success_count == len(self.mtw_devices):
                    self.log(f"Successfully reset heading for all {success_count} MTW sensors")
                else:
                    self.log(f"Reset heading: {success_count}/{len(self.mtw_devices)} successful")
            
            except Exception as e:
                logging.error(f"Error in reset_heading: {e}", exc_info=True)
                self.log(f"ERROR: Failed to reset heading - {str(e)}")