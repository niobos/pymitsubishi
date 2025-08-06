import pytest

from pymitsubishi import GeneralStates, PowerOnOff, DriveMode, WindSpeed, VerticalWindDirection, HorizontalWindDirection

@pytest.fixture
def general_states() -> GeneralStates:
    return GeneralStates(
        power_on_off=PowerOnOff.OFF,
        drive_mode=DriveMode.AUTO,
        temperature=22.0,
        wind_speed=WindSpeed.AUTO,
        vertical_wind_direction_right=VerticalWindDirection.AUTO,
        vertical_wind_direction_left=VerticalWindDirection.AUTO,
        horizontal_wind_direction=HorizontalWindDirection.AUTO,
        dehum_setting=0,
        is_power_saving=False,
        wind_and_wind_break_direct=0,
        i_see_sensor=False,
        mode_raw_value=0,
        wide_vane_adjustment=False,
        temp_mode=False,
        undocumented_flags={},
    )