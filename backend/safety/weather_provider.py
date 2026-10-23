import requests
from datetime import datetime

from backend.safety.config import (
    LAT,
    LON
)

URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}"
    f"&longitude={LON}"
    f"&current="
    f"temperature_2m,"
    f"wind_speed_10m,"
    f"cloud_cover"
    f"&hourly="
    f"precipitation_probability,"
    f"precipitation,"
    f"temperature_2m"
    f"&wind_speed_unit=kmh"
    f"&timezone=Europe%2FParis"
    f"&forecast_days=1"
)


def get_weather():

    response = None
    last_exception = None

    for _ in range(3):

        try:

            response = requests.get(
                URL,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

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

            return {
                "wind": current.get(
                    "wind_speed_10m",
                    0
                ),
                "clouds": current.get(
                    "cloud_cover",
                    0
                ),
                "rain_probability": (
                    precip_probability[next_index]
                    if next_index < len(precip_probability)
                    else 0
                ),
                "rain_mm": (
                    precipitation[next_index]
                    if next_index < len(precipitation)
                    else 0
                ),
                "temperature": current.get(
                    "temperature_2m",
                    0
                ),
                "forecast_temperature": (
                    temperatures[next_index]
                    if next_index < len(temperatures)
                    else 0
                )
            }

        except Exception as ex:

            last_exception = ex

    raise last_exception