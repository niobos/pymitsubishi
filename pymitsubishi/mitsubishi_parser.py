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
    horizontal_wind_direction: HorizontalWindDirection = HorizontalWindDirection.AUTO
    dehum_setting: int  = 0
    is_power_saving: bool  = False
    wind_and_wind_break_direct: int  = 0
    # Enhanced functionality based on SwiCago insights
    i_see_sensor: bool = False  # i-See sensor active flag
    wide_vane_adjustment: bool = False  # Wide vane adjustment flag (SwiCago wideVaneAdj)
    temp_mode: bool = False     # Direct temperature mode flag (SwiCago tempMode)

    @staticmethod
    def is_general_states_payload(data: bytes) -> bool:
        """Check if payload contains general states data"""
        if len(data) < 6:
            return False
        return data[1] in [0x62, 0x7b] and data[5] == 0x02

    @classmethod
    def deserialize(cls, data: bytes) -> GeneralStates:
        logger.debug(f"GeneralState.deserialize: {data.hex()}")
        if len(data) < 21:
            raise ValueError("Data too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        # Compared to the SwiCago implementation, we have an offset of 5:
        # SwiCago's data[0] is our data[5]
        obj._unknown0 = data[0:8]

        obj.power_on_off = PowerOnOff(data[8])

        # Enhanced mode parsing with i-See sensor detection
        obj.drive_mode = DriveMode(data[9] & 0x07)
        obj.i_see_sensor = bool(data[9] & 0x08)
        obj._unknown9 = data[9] & 0xF0

        obj.coarse_temperature = cls._from_coarse_temperature(data[10])

        obj.wind_speed = WindSpeed(data[11])
        obj.vertical_wind_direction = VerticalWindDirection(data[12])

        obj._unknown13 = data[13:15]

        wide_vane_data = data[15]
        obj.horizontal_wind_direction = HorizontalWindDirection(wide_vane_data & 0x0F)  # Lower 4 bits
        obj.wide_vane_adjustment = (wide_vane_data & 0xF0) == 0x80  # Upper 4 bits = 0x80

        obj.fine_temperature = cls._from_fine_temperature(data[16])

        obj.dehum_setting = data[17]

        obj.is_power_saving = data[18] > 0

        obj.wind_and_wind_break_direct = data[19]

        obj._unknown20 = data[20:]

        return obj

    def generate_general_command(self, controls: Dict[str, bool]) -> bytes:
        # Calculate segment 1 value (control flags)
        control_flags = 0
        if controls.get('power_on_off'):
            control_flags |= 0x01
        if controls.get('drive_mode'):
            control_flags |= 0x02
        if controls.get('temperature'):
            control_flags |= 0x04
        if controls.get('wind_speed'):
            control_flags |= 0x08
        if controls.get('up_down_wind_direct'):
            control_flags |= 0x10

        # Calculate segment 2 value
        control_flags2 = 0
        if controls.get('left_right_wind_direct'):
            control_flags2 |= 0x01
        if controls.get('outside_control', True):  # Default true
            control_flags2 |= 0x02

        # Build payload
        payload = b'\x41\x01\x30\x10\x01'
        payload += control_flags.to_bytes(1)
        payload += control_flags2.to_bytes(1)
        payload += self.power_on_off.value.to_bytes(1)
        payload += self.drive_mode.value.to_bytes(1)
        payload += self._to_coarse_temperature(self.coarse_temperature).to_bytes(1)
        payload += self.wind_speed.to_bytes(1)
        payload += self.vertical_wind_direction.value.to_bytes(1)
        payload += b'\0' * 5
        payload += self.horizontal_wind_direction.value.to_bytes(1)
        payload += self._to_fine_temperature(self.fine_temperature).to_bytes(1)
        payload += b'\x41'

        # Calculate and append FCC
        fcc = calc_fcc(payload).to_bytes(1)
        return b"\xfc" + payload + fcc

    def generate_extend08_command(self: GeneralStates, controls: Dict[str, bool]) -> bytes:
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

        payload = b"\x41\x01\x30\x10\x08"
        payload += segment_x_value.to_bytes(1)
        payload += b"\0\0"
        payload += (self.dehum_setting if controls.get('dehum') else 0).to_bytes(1)
        payload += b'\x0a' if self.is_power_saving else b'\x00'
        payload += (self.wind_and_wind_break_direct if controls.get('wind_and_wind_break') else 0).to_bytes(1)
        payload += b'\x01' if controls.get('buzzer') else b'\x00'
        payload += b"\x00" * 8
        fcc = calc_fcc(payload).to_bytes(1)
        return b'\xfc' + payload + fcc

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

        obj._unknown0 = data[0:10]
        obj.outside_temperature = GeneralStates._from_fine_temperature(data[10])
        obj._unknown11 = data[11]
        obj.room_temperature = GeneralStates._from_fine_temperature(data[12])
        obj._unknown13 = data[13:19]
        obj.thermal_sensor = (data[19] & 0x01) != 0
        obj._unknown19 = data[19] & 0xf7
        obj.wind_speed_pr557 = 1 if (data[20] & 0x01) == 1 else 0
        obj._unknown20 = data[20] & 0xf7

        if len(data) > 21:
            obj._unknown21 = data[21:]

        return obj


@dataclass
class EnergyStates:
    """Parsed energy and operational states from device response"""
    compressor_frequency: Optional[int] = None  # Raw compressor frequency value
    operating: int = False  # True if heat pump is actively operating

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
        if len(data) < 12:  # Need at least enough bytes for data[4]
            raise ValueError("Payload too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        obj._unknown0 = data[0:9]
        obj.compressor_frequency = data[9]
        obj.operating = data[10]
        obj._unknown11 = data[11:]

        return obj


@dataclass 
class ErrorStates:
    """Parsed error states from device response"""
    error_code: int = 0x8000

    @staticmethod
    def is_error_states_payload(payload: bytes) -> bool:
        """Check if payload contains error states data"""
        if len(payload) < 6:
            return False
        return payload[1] in [0x62, 0x7b] and payload[5] == 0x04

    @classmethod
    def deserialize(cls, data: bytes) -> ErrorStates:
        if len(data) < 11:
            raise ValueError("Payload too short")

        calculated_fcc = calc_fcc(data[1:-1])
        if calculated_fcc != data[-1]:
            raise ValueError(f"Checksum mismatch: got 0x{data[-1]:02x}, expected 0x{calculated_fcc:02x}")

        obj = cls.__new__(cls)

        obj._unknown0 = data[0:9]
        obj.error_code = int.from_bytes(data[9:11], byteorder="big", signed=False)
        if len(data) > 11:
            obj._unknown11 = data[11:]

        return obj

    @property
    def is_abnormal_state(self):
        return self.error_code != 0x8000


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
            }

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

    def estimate_power_consumption(self) -> float:
        """Estimate power consumption based on compressor frequency and operational parameters

        This is a rough estimation based on empirical data from heat pump literature.
        Actual consumption varies significantly based on outdoor conditions, efficiency rating, etc.

        Returns:
            Estimated power consumption in Watts
        """
        if self.energy.compressor_frequency == 0:
            # Unit is not actively operating - only standby power
            return 10.0  # Typical standby consumption

        # Base power estimation from compressor frequency
        # This is a rough linear approximation - real curves are more complex
        frequency_factor = self.energy.compressor_frequency / 255.0  # Normalize to 0-1

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

        base_power = mode_base_watts.get(self.general.drive_mode, 1000)

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

        fan_power = fan_power_map.get(self.general.wind_speed, 50)

        # Total estimated power
        total_power = compressor_power + fan_power + 20  # +20W for control electronics

        return round(total_power, 1)


def calc_fcc(payload: bytes) -> int:
    """Calculate FCC checksum for Mitsubishi protocol payload"""
    return 0x100 - (sum(payload[0:20]) % 0x100)  # TODO: do we actually need to limit this to 20 bytes?
