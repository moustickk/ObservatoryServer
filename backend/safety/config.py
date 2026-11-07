"""Configuration meteo, relue a chaque usage.

Les seuils et le modele ne sont plus figes a l'import : `current()` construit
un instantane depuis `settings_manager` a chaque evaluation ou telechargement.
Un enregistrement dans l'interface s'applique donc sans redemarrage.

L'instantane est fige (`frozen=True`) : une evaluation ne peut pas voir un
melange de deux configurations si un reglage change pendant qu'elle tourne.
"""

import threading

from dataclasses import dataclass

from backend.common.settings_manager import (
    DEFAULT_SETTINGS,
    as_dict,
)


LAT = 48.119722
LON = -1.200556


@dataclass(frozen=True)
class WeatherSettings:
    """Seuils et parametres meteo, coherents entre eux."""

    max_wind_speed: float
    max_wind_gust: float
    max_rain_probability: float
    max_rain_mm: float
    max_cloud_cover: float
    min_temperature: float
    lookahead_hours: int
    max_weather_age_minutes: float
    cache_timeout_minutes: float
    update_interval: float
    model: str


def _number(data, key):

    try:
        return float(data.get(key, DEFAULT_SETTINGS[key]))
    except (TypeError, ValueError):
        return float(DEFAULT_SETTINGS[key])


def _integer(data, key):

    try:
        return int(data.get(key, DEFAULT_SETTINGS[key]))
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS[key])


def current():
    """Instantane des reglages meteo courants."""

    data = as_dict()

    return WeatherSettings(
        max_wind_speed=_number(data, "max_wind_speed"),
        max_wind_gust=_number(data, "max_wind_gust"),
        max_rain_probability=_number(data, "max_rain_probability"),
        max_rain_mm=_number(data, "max_rain_mm"),
        max_cloud_cover=_number(data, "max_cloud_cover"),
        min_temperature=_number(data, "min_temperature"),
        lookahead_hours=_integer(data, "lookahead_hours"),
        max_weather_age_minutes=_number(data, "weather_max_age_minutes"),
        cache_timeout_minutes=_number(data, "weather_cache_minutes"),
        update_interval=_number(data, "weather_update_seconds"),
        model=str(
            data.get("weather_model")
            or DEFAULT_SETTINGS["weather_model"]
        ),
    )


# Reveille la boucle meteo apres un changement de reglage : le nouveau seuil,
# le nouveau modele ou le nouvel intervalle doit s'appliquer au cycle suivant.
CHANGED = threading.Event()


def notify_changed():
    CHANGED.set()
