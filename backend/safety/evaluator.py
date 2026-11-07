"""Seuils de securite meteo.

Chaque depassement ajoute un motif explicite : c'est ce que l'operateur lit
dans `/api/health` et dans Alpaca. Un refus sans motif oblige a ouvrir les
journaux, ce qui n'est pas acceptable en pleine nuit.

Les valeurs venant du fournisseur sont deja des « pire cas » sur la fenetre
de prevision (voir `weather_provider`) : ici on ne fait que comparer.
"""

from backend.safety.config import current


def _number(weather, key):
    try:
        return float(weather.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_weather(weather, settings=None):
    """Compare une mesure aux seuils courants.

    `settings` permet aux tests de fixer les seuils ; par defaut, ils sont
    relus a chaque appel (application immediate, sans redemarrage).
    """

    settings = settings or current()

    reasons = []

    wind = _number(weather, "wind")
    gust = _number(weather, "wind_gust")
    rain_probability = _number(weather, "rain_probability")
    rain_mm = _number(weather, "rain_mm")
    clouds = _number(weather, "clouds")
    temperature = _number(weather, "temperature")
    forecast_temperature = _number(weather, "forecast_temperature")

    if wind > settings.max_wind_speed:
        reasons.append(f"VENT ({wind:g} km/h)")

    if gust > settings.max_wind_gust:
        reasons.append(f"RAFALES ({gust:g} km/h)")

    if rain_probability > settings.max_rain_probability:
        reasons.append(f"PLUIE ({rain_probability:g}%)")

    if rain_mm > settings.max_rain_mm:
        reasons.append(f"PLUIE ({rain_mm:g} mm)")

    if clouds > settings.max_cloud_cover:
        reasons.append(f"NUAGES ({clouds:g}%)")

    if temperature <= settings.min_temperature or forecast_temperature <= settings.min_temperature:
        reasons.append("RISQUE GEL")

    return (len(reasons) == 0, reasons)
