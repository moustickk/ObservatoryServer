"""Previsions Open-Meteo, reduites au pire cas de la fenetre a venir.

Deux principes :

1. **On ne regarde pas seulement l'heure suivante.** Le fournisseur calcule
   le maximum de pluie, de rafales et le minimum de temperature sur toute la
   fenetre `lookahead_hours`. Ouvrir le toit parce que la prochaine heure est
   seche, alors qu'une averse est annoncee une heure plus tard, n'a pas de
   sens pour un toit qui met 47 s a se fermer mais qu'on laisse ouvert des
   heures.

2. **Le temps est celui du site, pas celui de la machine.** Open-Meteo est
   interroge en `Europe/Paris` et renvoie des heures locales sans decalage,
   ainsi que `utc_offset_seconds`. On decale l'horloge UTC de ce montant
   plutot que d'utiliser le fuseau de la machine : si le serveur tourne en
   UTC, ou sur un poste mal configure, on ne se trompe plus de fenetre.
   (`zoneinfo` a aussi ete ecarte : Windows n'embarque pas de base de
   fuseaux, il aurait fallu ajouter `tzdata`.)
"""

from datetime import datetime, timedelta, timezone

import requests

from backend.safety.config import LAT, LON, LOOKAHEAD_HOURS, WEATHER_MODEL


TIME_FORMAT = "%Y-%m-%dT%H:%M"

BASE_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}"
    f"&longitude={LON}"
    "&current="
    "temperature_2m,"
    "wind_speed_10m,"
    "wind_gusts_10m,"
    "cloud_cover"
    "&hourly="
    "precipitation_probability,"
    "precipitation,"
    "temperature_2m,"
    "wind_gusts_10m"
    "&wind_speed_unit=kmh"
    "&timezone=Europe%2FParis"
    "&forecast_days=1"
)


def build_url(model=None):
    """URL Open-Meteo pour un modele donne.

    « best_match » est le comportement par defaut du fournisseur : on ne
    l'ajoute pas, pour garder la requete minimale. Les autres modeles sont
    demandes explicitement.
    """

    model = model or WEATHER_MODEL

    if model and model != "best_match":
        return f"{BASE_URL}&models={model}"

    return BASE_URL


URL = build_url()


def local_now(data):
    """Heure locale du site, deduite du decalage fourni par Open-Meteo."""

    offset = data.get("utc_offset_seconds")

    if not isinstance(offset, (int, float)):
        raise ValueError("reponse Open-Meteo sans decalage horaire")

    return (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(seconds=offset)
    )


def _parse_time(value):

    try:
        return datetime.strptime(value, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def parse_weather(data, now=None):
    """Transforme une reponse Open-Meteo en mesures « pire cas ».

    Leve `ValueError` si la reponse est inexploitable : mieux vaut une erreur
    claire, traitee en UNSAFE par la surveillance, qu'un dict plein de zeros
    qui passerait pour du beau temps.
    """

    if not isinstance(data, dict):
        raise ValueError("reponse Open-Meteo illisible")

    if data.get("error"):
        raise ValueError(data.get("reason") or "erreur Open-Meteo")

    now = now or local_now(data)

    current = data.get("current") or {}
    hourly = data.get("hourly") or {}

    times = hourly.get("time") or []
    if not times:
        raise ValueError("reponse Open-Meteo sans serie horaire")

    parsed = [_parse_time(value) for value in times]

    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=LOOKAHEAD_HOURS)

    window = [
        index
        for index, moment in enumerate(parsed)
        if moment is not None and start <= moment <= end
    ]

    if not window:
        raise ValueError(
            f"aucune prevision entre {start:%Y-%m-%d %H:%M} et "
            f"{end:%Y-%m-%d %H:%M}"
        )

    def worst(series, pick, default=0.0):

        if not series:
            return default

        values = [
            series[index]
            for index in window
            if index < len(series) and series[index] is not None
        ]

        return pick(values) if values else default

    rain_probability = worst(
        hourly.get("precipitation_probability") or [],
        max,
    )

    rain_mm = worst(
        hourly.get("precipitation") or [],
        max,
    )

    forecast_temperature = worst(
        hourly.get("temperature_2m") or [],
        min,
    )

    hourly_gust = worst(
        hourly.get("wind_gusts_10m") or [],
        max,
    )

    wind_gust = max(
        hourly_gust,
        current.get("wind_gusts_10m") or 0,
    )

    return {
        "wind": current.get("wind_speed_10m", 0) or 0,
        "wind_gust": wind_gust,
        "clouds": current.get("cloud_cover", 0) or 0,
        "rain_probability": rain_probability,
        "rain_mm": rain_mm,
        "temperature": current.get("temperature_2m", 0) or 0,
        "forecast_temperature": forecast_temperature,
        "window_hours": LOOKAHEAD_HOURS,
    }


def get_weather():

    last_exception = None

    for _ in range(3):

        try:

            response = requests.get(URL, timeout=10)
            response.raise_for_status()

            return parse_weather(response.json())

        except Exception as ex:  # reseau, JSON, fenetre vide...
            last_exception = ex

    raise last_exception
