from backend.common.logs import safety_log
from backend.safety import state

from backend.safety.status import (
    get_status
)

from backend.safety.device_state import (
    get_device_state
)


class SafetyService:

    def status(self):

        return get_status()

    def device_state(self):

        return get_device_state()

    def is_safe(self):

        return get_status()["safe"]

    # -- verdict force (essais) ------------------------------------------

    def force_status(self):

        forced, remaining = state.forced_state()

        return {
            "forced": forced is not None,
            "value": forced,
            "remaining_seconds": remaining,
            "indefinite": forced is not None and remaining is None,
        }

    def force(self, value, minutes=10):
        """Force SAFE ou UNSAFE, ou revient au reel.

        `minutes = 0` demande un SAFE illimite (mode intervention). C'est le
        seul verdict qui peut etre impose sans echeance : un UNSAFE illimite
        n'aurait pas de sens et masquerait une panne.
        """

        text = str(value or "").strip().upper()

        if text in ("", "AUTO", "REEL", "REAL"):

            state.set_forced(None, 0)
            state.notify_change()
            safety_log("METEO | retour au verdict reel")
            return self.force_status()

        if text not in ("SAFE", "UNSAFE"):

            raise ValueError("valeur attendue : auto, safe ou unsafe")

        try:
            minutes = int(minutes)
        except (TypeError, ValueError):

            raise ValueError("duree invalide") from None

        if minutes < 0:

            raise ValueError("duree invalide")

        if minutes == 0:

            if text != "SAFE":

                raise ValueError(
                    "le forcage illimite n'est autorise que pour SAFE"
                )

            seconds = 0
            duree = "ILLIMITE (mode intervention)"

        else:

            minutes = max(1, min(minutes, 60))
            seconds = minutes * 60
            duree = f"{minutes} min"

        state.set_forced(text, seconds)

        state.notify_change()

        safety_log(f"METEO | verdict FORCE : {text} pendant {duree}")

        return self.force_status()
