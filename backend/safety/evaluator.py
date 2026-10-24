"""Seuils de securite meteo.

Chaque depassement ajoute un motif explicite : c'est ce que l'operateur lit
dans `/api/health` et dans Alpaca. Un refus sans motif oblige a ouvrir les
journaux, ce qui n'est pas acceptable en pleine nuit.

Les valeurs venant du fournisseur sont deja des « pire cas » sur la fenetre
de prevision (voir `weather_provider`) : ici on ne fait que comparer.
"""

from backend.safety.config import (
    MAX_CLOUD_COVER,
    MAX_RAIN_MM,
    MAX_RAIN_PROBABILITY,
    MAX_WIND_GUST,
    MAX_WIND_SPEED,
    MIN_TEMPERATURE,
)


def _number(weather, key):
    try:
        return float(weather.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_weather(weather):

    reasons = []

    wind = _number(weather, "wind")
    gust = _number(weather, "wind_gust")
    rain_probability = _number(weather, "rain_probability")
    rain_mm = _number(weather, "rain_mm")
    clouds = _number(weather, "clouds")
    temperature = _number(weather, "temperature")
    forecast_temperature = _number(weather, "forecast_temperature")

    if wind > MAX_WIND_SPEED:
        reasons.append(f"VENT ({wind:g} km/h)")

    if gust > MAX_WIND_GUST:
        reasons.append(f"RAFALES ({gust:g} km/h)")

    if rain_probability > MAX_RAIN_PROBABILITY:
        reasons.append(f"PLUIE ({rain_probability:g}%)")

    if rain_mm > MAX_RAIN_MM:
        reasons.append(f"PLUIE ({rain_mm:g} mm)")

    if clouds > MAX_CLOUD_COVER:
        reasons.append(f"NUAGES ({clouds:g}%)")

    if temperature <= MIN_TEMPERATURE or forecast_temperature <= MIN_TEMPERATURE:
        reasons.append("RISQUE GEL")

    return (len(reasons) == 0, reasons)
