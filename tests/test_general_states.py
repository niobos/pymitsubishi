import pytest

from pymitsubishi import GeneralStates, DriveMode, WindSpeed, VerticalWindDirection, HorizontalWindDirection, PowerOnOff


@pytest.mark.parametrize(
    'data_hex, power, mode',
    [  #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        ('fc62013010020000000b070000000083b046000000d0', PowerOnOff.OFF, DriveMode.COOLER),
        ('fc620130100200000108080000000083ae46000000d3', PowerOnOff.ON, DriveMode.AUTO),
        ('fc62013010020000010b070000000083b046000000cf', PowerOnOff.ON, DriveMode.COOLER),
        ('fc62013010020000010a070000000083b032000000e4', PowerOnOff.ON, DriveMode.DEHUM),
        ('fc620130100200000109090000000083ac28000000f1', PowerOnOff.ON, DriveMode.HEATER),
        ('fc620130100200000107070000000083b028000000f1', PowerOnOff.ON, DriveMode.FAN),
        ('fc6201301002000001080b0000000083a846000000d6', PowerOnOff.ON, DriveMode.AUTO),  # auto, 20º => cooling
        ('fc620130100200000108010000000083bc46000000cc', PowerOnOff.ON, DriveMode.AUTO),  # auto, 30º => heating
    ],
)
def test_parse_general_states_mode(data_hex, power, mode):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.power_on_off == power
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
        ('fc62013010020000010b070000000083b046000000cf', 0),  # auto
        ('fc62013010020000010b070100000083b046000000ce', 1),  # "silent"
        ('fc620130100200000107070200000083b028000000ef', 2),  # 1 bar
        ('fc620130100200000107070300000083b028000000ee', 3),  # 2 bars
        # no 4 in my system
        ('fc620130100200000107070500000083b028000000ec', 5),  # 3 bars
        ('fc620130100200000107070600000083b028000000eb', 6),  # 4 bars, max
    ],
)
def test_parse_general_states_wind_speed(data_hex, wind_speed):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.wind_speed == wind_speed

@pytest.mark.parametrize(
    'data_hex, vane',
    [  #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        ('fc620130100200000107070000000083b028000000f1', VerticalWindDirection.AUTO),
        ('fc620130100200000107070001000083b028000000f0', VerticalWindDirection.V1),
        ('fc620130100200000107070002000083b028000000ef', VerticalWindDirection.V2),
        ('fc620130100200000107070005000083b028000000ec', VerticalWindDirection.V5),
        ('fc620130100200000107070007000083b028000000ea', VerticalWindDirection.SWING),
    ],
)
def test_parse_general_states_vertical_vane(data_hex, vane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.vertical_wind_direction == vane

@pytest.mark.parametrize(
    'data_hex, vane',
    [
        ('fc62013010020000010b070000000081b046000000d1', HorizontalWindDirection.L),
        ('fc62013010020000010b070000000082b046000000d0', HorizontalWindDirection.LS),
        ('fc62013010020000010b070000000083b046000000cf', HorizontalWindDirection.C),
        ('fc62013010020000010b070000000084b046000000ce', HorizontalWindDirection.RS),
        ('fc62013010020000010b070000000085b046000000cd', HorizontalWindDirection.R),
        ('fc62013010020000010b070000000088b046000000ca', HorizontalWindDirection.LR),  # split
        ('fc62013010020000010b07000000008cb046000000c6', HorizontalWindDirection.LCR_S),  # sweep
    ],
)
def test_parse_general_states_horizontal_vane(data_hex, vane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.horizontal_wind_direction == vane

@pytest.mark.parametrize(
    'data_hex, hvane, isee_hvane',
    [  #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        ('fc62013010020000010b070000000083b046000000cf', HorizontalWindDirection.C, 0),  # off
        ('fc62013010020000010b070000000080b046000100d1', HorizontalWindDirection.AUTO, 1),  # avoid
        ('fc62013010020000010b070000000080b046000200d0', HorizontalWindDirection.AUTO, 2),  # aim
        ('fc62013010020000010b070000000080b046000000d2', HorizontalWindDirection.AUTO, 0),  # wide
    ],
)
def test_parse_general_states_hvane_isee(data_hex, hvane, isee_hvane):
    states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    assert states.horizontal_wind_direction == hvane
    assert states.wind_and_wind_break_direct == isee_hvane

def test_parse_general_states_purifier():
    # TODO: find out where the purifier bit is located
    on  = ['fc62013010020000010b070000000083b046000000cf', 'fc620130100300000d00a8aeaefe42000114520000a2', 'fc6201301004000000800000000000000000000000d9', 'fc620130100500000000000000000000000000000058', 'fc620130100600000000001d5178000042000000002f', 'fc620130100900000001000000000000000000000053']
    off = ['fc62013010020000010b070000000083b046000000cf', 'fc620130100300000d00a8aeaefe42000114530000a1', 'fc6201301004000000800000000000000000000000d9', 'fc620130100500000000000000000000000000000058', 'fc620130100600000000001d5178000042000000002f', 'fc620130100900000001000000000000000000000053']
    #states = GeneralStates.deserialize(bytes.fromhex(data_hex))
    #assert states.purifier == purifier

