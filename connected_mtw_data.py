"""
Data structure for storing MTW sensor data
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ConnectedMTwData:
    """
    Stores all sensor data for a connected MTW
    Similar to C++ ConnectedMTwData class
    """
    
    # Device identification
    device_id: str = ""
    
    # Timing information
    timestamp: float = 0.0
    packet_counter: int = 0
    
    # Orientation (Euler angles in degrees)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    
    # Orientation (Quaternion)
    q0: float = 0.0
    q1: float = 0.0
    q2: float = 0.0
    q3: float = 0.0
    
    # Calibrated gyroscope (rad/s)
    gyr_x: float = 0.0
    gyr_y: float = 0.0
    gyr_z: float = 0.0
    
    # Calibrated accelerometer (m/s^2)
    acc_x: float = 0.0
    acc_y: float = 0.0
    acc_z: float = 0.0
    
    # Calibrated magnetometer
    mag_x: float = 0.0
    mag_y: float = 0.0
    mag_z: float = 0.0
    
    # Free acceleration (without gravity)
    free_acc_x: float = 0.0
    free_acc_y: float = 0.0
    free_acc_z: float = 0.0
    
    # Pressure sensor
    pressure: int = 0
    
    # Status word
    status: int = 0
    
    # Additional metrics (like in C++ version)
    battery_level: int = 0
    rssi: int = 0  # Received Signal Strength Indicator
    effective_update_rate: float = 0.0
    
    # Frame skip tracking
    frame_skips_list: List[int] = field(default_factory=list)
    sum_frame_skips: int = 0
    
    # Flags
    contains_orientation: bool = False
    
    def set_orientation_euler(self, roll: float, pitch: float, yaw: float):
        """Set orientation from Euler angles"""
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.contains_orientation = True
    
    def set_orientation_quaternion(self, q0: float, q1: float, q2: float, q3: float):
        """Set orientation from quaternion"""
        self.q0 = q0
        self.q1 = q1
        self.q2 = q2
        self.q3 = q3
    
    def update_effective_rate(self, frame_skips: int):
        """
        Update effective update rate based on frame skips
        Mirrors the C++ implementation logic
        """
        self.frame_skips_list.append(frame_skips)
        self.sum_frame_skips += frame_skips
        
        # Calculate effective update rate
        total_frames = len(self.frame_skips_list) + self.sum_frame_skips
        if total_frames > 0:
            self.effective_update_rate = 100 * (1 - self.sum_frame_skips / total_frames)
        
        # Keep rolling window of 99 frames
        while len(self.frame_skips_list) + self.sum_frame_skips > 99 and len(self.frame_skips_list) > 0:
            self.sum_frame_skips -= self.frame_skips_list.pop(0)
    
    def to_csv_row(self) -> List[str]:
        """Convert data to CSV row format"""
        return [
            self.device_id,
            f"{self.timestamp:.5f}",
            str(self.packet_counter),
            str(self.status),
            f"{self.gyr_x:.6f}",
            f"{self.gyr_y:.6f}",
            f"{self.gyr_z:.6f}",
            f"{self.acc_x:.6f}",
            f"{self.acc_y:.6f}",
            f"{self.acc_z:.6f}",
            f"{self.mag_x:.6f}",
            f"{self.mag_y:.6f}",
            f"{self.mag_z:.6f}",
            f"{self.roll:.6f}",
            f"{self.pitch:.6f}",
            f"{self.yaw:.6f}",
            f"{self.q0:.6f}",
            f"{self.q1:.6f}",
            f"{self.q2:.6f}",
            f"{self.q3:.6f}",
            f"{self.free_acc_x:.6f}",
            f"{self.free_acc_y:.6f}",
            f"{self.free_acc_z:.6f}",
            str(self.pressure)
        ]