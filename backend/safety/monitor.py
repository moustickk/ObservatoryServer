"""Boucle de surveillance meteo, fail-safe.

Regle de securite : **une panne du fournisseur ne vaut jamais SAFE**.

L'ancienne version, en cas d'echec reseau, declarait SAFE des que le cache
avait moins de 30 minutes — sans regarder ce que disait ce cache. Une mesure
UNSAFE suivie d'une coupure reseau faisait donc passer le toit en SAFE, ce
qui est exactement l'inverse du comportement attendu.

Desormais, en cas d'echec :

 - sans aucune mesure : UNSAFE (on ne sait rien) ;
 - mesure trop ancienne : UNSAFE (elle ne decrit plus le present) ;
 - mesure recente : on **rejoue son evaluation** et on conserve son verdict,
   en indiquant l'age du cache. Une mesure recente disant « dangereux »
   reste dangereuse.
"""

import logging
import time

from backend.common.logs import safety_log
from backend.safety import state
from backend.safety.config import CHANGED, current
from backend.safety.engine import process_weather
from backend.safety.evaluator import evaluate_weather
from backend.safety.state import set_safe, set_unsafe, weather_age_minutes
from backend.safety.weather_provider import get_weather


log = logging.getLogger(__name__)


def failure_decision(cached, age_minutes, max_age_minutes=None):
    """Verdict quand le fournisseur est injoignable.

    Retourne `(safe, message)`. Ne retourne jamais `True` sans avoir evalue
    une mesure, et jamais `True` sur une mesure perimee.
    """

    if max_age_minutes is None:
        max_age_minutes = current().max_weather_age_minutes

    if cached is None or age_minutes is None or age_minutes < 0:
        return False, "UNSAFE | AUCUNE DONNEE METEO"

    if age_minutes > max_age_minutes:
        return False, (
            f"UNSAFE | DONNEES PERIMEES "
            f"({age_minutes} min > {max_age_minutes} min)"
        )

    safe, reasons = evaluate_weather(cached)

    if safe:
        return True, f"SAFE | CACHE {age_minutes} min"

    return False, (
        f"UNSAFE | CACHE {age_minutes} min [{', '.join(reasons)}]"
    )


def _wait(seconds, stop_event):
    """Attend le prochain cycle, mais se reveille si un reglage change."""

    deadline = time.monotonic() + max(0.0, float(seconds))

    while True:

        if stop_event is not None and stop_event.is_set():
            return

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return

        if CHANGED.wait(timeout=min(remaining, 1.0)):
            CHANGED.clear()
            return


def weather_monitor(stop_event=None):

    safety_log("Weather monitor started")

    while True:

        if stop_event is not None and stop_event.is_set():
            break

        settings = current()

        try:

            weather = get_weather()

            log.debug("Meteo recue : %s", weather)

            process_weather(weather)

        except Exception as ex:

            age = weather_age_minutes()

            safe, message = failure_decision(
                state.last_good_data,
                age,
                settings.max_weather_age_minutes,
            )
            message = f"{message} ({ex})"

            if safe:
                set_safe(message)
                log.warning("%s", message)
            else:
                set_unsafe(message)
                log.error("%s", message)

            safety_log(message)

        _wait(settings.update_interval, stop_event)
