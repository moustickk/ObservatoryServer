"""Boucle de surveillance meteo.

Phase 5 remplacera la logique de cache par un vrai comportement fail-safe
(donnees perimees ou API en panne => UNSAFE).
"""

import logging
import time

from backend.common.logs import safety_log
from backend.safety.config import CACHE_TIMEOUT_MINUTES, UPDATE_INTERVAL
from backend.safety.engine import process_weather
from backend.safety.state import (
    cache_valid,
    set_safe,
    set_unsafe,
    weather_age_minutes,
)
from backend.safety.weather_provider import get_weather


log = logging.getLogger(__name__)


def weather_monitor(stop_event=None):

    safety_log("Weather monitor started")

    while True:

        if stop_event is not None and stop_event.is_set():
            break

        try:

            weather = get_weather()

            log.debug("Meteo recue : %s", weather)

            process_weather(weather)

        except Exception as ex:

            if cache_valid(CACHE_TIMEOUT_MINUTES):

                age = weather_age_minutes()

                message = f"SAFE | CACHE UTILISE ({age} min)"

                set_safe(message)
                safety_log(message)

            else:

                set_unsafe(f"UNSAFE | {ex}")
                safety_log(f"UNSAFE | {ex}")
                log.warning("Meteo indisponible : %s", ex)

        if stop_event is not None:
            stop_event.wait(UPDATE_INTERVAL)
        else:
            time.sleep(UPDATE_INTERVAL)
