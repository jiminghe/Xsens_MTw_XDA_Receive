"""
Duplicate packet detection and filtering
"""

import logging
from typing import Dict


class DuplicatePacketFilter:
    """
    Detects and filters duplicate packets based on sensor ID and packet counter.
    """
    
    def __init__(self, num_sensors: int):
        """
        Initialize duplicate packet filter.
        
        Args:
            num_sensors: Number of sensors to track
        """
        # Dictionary to store last packet counter for each sensor
        # Key: sensor_index, Value: last_packet_counter
        self.last_packet_counters: Dict[int, int] = {}
        self.duplicate_count = 0
    
    def is_duplicate(self, sensor_index: int, packet_counter: int) -> bool:
        """
        Check if this packet is a duplicate.
        
        Args:
            sensor_index: Index of the sensor (0, 1, 2, ...)
            packet_counter: Current packet counter
            
        Returns:
            bool: True if duplicate, False if new packet
        """
        # Check if we have seen this sensor before
        if sensor_index not in self.last_packet_counters:
            # First packet from this sensor
            self.last_packet_counters[sensor_index] = packet_counter
            return False
        
        # Check if packet counter is the same as last time
        if self.last_packet_counters[sensor_index] == packet_counter:
            # Duplicate packet detected
            self.duplicate_count += 1
            logging.debug(f"Duplicate packet detected for sensor {sensor_index}, "
                         f"packet counter: {packet_counter}")
            return True
        else:
            # New packet - update the last counter
            self.last_packet_counters[sensor_index] = packet_counter
            return False
    
    def get_duplicate_count(self) -> int:
        """Get total number of duplicates detected."""
        return self.duplicate_count
    
    def reset(self):
        """Reset the duplicate filter."""
        self.last_packet_counters = {}
        self.duplicate_count = 0