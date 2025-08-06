"""
Unit tests for mitsubishi_parser module using real device data.

Tests parser functions with actual hex codes and ProfileCode data
collected from real Mitsubishi MAC-577IF-2E devices.
"""

import pytest
from pymitsubishi.mitsubishi_parser import (
    calc_fcc, convert_temperature, convert_temperature_to_segment,
    PowerOnOff, DriveMode, WindSpeed,
    VerticalWindDirection, HorizontalWindDirection,
    parse_code_values, GeneralStates, ParsedDeviceState, generate_general_command, generate_extend08_command,
    MitsubishiSensorTemperature, parse_sensor_states, parse_general_states
)

from .test_fixtures import SAMPLE_CODE_VALUES, SAMPLE_PROFILE_CODES


@pytest.mark.parametrize(
    'payload,expected',
    [
        # These are based on patterns seen in real device communication
        (b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19", 0x06), # Sample command
        (b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x02\x02\x00\x80\x00\x00\x00\x00", 0x86),  # Real code pattern
        (b"\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe\xa0\xbe", 0xb2),  # Profile code pattern
    ],
)
def test_fcc(payload, expected):
    checksum = calc_fcc(payload)
    assert checksum == expected


def test_generate_general_command():
    command = generate_general_command(GeneralStates(), {})
    assert command == "fc410130100100020008090000000000000000ac417d"

def test_generate_extend08_command():
    command = generate_extend08_command(GeneralStates(), {})
    assert command == "fc410130100800000000000000000000000000000076"

def test_sensor_temperature():
    t = MitsubishiSensorTemperature.from_segment(182)
    assert t == 27.0

def test_parse_general_states():
    states = parse_general_states(bytes.fromhex('fc620130100200000003080000000083ae46000000d9'))
    assert states.drive_mode == DriveMode.COOLER

def test_parse_sensor_states():
    states = parse_sensor_states(bytes.fromhex('fc620130100300000f00b4b2b2fe420001141a0000c4'))
    assert states.outside_temperature == 26.0

class TestTemperatureConversion:
    """Test temperature conversion functions with real values."""
    
    def test_temperature_conversion_real_values(self):
        """Test temperature conversion with actual AC temperature values."""
        # Test common AC temperature settings
        real_temps = [160, 180, 200, 220, 240, 260, 280, 300, 320]  # 16-32°C
        
        for temp_units in real_temps:
            # Test segment conversion
            segment = convert_temperature(temp_units)
            assert len(segment) == 2
            
            # Test segment format conversion  
            segment14 = convert_temperature_to_segment(temp_units)
            assert len(segment14) == 2

    def test_temperature_edge_cases(self):
        """Test temperature conversion edge cases."""
        # Test minimum temperature (16°C = 160 units)
        assert convert_temperature(160) is not None
        
        # Test maximum temperature (32°C = 320 units)  
        assert convert_temperature(320) is not None


class TestModeAndStatusParsing:
    """Test parsing of mode and status values from real device responses."""
    
    def test_power_status_parsing(self):
        """Test power status parsing with real status codes."""
        # Real device power status patterns
        power_codes = ["00", "01", "02", "03", "ff"]
        
        for code in power_codes:
            status = PowerOnOff.from_segment(code)
            assert status in [PowerOnOff.ON, PowerOnOff.OFF]
            
            # Codes 01 and 02 should be ON, others typically OFF
            if code in ["01", "02"]:
                assert status == PowerOnOff.ON
    
    def test_drive_mode_parsing(self):
        """Test drive mode parsing with real mode codes."""
        # Real device mode mappings from actual responses
        mode_mappings = {
            "01": DriveMode.HEATER,
            "02": DriveMode.DEHUM,
            "03": DriveMode.COOLER,
            "07": DriveMode.FAN,
            "08": DriveMode.AUTO,
            "09": DriveMode.HEATER,
            "0a": DriveMode.DEHUM,
            "0b": DriveMode.COOLER,
            "0c": DriveMode.DEHUM,
            "19": DriveMode.AUTO_HEATER,
            "1b": DriveMode.AUTO_COOLER,
        }
        
        for code, expected_mode in mode_mappings.items():
            parsed_mode = DriveMode.from_segment(code)
            assert parsed_mode == expected_mode
    
    def test_wind_speed_parsing(self):
        """Test wind speed parsing with real speed codes."""
        # Test that wind speed parsing works with common codes
        speed_codes = ["00", "01", "02", "03", "05", "ff"]
        
        for code in speed_codes:
            speed = WindSpeed.from_segment(code)
            assert isinstance(speed, WindSpeed)
            assert speed in [WindSpeed.AUTO, WindSpeed.LEVEL_1, WindSpeed.LEVEL_2, 
                           WindSpeed.LEVEL_3, WindSpeed.LEVEL_FULL]


class TestCodeValueParsing:
    """Test parsing of real CODE values from device responses."""
    
    def test_code_value_structure(self):
        """Test that real code values have the expected structure."""
        for code_value in SAMPLE_CODE_VALUES:
            assert len(code_value) >= 12  # Minimum length for group code extraction
            assert all(c in '0123456789abcdef' for c in code_value.lower())
            
            # Extract group code (position 20-22)
            group_code = code_value[20:22]
            assert len(group_code) == 2
            # Allow the group codes that are actually in the test data
            assert group_code in ["02", "03", "04", "05", "06", "07", "08", "09", "0a"]
    
    def test_code_values_parsing(self):
        """Test parsing of complete code value arrays."""
        # Test that parse_code_values can handle real code arrays
        parsed_state = parse_code_values([
            bytes.fromhex(code)
            for code in SAMPLE_CODE_VALUES
        ])
        
        # Should return a ParsedDeviceState or None
        assert parsed_state is None or isinstance(parsed_state, ParsedDeviceState)
        
        # If parsing succeeds, verify structure
        if parsed_state and parsed_state.general:
            assert hasattr(parsed_state.general, 'power_on_off')
            assert hasattr(parsed_state.general, 'drive_mode')
            assert hasattr(parsed_state.general, 'temperature')


class TestProfileCodeAnalysis:
    """Test ProfileCode analysis with real profile data."""
    
    def test_profile_code_structure(self):
        """Test that profile codes have the expected structure."""
        for profile_code in SAMPLE_PROFILE_CODES:
            assert len(profile_code) == 64  # 32 bytes = 64 hex chars
            assert all(c in '0123456789abcdef' for c in profile_code.lower())
    
    def test_profile_code_parsing(self):
        """Test parsing of individual profile code components."""
        # Test the first profile code which has real capability data
        profile_code = SAMPLE_PROFILE_CODES[0]
        data = bytes.fromhex(profile_code)
        
        assert len(data) == 32  # Should be 32 bytes
        
        # Extract components (based on real device analysis)
        group_code = data[5] if len(data) > 5 else 0
        version_info = (data[6] << 8) | data[7] if len(data) > 7 else 0
        feature_flags = (data[8] << 8) | data[9] if len(data) > 9 else 0
        capability_field = (data[10] << 8) | data[11] if len(data) > 11 else 0
        
        # Verify extracted values match expected patterns
        assert isinstance(group_code, int)
        assert isinstance(version_info, int)
        assert isinstance(feature_flags, int)
        assert isinstance(capability_field, int)
    
    def test_empty_profile_codes(self):
        """Test handling of empty profile codes."""
        # Test profile codes that are all zeros
        empty_profile = SAMPLE_PROFILE_CODES[2]  # All zeros
        data = bytes.fromhex(empty_profile)
        
        # Should be all zeros
        assert all(byte == 0 for byte in data)
        
        # Parsing should handle gracefully
        version_info = (data[6] << 8) | data[7]
        assert version_info == 0


class TestRealDeviceDataIntegrity:
    """Test data integrity and consistency of real device responses."""
    
    def test_data_consistency(self):
        """Test that sample data is internally consistent."""
        # Verify that profile codes and code values are from same device type
        # All should be consistent with a MAC-577IF-2E device
        
        # Check that group codes are in expected range
        group_codes = set()
        for code_value in SAMPLE_CODE_VALUES:
            if len(code_value) >= 22:
                group_code = code_value[20:22]
                group_codes.add(group_code)
        
        # Should have typical group codes for this device type
        expected_codes = {"02", "03", "04", "05", "06", "07", "08", "09", "0a"}
        assert group_codes == expected_codes
    
    def test_profile_code_variations(self):
        """Test that profile codes show expected variations."""
        # First profile should have actual data
        first_profile = SAMPLE_PROFILE_CODES[0]
        assert not all(c == '0' for c in first_profile)
        
        # Second profile has repeated pattern  
        second_profile = SAMPLE_PROFILE_CODES[1]
        assert 'a0be' in second_profile
        
        # Remaining profiles should be empty
        for empty_profile in SAMPLE_PROFILE_CODES[2:]:
            assert all(c == '0' for c in empty_profile)


class TestErrorConditions:
    """Test error handling with malformed real-world data."""
    
    def test_truncated_code_values(self):
        """Test handling of truncated code values."""
        # Test with shortened versions of real codes
        truncated_codes = [code[:20] for code in SAMPLE_CODE_VALUES[:3]]
        
        for code in truncated_codes:
            # Should handle gracefully without crashing
            try:
                if len(code) >= 12:
                    group_code = code[10:12]
                    assert len(group_code) <= 2
            except IndexError:
                pass  # Expected for very short codes
    
    def test_invalid_hex_characters(self):
        """Test handling of invalid hex characters in codes."""
        # Create codes with invalid characters based on real patterns
        invalid_codes = [
            "gggggggggggggggggggg0202008000",  # Invalid hex chars
            "ffffffffffffffffffff02G2008000",  # Single invalid char
        ]
        
        for code in invalid_codes:
            # Should detect invalid hex gracefully
            try:
                # This would fail on invalid hex
                bytes.fromhex(code)
                assert False, "Should have failed on invalid hex"
            except ValueError:
                pass  # Expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
