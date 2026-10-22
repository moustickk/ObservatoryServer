from datetime import datetime

from backend.safety.state import (
    is_safe,
    weather_data,
    last_weather_update
)


def get_device_state():

    age = -1

    if last_weather_update:

        age = int(
            (
                datetime.now()
                - last_weather_update
            ).total_seconds() / 60
        )

    return [
        {
            "Name": "IsSafe",
            "Value": is_safe
        },
        {
            "Name": "Wind",
            "Value": weather_data["wind"]
        },
        {
            "Name": "CloudCover",
            "Value": weather_data["clouds"]
        },
        {
            "Name": "RainProbability",
            "Value": weather_data["rain_probability"]
        },
        {
            "Name": "RainMM",
            "Value": weather_data["rain_mm"]
        },
        {
            "Name": "Temperature",
            "Value": weather_data["temperature"]
        },
        {
            "Name": "DataAgeMinutes",
            "Value": age
        }
    ]