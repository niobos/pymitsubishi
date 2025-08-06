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

from pymitsubishi import MitsubishiAPI

# Temperature constants
MIN_TEMPERATURE = 160  # 16.0°C in 0.1°C units
MAX_TEMPERATURE = 310  # 31.0°C in 0.1°C units

class PowerOnOff(Enum):
    OFF = '00'
    ON = '01'

    @classmethod
    def from_segment(cls, segment: str) -> PowerOnOff:
        if segment in ['01', '02']:
            return PowerOnOff.ON
        else:
            return PowerOnOff.OFF

class DriveMode(Enum):
    AUTO = 0
    HEATER = 1
    DEHUM = 2
    COOLER = 3
    AUTO_COOLER = 0x1b
    AUTO_HEATER = 0x19
    FAN = 7

    @classmethod
    def from_segment(cls, segment: int) -> DriveMode:
        mode_map = {
            0x03: DriveMode.COOLER, 0x0b: DriveMode.COOLER,
            0x01: DriveMode.HEATER, 0x09: DriveMode.HEATER,
            0x08: DriveMode.AUTO,
            0x00: DriveMode.DEHUM, 0x02: DriveMode.DEHUM, 0x0a: DriveMode.DEHUM, 0x0c: DriveMode.DEHUM,
            0x1b: DriveMode.AUTO_COOLER,
            0x19: DriveMode.AUTO_HEATER,
        }
        return mode_map.get(segment, DriveMode.FAN)

class WindSpeed(Enum):
    AUTO = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_FULL = 5

    @classmethod
    def from_segment(cls, segment: str) -> WindSpeed:
        speed_map = {
            '00': WindSpeed.AUTO,
            '01': WindSpeed.LEVEL_1,
            '02': WindSpeed.LEVEL_2,
            '03': WindSpeed.LEVEL_3,
            '05': WindSpeed.LEVEL_FULL,
        }
        return speed_map.get(segment, WindSpeed.AUTO)

class VerticalWindDirection(Enum):
    AUTO = 0
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4
    V5 = 5
    SWING = 7

    @classmethod
    def from_segment(cls, segment: str) -> VerticalWindDirection:
        direction_map = {
            '00': VerticalWindDirection.AUTO,
            '01': VerticalWindDirection.V1,
            '02': VerticalWindDirection.V2,
            '03': VerticalWindDirection.V3,
            '04': VerticalWindDirection.V4,
            '05': VerticalWindDirection.V5,
            '07': VerticalWindDirection.SWING,
        }
        return direction_map.get(segment, VerticalWindDirection.AUTO)

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

    @classmethod
    def from_segment(cls, segment: str) -> HorizontalWindDirection:
        value = int(segment, 16) & 0x7F  # 127 & value
        try:
            return HorizontalWindDirection(value)
        except ValueError:
            return HorizontalWindDirection.AUTO

