from backend.safety.config import (
    MAX_WIND_SPEED,
    MAX_RAIN_PROBABILITY,
    MAX_RAIN_MM,
    MAX_CLOUD_COVER,
    MIN_TEMPERATURE
)


def evaluate_weather(
    wind,
    clouds,
    rain_probability,
    rain_mm,
    current_temp,
    forecast_temp
):

    reasons = []

    if wind > MAX_WIND_SPEED:
        reasons.append(
            f"VENT ({wind} km/h)"
        )

    if (
        rain_probability
        > MAX_RAIN_PROBABILITY
    ):
        reasons.append(
            f"PLUIE ({rain_probability}%)"
        )

    if rain_mm > MAX_RAIN_MM:
        reasons.append(
            f"PLUIE ({rain_mm} mm)"
        )

    if clouds > MAX_CLOUD_COVER:
        reasons.append(
            f"NUAGES ({clouds}%)"
        )

    if (
        current_temp <= MIN_TEMPERATURE
        or forecast_temp <= MIN_TEMPERATURE
    ):
        reasons.append(
            "RISQUE GEL"
        )

    return (
        len(reasons) == 0,
        reasons
    )