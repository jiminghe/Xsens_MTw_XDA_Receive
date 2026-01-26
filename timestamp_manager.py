"""
Timestamp management based on packet counter and data rate
"""

import time
import logging


def get_high_accuracy_timestamp() -> float:
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
    
    # uint32 max value for wraparound detection
    UINT32_MAX = 0xFFFFFFFF
    
    def __init__(self, data_rate: int):
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
    
    def get_timestamp(self, packet_counter: int, pc_timestamp: float = None) -> float:
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
    
    def _compute_counter_diff(self, current_counter: int, reference_counter: int) -> int:
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