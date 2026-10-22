import requests

from backend.safety.config import (
    LAT,
    LON
)


def get_weather():

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}"
        f"&longitude={LON}"
        f"&current=temperature_2m,"
        f"wind_speed_10m,"
        f"cloud_cover"
        f"&hourly=precipitation_probability,"
        f"precipitation,"
        f"temperature_2m"
        f"&wind_speed_unit=kmh"
        f"&timezone=Europe%2FParis"
        f"&forecast_days=1"
    )

    response = requests.get(
        url,
        timeout=10
    )

    response.raise_for_status()

    return response.json()