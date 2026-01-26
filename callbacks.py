"""
Callback handlers for XDA events
"""

import xsensdeviceapi as xda
from collections import deque
from threading import Lock
import logging


class WirelessMasterCallback(xda.XsCallback):
    """
    Callback handler for wireless master device
    Tracks connected MTW devices and their connectivity state
    """
    
    def __init__(self, main_window=None):
        super().__init__()
        self.m_connected_mtws = set()
        self.m_mutex = Lock()
        self.main_window = main_window  # Reference to MainWindow for signal emission
    
    def set_main_window(self, main_window):
        """Set reference to main window for signal emission"""
        self.main_window = main_window
    
    def get_connected_mtws(self):
        """Get copy of connected MTWs set (thread-safe)"""
        with self.m_mutex:
            return self.m_connected_mtws.copy()
    
    def onConnectivityChanged(self, dev, new_state):
        """
        Called when MTW connectivity state changes
        Handles connection, disconnection, and rejection events
        """
        try:
            with self.m_mutex:
                if new_state == xda.XCS_Disconnected:
                    logging.info(f"EVENT: MTW Disconnected -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    # Emit signal to GUI
                    if self.main_window:
                        self.main_window.mtwDisconnectedSignal.emit(dev.deviceId())
                    
                elif new_state == xda.XCS_Rejected:
                    logging.info(f"EVENT: MTW Rejected -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    
                elif new_state == xda.XCS_PluggedIn:
                    logging.info(f"EVENT: MTW PluggedIn -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    
                elif new_state == xda.XCS_Wireless:
                    logging.info(f"EVENT: MTW Connected -> {dev.deviceId()}")
                    self.m_connected_mtws.add(dev)
                    # Emit signal to GUI
                    if self.main_window:
                        self.main_window.mtwWirelessSignal.emit(dev.deviceId())
                    
                elif new_state == xda.XCS_File:
                    logging.info(f"EVENT: MTW File -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    
                elif new_state == xda.XCS_Unknown:
                    logging.info(f"EVENT: MTW Unknown -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    
                else:
                    logging.info(f"EVENT: MTW Error -> {dev.deviceId()}")
                    self.m_connected_mtws.discard(dev)
                    
        except Exception as e:
            logging.error(f"Error in onConnectivityChanged: {e}", exc_info=True)
    
    def onDeviceStateChanged(self, device, new_state, old_state):
        """Called when device state changes (config, measurement, recording)"""
        try:
            if new_state == xda.XDS_Config:
                if old_state != xda.XDS_Initial:
                    logging.info(f"Device {device.deviceId()} entered Config mode")
                    
            elif new_state == xda.XDS_Measurement:
                logging.info(f"Device {device.deviceId()} started Measurement")
                
            elif new_state == xda.XDS_WaitingForRecordingStart:
                logging.info(f"Device {device.deviceId()} waiting for recording start")
                
            elif new_state == xda.XDS_Recording:
                logging.info(f"Device {device.deviceId()} started Recording")
                
        except Exception as e:
            logging.error(f"Error in onDeviceStateChanged: {e}", exc_info=True)
    
    def onError(self, device, error):
        """Called when device error occurs"""
        try:
            error_str = xda.XsResultValue_toString(error)
            logging.error(f"Device error - ID: {device.deviceId()}, Error: {error_str}")
        except Exception as e:
            logging.error(f"Error in onError callback: {e}", exc_info=True)


class MtwCallback(xda.XsCallback):
    """
    Callback handler for individual MTW device
    Buffers incoming data packets for processing
    """
    
    def __init__(self, mtw_index, device):
        super().__init__()
        self.m_packet_buffer = deque(maxlen=300)
        self.m_mutex = Lock()
        self.m_mtw_index = mtw_index
        self.m_device = device
        self.packet_count = 0
    
    def data_available(self):
        """Check if data is available in buffer (thread-safe)"""
        try:
            with self.m_mutex:
                return bool(self.m_packet_buffer)
        except Exception as e:
            logging.error(f"Error in data_available: {e}", exc_info=True)
            return False
    
    def get_oldest_packet(self):
        """Get oldest packet from buffer without removing it"""
        try:
            with self.m_mutex:
                if len(self.m_packet_buffer) > 0:
                    return self.m_packet_buffer[0]
                return None
        except Exception as e:
            logging.error(f"Error in get_oldest_packet: {e}", exc_info=True)
            return None
    
    def delete_oldest_packet(self):
        """Remove oldest packet from buffer"""
        try:
            with self.m_mutex:
                if len(self.m_packet_buffer) > 0:
                    self.m_packet_buffer.popleft()
        except Exception as e:
            logging.error(f"Error in delete_oldest_packet: {e}", exc_info=True)
    
    def get_mtw_index(self):
        """Get MTW index"""
        return self.m_mtw_index
    
    def device(self):
        """Get device instance"""
        assert self.m_device is not None
        return self.m_device
    
    def onLiveDataAvailable(self, dev, packet):
        """
        Called when new live data packet arrives
        NOTE: Processing should not be done in this thread - just buffer the packet
        """
        try:
            with self.m_mutex:
                self.m_packet_buffer.append(packet)
                self.packet_count += 1
                
                # Buffer overflow protection (already handled by maxlen, but log it)
                if len(self.m_packet_buffer) >= 300:
                    logging.warning(f"MTW {self.m_mtw_index} buffer near full: {len(self.m_packet_buffer)}")
                    
        except Exception as e:
            logging.error(f"Error in onLiveDataAvailable: {e}", exc_info=True)
    
    def onInfoResponse(self, dev, request):
        """Called when info response received (e.g., battery level)"""
        try:
            if request == xda.XIR_BatteryLevel:
                battery_level = dev.batteryLevel()
                logging.debug(f"MTW {self.m_mtw_index} battery level: {battery_level}%")
        except Exception as e:
            logging.error(f"Error in onInfoResponse: {e}", exc_info=True)