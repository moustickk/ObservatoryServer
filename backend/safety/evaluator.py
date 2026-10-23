from backend.safety.config import (
    MAX_WIND_SPEED,
    MAX_RAIN_PROBABILITY,
    MAX_RAIN_MM,
    MAX_CLOUD_COVER,
    MIN_TEMPERATURE
)


def evaluate_weather(weather):

    reasons = []

    if weather["wind"] > MAX_WIND_SPEED:

        reasons.append(
            f"VENT ({weather['wind']} km/h)"
        )

    if (
        weather["rain_probability"]
        > MAX_RAIN_PROBABILITY
    ):

        reasons.append(
            f"PLUIE ({weather['rain_probability']}%)"
        )

    if weather["rain_mm"] > MAX_RAIN_MM:

        reasons.append(
            f"PLUIE ({weather['rain_mm']} mm)"
        )

    if weather["clouds"] > MAX_CLOUD_COVER:

        reasons.append(
            f"NUAGES ({weather['clouds']}%)"
        )

    if (
        weather["temperature"]
        <= MIN_TEMPERATURE
        or
        weather["forecast_temperature"]
        <= MIN_TEMPERATURE
    ):

        reasons.append(
            "RISQUE GEL"
        )

    return (
        len(reasons) == 0,
        reasons
    )