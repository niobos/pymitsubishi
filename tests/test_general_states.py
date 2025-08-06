import pytest

from pymitsubishi import GeneralStates, DriveMode, WindSpeed, VerticalWindDirection, HorizontalWindDirection


@pytest.mark.parametrize(
    'data_hex, mode',
    [
        ('fc620130100200000108080000000083ae46000000d3', DriveMode.AUTO),
        ('fc62013010020000010b070000000083b046000000cf', DriveMode.COOLER),
        ('fc62013010020000010a070000000083b032000000e4', DriveMode.DEHUM),
        ('fc620130100200000109090000000083ac28000000f1', DriveMode.HEATER),
        ('fc620130100200000107070000000083b028000000f1', DriveMode.FAN),
    ],
)
def test_parse_general_states_mode(data_hex, mode):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.drive_mode == mode

@pytest.mark.parametrize(
    'data_hex, temp',
    [
        ('fc62013010020000010b070000000083b046000000cf', 24.0),
        ('fc62013010020000010b090000000083ac46000000d1', 22.0),
    ],
)
def test_parse_general_states_temp(data_hex, temp):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.temperature == temp

@pytest.mark.parametrize(
    'data_hex, wind_speed',
    [
        ('fc62013010020000010b070000000083b046000000cf', WindSpeed.AUTO),
        ('fc62013010020000010b070100000083b046000000ce', WindSpeed.LEVEL_1),  # silent
        ('fc62013010020000010b070200000083b046000000cd', WindSpeed.LEVEL_2),  # 1
        ('fc62013010020000010b070500000083b046000000ca', WindSpeed.LEVEL_FULL),  # 3
        ('fc62013010020000010b070600000083b046000000c9', WindSpeed.LEVEL_FULL),  # 4
    ],
)
def test_parse_general_states_wind_speed(data_hex, wind_speed):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.wind_speed == wind_speed

@pytest.mark.parametrize(
    'data_hex, lvane, rvane',
    [
        ('fc62013010020000010b070000000083b046000000cf', VerticalWindDirection.AUTO, VerticalWindDirection.AUTO),
        ('fc62013010020000010b070001000083b046000000ce', VerticalWindDirection.V1, VerticalWindDirection.AUTO),
        ('fc62013010020000010b070005000083b046000000ca', VerticalWindDirection.V5, VerticalWindDirection.AUTO),
        ('fc62013010020000010b070005000083b046000000ca', VerticalWindDirection.V5, VerticalWindDirection.V1),
        ('fc62013010020000010b070007000083b046000000c8', VerticalWindDirection.SWING, VerticalWindDirection.V1),
        ('fc62013010020000010b070007000083b046000000c8', VerticalWindDirection.SWING, VerticalWindDirection.V5),
        ('fc62013010020000010b070007000083b046000000c8', VerticalWindDirection.AUTO, VerticalWindDirection.SWING),
    ],
)
def test_parse_general_states_vertical_vane(data_hex, lvane, rvane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.vertical_wind_direction_left == lvane
    assert states.vertical_wind_direction_right == rvane

@pytest.mark.parametrize(
    'data_hex, vane',
    [
        ('fc62013010020000010b070000000081b046000000d1', HorizontalWindDirection.L),
        ('fc62013010020000010b070000000082b046000000d0', HorizontalWindDirection.LC),
        ('fc62013010020000010b070000000083b046000000cf', HorizontalWindDirection.C),
        ('fc62013010020000010b070000000084b046000000ce', HorizontalWindDirection.CR),
        ('fc62013010020000010b070000000085b046000000cd', HorizontalWindDirection.R),
        ('fc62013010020000010b070000000088b046000000ca', HorizontalWindDirection.LR),  # split
        ('fc62013010020000010b07000000008cb046000000c6', HorizontalWindDirection.LCR_S),  # sweep
    ],
)
def test_parse_general_states_horizontal_vane(data_hex, vane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.horizontal_wind_direction == vane

@pytest.mark.parametrize(
    'data_hex, isee_hvane',
    [
        ('fc62013010020000010b070000000083b046000000cf', 'off'),
        ('fc62013010020000010b070000000080b046000100d1', 'avoid'),
        ('fc62013010020000010b070000000080b046000200d0', 'aim'),
        ('fc62013010020000010b070000000080b046000000d2', 'even'),
    ],
)
def test_parse_general_states_isee(data_hex, isee_hvane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.i_see_sensor == isee_hvane

def test_parse_general_states_purifier(data_hex, purifier):
    # TODO: find out where the purifier bit is located
    on  = ['fc62013010020000010b070000000083b046000000cf', 'fc620130100300000d00a8aeaefe42000114520000a2', 'fc6201301004000000800000000000000000000000d9', 'fc620130100500000000000000000000000000000058', 'fc620130100600000000001d5178000042000000002f', 'fc620130100900000001000000000000000000000053']
    off = ['fc62013010020000010b070000000083b046000000cf', 'fc620130100300000d00a8aeaefe42000114530000a1', 'fc6201301004000000800000000000000000000000d9', 'fc620130100500000000000000000000000000000058', 'fc620130100600000000001d5178000042000000002f', 'fc620130100900000001000000000000000000000053']
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    #assert states.purifier == purifier