class MitsubishiTemperature(float):
    @classmethod
    def from_segment(cls, segment: int) -> MitsubishiTemperature:
        t = (segment - 0x80) * 0.5
        # TODO: should we cap to 0<=t<=40.0 ?
        return MitsubishiTemperature(t)

    @property
    def segment5_value(self) -> int:
        if self < 16:
            return 31-16
        if self > 31:
            return 31-31

        e = 31 - int(self)
        frac = self % 1
        return (0x10 if frac >= 0.5 else 0x00) + e

    @property
    def segment14_value(self) -> int:
        return 0x80 + int(self // 0.5)

@dataclass
class GeneralStates:
    """Parsed general AC states from device response"""
    power_on_off: PowerOnOff = PowerOnOff.OFF
    drive_mode: DriveMode = DriveMode.AUTO
    temperature: MitsubishiTemperature = MitsubishiTemperature(22.0)
    wind_speed: WindSpeed = WindSpeed.AUTO
    vertical_wind_direction_right: VerticalWindDirection = VerticalWindDirection.AUTO
    vertical_wind_direction_left: VerticalWindDirection = VerticalWindDirection.AUTO
    horizontal_wind_direction: HorizontalWindDirection = HorizontalWindDirection.AUTO
    dehum_setting: int = 0
    is_power_saving: bool = False
    wind_and_wind_break_direct: int = 0
    # Enhanced functionality based on SwiCago insights
    i_see_sensor: bool = False  # i-See sensor active flag
    mode_raw_value: int = 0     # Raw mode value before i-See processing
    wide_vane_adjustment: bool = False  # Wide vane adjustment flag (SwiCago wideVaneAdj)
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
        payload = data.hex()

        power_on_off = PowerOnOff.from_segment(format(data[8], "02x"))

        # Our payload structure starts with 'fc62013010' (5 bytes) then data begins
        # So data[0] is at position 10-11, data[1] at 12-13, etc.
        # data[5] (temp segment) would be at position 20-21
        # data[11] (direct temp) would be at position 32-33

        if len(payload) > 33:  # Check if we have data[11] position (32-33)
            temp_direct_raw = data[16]  # data[11] in SwiCago
            if temp_direct_raw != 0x00:
                # Direct temperature mode (SwiCago tempMode = true)
                temp_mode = True
                temperature = MitsubishiTemperature.from_segment(temp_direct_raw)
            else:
                # Segment-based temperature (SwiCago tempMode = false)
                temp_mode = False
                if len(payload) > 21:  # Check if we have data[5] position (20-21)
                    temperature = MitsubishiTemperature.from_segment(data[10])  # data[5] in SwiCago
        elif len(payload) > 21:  # Fallback to segment-based parsing if we don't have data[11]
            temperature = MitsubishiTemperature.from_segment(data[10])

        # Enhanced mode parsing with i-See sensor detection
        mode_byte = data[9] # data[4] in SwiCago
        drive_mode, i_see_active, raw_mode = GeneralStates.parse_mode_with_i_see(mode_byte)

        wind_speed = WindSpeed.from_segment(payload[22:24])  # data[6] in SwiCago
        right_vertical_wind_direction = VerticalWindDirection.from_segment(payload[24:26])  # data[7] in SwiCago
        left_vertical_wind_direction = VerticalWindDirection.from_segment(payload[40:42])

        # Enhanced wide vane parsing with adjustment flag (SwiCago)
        wide_vane_data = data[15] if len(payload) > 31 else 0  # data[10] in SwiCago
        horizontal_wind_direction = HorizontalWindDirection.from_segment(f"{wide_vane_data & 0x0F:02x}")  # Lower 4 bits
        wide_vane_adjustment = (wide_vane_data & 0xF0) == 0x80  # Upper 4 bits = 0x80

        # Extra states
        dehum_setting = data[17] if len(payload) > 35 else 0
        is_power_saving = data[18] > 0 if len(payload) > 37 else False
        wind_and_wind_break_direct = data[19] if len(payload) > 39 else 0

        # Analyze undocumented bits for research purposes
        undocumented_analysis = analyze_undocumented_bits(payload)

        return GeneralStates(
            power_on_off=power_on_off,
            temperature=temperature,
            drive_mode=drive_mode,
            wind_speed=wind_speed,
            vertical_wind_direction_right=right_vertical_wind_direction,
            vertical_wind_direction_left=left_vertical_wind_direction,
            horizontal_wind_direction=horizontal_wind_direction,
            dehum_setting=dehum_setting,
            is_power_saving=is_power_saving,
            wind_and_wind_break_direct=wind_and_wind_break_direct,
            # Enhanced functionality based on SwiCago
            i_see_sensor=i_see_active,
            mode_raw_value=raw_mode,
            wide_vane_adjustment=wide_vane_adjustment,
            temp_mode=temp_mode,
            undocumented_flags=undocumented_analysis if undocumented_analysis.get('suspicious_patterns') or undocumented_analysis.get('unknown_segments') else None,
        )

    @staticmethod
    def parse_mode_with_i_see(mode_byte: int) -> tuple[DriveMode, bool, int]:
        """Parse drive mode considering i-See sensor flag (SwiCago enhancement)

        Based on SwiCago implementation: i-See sensor is detected when mode > 0x08.
        The actual mode is extracted by subtracting 0x08 from the raw mode value.

        Args:
            mode_byte: Raw mode byte value from payload

        Returns:
            tuple of (drive_mode, i_see_active, raw_mode_value)
        """
        # Check if i-See sensor flag is set (mode > 0x08 as per SwiCago)
        i_see_active = mode_byte > 0x08

        # Extract actual mode by removing i-See flag if present
        # This matches SwiCago's logic: receivedSettings.iSee ? (data[4] - 0x08) : data[4]
        actual_mode_value = mode_byte - 0x08 if i_see_active else mode_byte

        # Map the mode value to DriveMode enum
        drive_mode = DriveMode.from_segment(actual_mode_value)

        return drive_mode, i_see_active, mode_byte



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
    def deserialize(cls, payload: bytes) -> SensorStates:
        if len(payload) < 21:
            raise ValueError("Payload too short")

        outside_temperature = MitsubishiTemperature.from_segment(payload[10])
        room_temperature = MitsubishiTemperature.from_segment(payload[12])
        thermal_sensor = (payload[19] & 0x01) != 0
        wind_speed_pr557 = 1 if (payload[20] & 0x01) == 1 else 0

        return SensorStates(
            outside_temperature=outside_temperature,
            room_temperature=room_temperature,
            thermal_sensor=thermal_sensor,
            wind_speed_pr557=wind_speed_pr557,
        )

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
    def deserialize(cls, payload_b: bytes, general_states: Optional[GeneralStates] = None) -> EnergyStates:
        """Parse energy/status states from hex payload (SwiCago group 06)

        Based on SwiCago implementation:
        - data[3] = compressor frequency
        - data[4] = operating status (boolean)

        Args:
            payload_b: payload bytes
            general_states: Optional general states for power estimation context
        """
        payload = payload_b.hex()
        if len(payload_b) < 12:  # Need at least enough bytes for data[4]
            raise ValueError("Payload too short")

        # Extract compressor frequency from data[3] (position 18-19 in hex string)
        compressor_frequency = int(payload[18:20], 16)

        # Extract operating status from data[4] (position 20-21 in hex string)
        operating = int(payload[20:22], 16) > 0

        # Estimate power consumption if we have context
        estimated_power = None
        if general_states:
            estimated_power = estimate_power_consumption(
                compressor_frequency,
                general_states.drive_mode,
                general_states.wind_speed
            )

        return EnergyStates(
            compressor_frequency=compressor_frequency,
            operating=operating,
            estimated_power_watts=estimated_power,
        )


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
    def deserialize(cls, payload_b: bytes) -> ErrorStates:
        payload = payload_b.hex()
        if len(payload) < 22:
            raise ValueError("Payload too short")

        code_head = payload[18:20]
        code_tail = payload[20:22]
        is_abnormal_state = not (code_head == '80' and code_tail == '00')
        error_code = f"{code_head}{code_tail}"

        return ErrorStates(
            is_abnormal_state=is_abnormal_state,
            error_code=error_code,
        )


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
        WindSpeed.AUTO: 50,      # Variable
        WindSpeed.LEVEL_1: 30,   # Low speed
        WindSpeed.LEVEL_2: 60,   # Medium-low
        WindSpeed.LEVEL_3: 90,   # Medium-high
        WindSpeed.LEVEL_FULL: 120, # High speed
    }
    
    fan_power = fan_power_map.get(fan_speed, 50)
    
    # Total estimated power
    total_power = compressor_power + fan_power + 20  # +20W for control electronics
    
    return round(total_power, 1)

