from datetime import datetime

from backend.safety.models import (
    WeatherData
)


def parse_weather(data):

    current = data.get(
        "current",
        {}
    )

    hourly = data.get(
        "hourly",
        {}
    )

    times = hourly.get(
        "time",
        []
    )

    precip_probability = hourly.get(
        "precipitation_probability",
        []
    )

    precipitation = hourly.get(
        "precipitation",
        []
    )

    temperatures = hourly.get(
        "temperature_2m",
        []
    )

    current_hour = datetime.now().strftime(
        "%Y-%m-%dT%H:00"
    )

    try:

        index = times.index(
            current_hour
        )

    except ValueError:

        index = 0

    next_index = min(
        index + 1,
        len(times) - 1
    )

    return WeatherData(
        wind=current.