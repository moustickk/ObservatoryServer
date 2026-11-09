"""Vue de la securite meteo, avec prise en compte d'un verdict force.

Le forçage sert aux essais : verifier la fermeture automatique, le refus
d'interlock ou le comportement de NINA sans attendre la pluie. Le forçage
temporaire est **limite dans le temps** (10 minutes par defaut). Le mode
**SAFE illimite** est reserve aux interventions : il reste actif jusqu'au
retour manuel au reel (ou au redemarrage du serveur) et est signale comme tel
dans tous les affichages, y compris Alpaca : un verdict force ne doit jamais
etre confondu avec une mesure reelle.
"""

from backend.safety import state
from backend.safety.config import current


def _base():

    return {
        "safe": state.is_safe,
        "status": state.current_status,
        "weather": state.weather_data,
        "weather_model": current().model,
        "data_age_minutes": (
            state.weather_age_minutes()
        ),
        "last_weather_update": (
            state.last_weather_update.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if state.last_weather_update
            else None
        ),
    }


def get_status():

    forced, remaining = state.forced_state()

    indefinite = forced is not None and remaining is None

    status = _base()

    status["forced"] = forced is not None
    status["forced_value"] = forced
    status["forced_remaining_seconds"] = remaining
    status["forced_indefinite"] = indefinite

    if forced is not None:

        safe = forced == "SAFE"

        echeance = (
            "illimite, retour manuel"
            if indefinite
            else f"{remaining // 60} min"
        )

        status["safe"] = safe
        status["status"] = (
            f"FORCE | {'SAFE' if safe else 'UNSAFE'} "
            f"(meteo simulee, {echeance})"
        )

    return status
