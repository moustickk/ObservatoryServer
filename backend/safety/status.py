"""Vue de la securite meteo, avec prise en compte d'un verdict force.

Le forçage sert aux essais : verifier la fermeture automatique, le refus
d'interlock ou le comportement de NINA sans attendre la pluie. Il est
**limite dans le temps** (10 minutes par defaut) et signale comme tel dans
tous les affichages, y compris Alpaca : un verdict force ne doit jamais etre
confondu avec une mesure reelle.
"""

from backend.safety import state


def _base():

    return {
        "safe": state.is_safe,
        "status": state.current_status,
        "weather": state.weather_data,
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

    status = _base()

    status["forced"] = forced is not None
    status["forced_value"] = forced
    status["forced_remaining_seconds"] = remaining

    if forced is not None:

        safe = forced == "SAFE"

        status["safe"] = safe
        status["status"] = (
            f"FORCE | {'SAFE' if safe else 'UNSAFE'} "
            f"(meteo simulee, {remaining // 60} min)"
        )

    return status
