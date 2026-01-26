"""
XDA (Xsens Device API) wrapper class
Handles device scanning, port opening, and device management
"""

import xsensdeviceapi as xda
import logging
from callbacks import WirelessMasterCallback


class MyXda:
    """Main XDA controller class - manages XsControl and device detection"""
    
    def __init__(self):
        """Construct the XsControl instance"""
        logging.info("Constructing XsControl...")
        self.m_control = xda.XsControl.construct()
        
        if self.m_control is None:
            raise RuntimeError("Failed to construct the XsControl instance.")
        
        self.m_detected_devices = set()
    
    def __del__(self):
        """Destructor - cleanup resources"""
        self.reset()
        if self.m_control is not None:
            self.m_control.destruct()
    
    def get_device(self, device_id):
        """Get device by device ID"""
        return self.m_control.device(device_id)
    
    def reset(self):
        """Reset and close all connections"""
        self.m_detected_devices.clear()
        if self.m_control is not None:
            self.m_control.close()
    
    def scan_ports(self):
        """
        Scan for available ports and detect devices
        Returns list of detected XsPortInfo objects
        """
        logging.info("Scanning ports...")
        self.m_detected_devices = xda.XsScanner_scanPorts()
        
        return list(self.m_detected_devices)
    
    def find_wireless_master(self):
        """
        Find wireless master device from detected devices
        Returns XsPortInfo for wireless master, or None if not found
        """
        logging.info("Finding wireless master...")
        detected_devices = self.scan_ports()
        
        for port in detected_devices:
            if port.deviceId().isWirelessMaster():
                logging.info(f"Wireless master found @ {port.portName()}")
                return port
        
        logging.warning("No wireless masters found")
        return None
    
    def open_port(self, port_info):
        """
        Open port for communication
        Returns True if successful, False otherwise
        """
        logging.info(f"Opening port {port_info.portName()}...")
        
        success = self.m_control.openPort(
            port_info.portName(), 
            port_info.baudrate()
        )
        
        if success:
            logging.info(f"Successfully opened port {port_info.portName()}")
        else:
            logging.error(f"Failed to open port {port_info.portName()}")
        
        return success
    
    def get_all_device_ids(self):
        """Get all device IDs from control"""
        return self.m_control.deviceIds()
    
    def get_mtw_devices(self):
        """
        Get all MTW devices
        Returns list of XsDevice instances for MTWs
        """
        logging.info("Getting XsDevice instances for all MTWs...")
        
        all_device_ids = self.get_all_device_ids()
        mtw_device_ids = [device_id for device_id in all_device_ids if device_id.isMtw()]
        
        mtw_devices = []
        for device_id in mtw_device_ids:
            mtw_device = self.m_control.device(device_id)
            if mtw_device is not None:
                mtw_devices.append(mtw_device)
            else:
                logging.error(f"Failed to create MTW XsDevice instance for {device_id}")
        
        logging.info(f"Found {len(mtw_devices)} MTW devices")
        return mtw_devices