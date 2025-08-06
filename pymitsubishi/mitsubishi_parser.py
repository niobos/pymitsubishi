#!/usr/bin/env python3
"""
Mitsubishi Air Conditioner Protocol Parser

This module contains all the parsing logic for Mitsubishi AC protocol payloads,
including enums, state classes, and functions for decoding hex values.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class PowerOnOff(Enum):
    OFF = 0
    ON = 1
    ON2 = 2

class DriveMode(Enum):
    AUTO = 0
    HEATER = 1
    DEHUM = 2
    COOLER = 3
    AUTO_COOLER = 0x1b
    AUTO_HEATER = 0x19
    FAN = 7

class WindSpeed(int):
    pass

class VerticalWindDirection(Enum):
    AUTO = 0
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4
    V5 = 5
    SWING = 7

class HorizontalWindDirection(Enum):
    AUTO = 0
    L = 1
    LS = 2
    C = 3
    RS = 4
    R = 5
    LC = 6
    CR = 7
    LR = 8
    LCR = 9
    LCR_S = 12

@dataclass
class GeneralStates:
    """Parsed general AC states from device response"""
    power_on_off: PowerOnOff = PowerOnOff.OFF
    drive_mode: DriveMode = DriveMode.AUTO
    coarse_temperature: int = 22
    fine_temperature: float | None = 22.0
    wind_speed: WindSpeed = 0
    vertical_wind_direction: VerticalWindDirection = VerticalWindDirection.AUTO
    horizontal_wind_direction: HorizontalWindDirection | None = HorizontalWindDirection.AUTO
    dehum_setting: int | None = 0
    is_power_saving: bool | None = False
    wind_and_wind_break_direct: int | None = 0
    # Enhanced functionality based on SwiCago insights
    i_see_sensor: bool = False  # i-See sensor active flag
    mode_raw_value: int = 0     # Raw mode value before i-See processing
    wide_vane_adjustment: bool | None = False  # Wide vane adjustment flag (SwiCago wideVaneAdj)
    temp_mode: bool = False     # Direct temperature mode flag (SwiCago tempMode)
    undocumented_flags: Dict[str, Any] = None  # Store unknown bit patterns for analysis

    @staticmethod
    def is_general_states_payload(payload: bytes) -> bool:
        """Check if payload contains general states data"""
        if len(payload) < 6:
            return False
        return payload[1] in [0x62, 0x7b] and payload[5] == 0x02

    @classmethod
    def deserialize(cls, data: bytes) -> GeneralStates:
        logger.debug(f"GeneralState.deserialize: {data.hex()}")
        if len(data) < 21:
            raise ValueError("Data too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)
        payload = data.hex()

        # Compared to the SwiCago implementation, we have an offset of 5:
        # SwiCago's data[0] is our data[5]

        obj.power_on_off = PowerOnOff(data[8])

        # Enhanced mode parsing with i-See sensor detection
        obj.drive_mode = DriveMode(data[9] & 0x07)
        obj.i_see_sensor = bool(data[9] & 0x08)

        obj.coarse_temperature = cls._from_coarse_temperature(data[10])

        obj.wind_speed = WindSpeed(data[11])
        obj.vertical_wind_direction = VerticalWindDirection(data[12])

        if len(data) >= 16:
            wide_vane_data = data[15]
            obj.horizontal_wind_direction = HorizontalWindDirection(wide_vane_data & 0x0F)  # Lower 4 bits
            obj.wide_vane_adjustment = (wide_vane_data & 0xF0) == 0x80  # Upper 4 bits = 0x80
        else:
            obj.horizontal_wind_direction = None
            obj.wide_vane_adjustment = None

        if len(data) >= 17 and data[16] != 0x00:
            obj.fine_temperature = cls._from_fine_temperature(data[16])
        else:
            obj.fine_temperature = None

        if len(data) >= 18:
            obj.dehum_setting = data[17]
        else:
            obj.dehum_setting = None

        if len(data) >= 19:
            obj.is_power_saving = data[18] > 0
        else:
            obj.is_power_saving = None

        if len(data) >= 20:
            obj.wind_and_wind_break_direct = data[19]
        else:
            obj.wind_and_wind_break_direct = None

        # Analyze undocumented bits for research purposes
        obj.undocumented_analysis = cls.analyze_undocumented_bits(payload)

        return obj

    @staticmethod
    def analyze_undocumented_bits(payload: str) -> Dict[str, Any]:
        """Analyze payload for undocumented bit patterns and flags

        This function helps identify unknown functionality by examining
        bit patterns that haven't been documented yet.
        """
        analysis = {
            'payload_length': len(payload),
            'suspicious_patterns': [],
            'high_bits_set': [],
            'unknown_segments': {}
        }

        if len(payload) < 42:
            return analysis

        try:
            # Examine each byte for unusual patterns
            for i in range(0, min(len(payload), 42), 2):
                if i + 2 <= len(payload):
                    byte_hex = payload[i:i+2]
                    byte_val = int(byte_hex, 16)
                    position = i // 2

                    # Look for high bits that might indicate additional flags
                    if byte_val & 0x80:  # High bit set
                        analysis['high_bits_set'].append({
                            'position': position,
                            'hex': byte_hex,
                            'value': byte_val,
                            'binary': f"{byte_val:08b}"
                        })

                    # Look for patterns that don't match known mappings
                    if position == 9:  # Mode byte position
                        if byte_val not in [0x00, 0x01, 0x02, 0x03, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x19, 0x1b]:
                            analysis['suspicious_patterns'].append({
                                'type': 'unknown_mode',
                                'position': position,
                                'hex': byte_hex,
                                'value': byte_val,
                                'possible_i_see': byte_val > 0x08
                            })

                    # Check for non-zero values in typically unused positions
                    unused_positions = [12, 17, 19]  # Add more as we discover them
                    if position in unused_positions and byte_val != 0:
                        analysis['unknown_segments'][position] = {
                            'hex': byte_hex,
                            'value': byte_val,
                            'binary': f"{byte_val:08b}"
                        }

        except (ValueError, IndexError) as e:
            analysis['parse_error'] = str(e)

        return analysis

    def generate_general_command(self, controls: Dict[str, bool]) -> str:
        """Generate general control command hex string"""
        segments = {
            'segment0': '01',
            'segment1': '00',
            'segment2': '00',
            'segment3': '00',
            'segment4': '00',
            'segment5': '00',
            'segment6': '00',
            'segment7': '00',
            'segment13': '00',
            'segment14': '00',
            'segment15': '00',
        }

        # Calculate segment 1 value (control flags)
        segment1_value = 0
        if controls.get('power_on_off'):
            segment1_value |= 0x01
        if controls.get('drive_mode'):
            segment1_value |= 0x02
        if controls.get('temperature'):
            segment1_value |= 0x04
        if controls.get('wind_speed'):
            segment1_value |= 0x08
        if controls.get('up_down_wind_direct'):
            segment1_value |= 0x10

        # Calculate segment 2 value
        segment2_value = 0
        if controls.get('left_right_wind_direct'):
            segment2_value |= 0x01
        if controls.get('outside_control', True):  # Default true
            segment2_value |= 0x02

        segments['segment1'] = f"{segment1_value:02x}"
        segments['segment2'] = f"{segment2_value:02x}"
        segments['segment3'] = format(self.power_on_off.value, "02x")
        segments['segment4'] = format(self.drive_mode.value, "02x")
        segments['segment6'] = f"{self.wind_speed:02x}"
        segments['segment7'] = f"{self.vertical_wind_direction.value:02x}"
        segments['segment13'] = f"{self.horizontal_wind_direction.value:02x}"
        segments['segment15'] = '41'  # checkInside: 41 true, 42 false

        segments['segment5'] = format(self._to_coarse_temperature(self.coarse_temperature), "02x")
        segments['segment14'] = format(self._to_fine_temperature(self.fine_temperature), "02x")

        # Build payload
        payload = '41013010'
        for i in range(16):
            segment_key = f'segment{i}'
            payload += segments.get(segment_key, '00')

        # Calculate and append FCC
        fcc = format(calc_fcc(bytes.fromhex(payload)), "02x")
        return "fc" + payload + fcc

    def generate_extend08_command(self: GeneralStates, controls: Dict[str, bool]) -> str:
        """Generate extend08 command for buzzer, dehum, power saving, etc."""
        segment_x_value = 0
        if controls.get('dehum'):
            segment_x_value |= 0x04
        if controls.get('power_saving'):
            segment_x_value |= 0x08
        if controls.get('buzzer'):
            segment_x_value |= 0x10
        if controls.get('wind_and_wind_break'):
            segment_x_value |= 0x20

        segment_x = f"{segment_x_value:02x}"
        segment_y = f"{self.dehum_setting:02x}" if controls.get('dehum') else '00'
        segment_z = '0A' if self.is_power_saving else '00'
        segment_a = f"{self.wind_and_wind_break_direct:02x}" if controls.get('wind_and_wind_break') else '00'
        buzzer_segment = '01' if controls.get('buzzer') else '00'

        payload = "4101301008" + segment_x + "0000" + segment_y + segment_z + segment_a + buzzer_segment + "0000000000000000"
        fcc = format(calc_fcc(bytes.fromhex(payload)), "02x")
        return 'fc' + payload + fcc

    @staticmethod
    def _from_coarse_temperature(value: int) -> int:
        return 31 - value
    @staticmethod
    def _to_coarse_temperature(temp: int) -> int:
        if not 16 <= temp <= 31:
            raise ValueError(f"Invalid temperature value {temp}")
        return 31 - int(temp)

    @staticmethod
    def _from_fine_temperature(value: int) -> float:
        return (value - 0x80) * 0.5
    @staticmethod
    def _to_fine_temperature(temp: float | None) -> int:
        if temp is None:
            return 0x00
        return 0x80 + int(temp // 0.5)

    @property
    def temperature(self) -> float:
        if self.fine_temperature is not None:
            return self.fine_temperature
        return self.coarse_temperature


@dataclass
class SensorStates:
    """Parsed sensor states from device response"""
    outside_temperature: float | None
    room_temperature: float
    thermal_sensor: bool
    wind_speed_pr557: int

    @staticmethod
    def is_sensor_states_payload(payload: bytes) -> bool:
        """Check if payload contains sensor states data"""
        if len(payload) < 6:
            return False
        return payload[1] in [0x62, 0x7b] and payload[5] == 0x03

    @classmethod
    def deserialize(cls, data: bytes) -> SensorStates:
        if len(data) < 21:
            raise ValueError("Payload too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        obj.outside_temperature = GeneralStates._from_fine_temperature(data[10])
        obj.room_temperature = GeneralStates._from_fine_temperature(data[12])
        obj.thermal_sensor = (data[19] & 0x01) != 0
        obj.wind_speed_pr557 = 1 if (data[20] & 0x01) == 1 else 0

        return obj


@dataclass
class EnergyStates:
    """Parsed energy and operational states from device response"""
    compressor_frequency: Optional[int] = None  # Raw compressor frequency value
    operating: bool = False  # True if heat pump is actively operating
    estimated_power_watts: Optional[float] = None  # Estimated power consumption in Watts

    @staticmethod
    def is_energy_states_payload(payload: bytes) -> bool:
        """Check if payload contains energy/status data (SwiCago group 06)"""
        if len(payload) < 6:
            return False
        return payload[1] in [0x62, 0x7b] and payload[5] == 0x06

    @classmethod
    def deserialize(cls, data: bytes, general_states: Optional[GeneralStates] = None) -> EnergyStates:
        """Parse energy/status states from hex payload (SwiCago group 06)

        Based on SwiCago implementation:
        - data[3] = compressor frequency
        - data[4] = operating status (boolean)

        Args:
            data: payload bytes
            general_states: Optional general states for power estimation context
        """
        payload = data.hex()
        if len(data) < 12:  # Need at least enough bytes for data[4]
            raise ValueError("Payload too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        # Extract compressor frequency from data[3] (position 18-19 in hex string)
        obj.compressor_frequency = int(payload[18:20], 16)

        # Extract operating status from data[4] (position 20-21 in hex string)
        obj.operating = int(payload[20:22], 16) > 0

        # Estimate power consumption if we have context
        obj.estimated_power = None
        if general_states:
            obj.estimated_power = cls.estimate_power_consumption(
                obj.compressor_frequency,
                general_states.drive_mode,
                general_states.wind_speed
            )

        return obj

    @staticmethod
    def estimate_power_consumption(compressor_frequency: int, mode: DriveMode, fan_speed: WindSpeed) -> float:
        """Estimate power consumption based on compressor frequency and operational parameters

        This is a rough estimation based on empirical data from heat pump literature.
        Actual consumption varies significantly based on outdoor conditions, efficiency rating, etc.

        Args:
            compressor_frequency: Raw compressor frequency value (0-255 typical)
            mode: Operating mode (affects base consumption)
            fan_speed: Fan speed (affects additional consumption)

        Returns:
            Estimated power consumption in Watts
        """
        if compressor_frequency == 0:
            # Unit is not actively operating - only standby power
            return 10.0  # Typical standby consumption

        # Base power estimation from compressor frequency
        # This is a rough linear approximation - real curves are more complex
        frequency_factor = compressor_frequency / 255.0  # Normalize to 0-1

        # Mode-based base consumption (typical values for residential units)
        mode_base_watts = {
            DriveMode.COOLER: 1200,     # Cooling tends to use more power
            DriveMode.HEATER: 1000,     # Heating can be more efficient
            DriveMode.AUTO: 1100,       # Average
            DriveMode.DEHUM: 800,       # Dehumidification uses less
            DriveMode.FAN: 50,          # Fan only
            DriveMode.AUTO_COOLER: 1200,
            DriveMode.AUTO_HEATER: 1000,
        }

        base_power = mode_base_watts.get(mode, 1000)

        # Compressor power scales roughly with frequency
        compressor_power = base_power * frequency_factor

        # Fan power addition
        fan_power_map = {
            0: 50,      # Variable
            1: 30,   # Low speed
            2: 60,   # Medium-low
            3: 90,   # Medium-high
            4: 120, # High speed
        }

        fan_power = fan_power_map.get(fan_speed, 50)

        # Total estimated power
        total_power = compressor_power + fan_power + 20  # +20W for control electronics

        return round(total_power, 1)


@dataclass 
class ErrorStates:
    """Parsed error states from device response"""
    is_abnormal_state: bool = False
    error_code: str = "8000"

    @staticmethod
    def is_error_states_payload(payload: bytes) -> bool:
        """Check if payload contains error states data"""
        if len(payload) < 6:
            return False
        return payload[1] in [0x62, 0x7b] and payload[5] == 0x04

    @classmethod
    def deserialize(cls, data: bytes) -> ErrorStates:
        payload = data.hex()
        if len(payload) < 22:
            raise ValueError("Payload too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        code_head = payload[18:20]
        code_tail = payload[20:22]
        obj.is_abnormal_state = not (code_head == '80' and code_tail == '00')
        obj.error_code = f"{code_head}{code_tail}"

        return obj


@dataclass
class ParsedDeviceState:
    """Complete parsed device state combining all state types"""
    general: Optional[GeneralStates] = None
    sensors: Optional[SensorStates] = None
    errors: Optional[ErrorStates] = None
    energy: Optional[EnergyStates] = None  # New energy/operational data
    mac: str = ""
    serial: str = ""
    rssi: str = ""
    app_version: str = ""

    @classmethod
    def parse_code_values(cls, code_values: List[bytes]) -> ParsedDeviceState:
        """Parse a list of code values and return combined device state with energy information"""
        parsed_state = ParsedDeviceState()

        for value in code_values:
            hex_value = value.hex()
            if not hex_value or len(hex_value) < 20:
                continue

            hex_lower = hex_value.lower()
            if not all(c in '0123456789abcdef' for c in hex_lower):
                continue

            # Parse different payload types
            if GeneralStates.is_general_states_payload(value):
                parsed_state.general = GeneralStates.deserialize(value)
            elif SensorStates.is_sensor_states_payload(value):
                parsed_state.sensors = SensorStates.deserialize(value)
            elif ErrorStates.is_error_states_payload(value):
                parsed_state.errors = ErrorStates.deserialize(value)
            elif EnergyStates.is_energy_states_payload(value):
                # Parse energy states with context from general states if available
                parsed_state.energy = EnergyStates.deserialize(value, parsed_state.general)

        return parsed_state

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'device_info': {
                'mac': self.mac,
                'serial': self.serial,
                'rssi': self.rssi,
                'app_version': self.app_version,
            }
        }
        
        if self.general:
            result['general_states'] = {
                'power': 'ON' if self.general.power_on_off == PowerOnOff.ON else 'OFF',
                'mode': self.general.drive_mode.name,
                'target_temperature_celsius': self.general.temperature,
                'fan_speed': self.general.wind_speed.name,
                'vertical_wind_direction_right': self.general.vertical_wind_direction_right.name,
                'vertical_wind_direction_left': self.general.vertical_wind_direction_left.name,
                'horizontal_wind_direction': self.general.horizontal_wind_direction.name,
                'dehumidification_setting': self.general.dehum_setting,
                'power_saving_mode': self.general.is_power_saving,
                'wind_and_wind_break_direct': self.general.wind_and_wind_break_direct,
                # Enhanced functionality
                'i_see_sensor_active': self.general.i_see_sensor,
                'mode_raw_value': self.general.mode_raw_value,
            }
            # Include undocumented flags analysis if present
            if self.general.undocumented_flags:
                result['general_states']['undocumented_analysis'] = self.general.undocumented_flags
            
        if self.sensors:
            result['sensor_states'] = {
                'room_temperature_celsius': self.sensors.room_temperature,
                'outside_temperature_celsius': self.sensors.outside_temperature,
                'thermal_sensor_active': self.sensors.thermal_sensor,
                'wind_speed_pr557': self.sensors.wind_speed_pr557,
            }
            
        if self.errors:
            result['error_states'] = {
                'abnormal_state': self.errors.is_abnormal_state,
                'error_code': self.errors.error_code,
            }
            
        if self.energy:
            result['energy_states'] = {
                'compressor_frequency': self.energy.compressor_frequency,
                'operating': self.energy.operating,
                'estimated_power_watts': self.energy.estimated_power_watts,
            }
            
        return result

def calc_fcc(payload: bytes) -> int:
    """Calculate FCC checksum for Mitsubishi protocol payload"""
    return 0x100 - (sum(payload[0:20]) % 0x100)  # TODO: do we actually need to limit this to 20 bytes?
