"""
Unit tests for mitsubishi_parser module using real device data.

Tests parser functions with actual hex codes and ProfileCode data
collected from real Mitsubishi MAC-577IF-2E devices.
"""

import pytest

from pymitsubishi import SensorStates
from pymitsubishi.mitsubishi_parser import (
    calc_fcc,
    GeneralStates, ParsedDeviceState,
)

from .test_fixtures import SAMPLE_CODE_VALUES


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
    command = GeneralStates().generate_general_command({})
    assert command.hex() == "fc410130100100020000090000000000000000ac4185"

def test_generate_extend08_command():
    command = GeneralStates().generate_extend08_command({})
    assert command.hex() == "fc410130100800000000000000000000000000000076"

def test_parse_sensor_states():
    states = SensorStates.deserialize(bytes.fromhex('fc620130100300000f00b4b2b2fe420001141a0000c4'))
    assert states.outside_temperature == 26.0
    assert states.room_temperature == 25.0

class TestCodeValueParsing:
    """Test parsing of real CODE values from device responses."""

    def test_code_values_parsing(self):
        """Test parsing of complete code value arrays."""
        # Test that parse_code_values can handle real code arrays
        parsed_state = ParsedDeviceState.parse_code_values([
            bytes.fromhex(code)
            for code in SAMPLE_CODE_VALUES
        ])
        
        # Should return a ParsedDeviceState or None
        assert isinstance(parsed_state, ParsedDeviceState)
        
        # If parsing succeeds, verify structure
        if parsed_state and parsed_state.general:
            assert hasattr(parsed_state.general, 'power_on_off')
            assert hasattr(parsed_state.general, 'drive_mode')
            assert hasattr(parsed_state.general, 'temperature')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