def parse_code_values(code_values: List[bytes]) -> ParsedDeviceState:
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

def generate_general_command(general_states: GeneralStates, controls: Dict[str, bool]) -> str:
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
    segments['segment3'] = general_states.power_on_off.value
    segments['segment4'] = format(general_states.drive_mode.value, "02x")
    segments['segment6'] = f"{general_states.wind_speed.value:02x}"
    segments['segment7'] = f"{general_states.vertical_wind_direction_right.value:02x}"
    segments['segment13'] = f"{general_states.horizontal_wind_direction.value:02x}"
    segments['segment15'] = '41'  # checkInside: 41 true, 42 false
    
    segments['segment5'] = format(general_states.temperature.segment5_value, "02x")
    segments['segment14'] = format(general_states.temperature.segment14_value, "02x")
    
    # Build payload
    payload = '41013010'
    for i in range(16):
        segment_key = f'segment{i}'
        payload += segments.get(segment_key, '00')
    
    # Calculate and append FCC
    fcc = format(calc_fcc(bytes.fromhex(payload)), "02x")
    return "fc" + payload + fcc

def generate_extend08_command(general_states: GeneralStates, controls: Dict[str, bool]) -> str:
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
    segment_y = f"{general_states.dehum_setting:02x}" if controls.get('dehum') else '00'
    segment_z = '0A' if general_states.is_power_saving else '00'
    segment_a = f"{general_states.wind_and_wind_break_direct:02x}" if controls.get('wind_and_wind_break') else '00'
    buzzer_segment = '01' if controls.get('buzzer') else '00'
    
    payload = "4101301008" + segment_x + "0000" + segment_y + segment_z + segment_a + buzzer_segment + "0000000000000000"
    fcc = format(calc_fcc(bytes.fromhex(payload)), "02x")
    return 'fc' + payload + fcc
