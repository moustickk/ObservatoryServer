"""Vue de sante agregee du serveur."""

from backend.common.constants import APP_NAME, VERSION


def health_snapshot(services):

    dome = services.dome.status()
    safety = services.safety.status()

    return {
        "application": APP_NAME,
        "version": VERSION,
        "simulation": services.simulation,
        "dome": {
            "state": dome["state"],
            "position": dome["position"],
            "alarm": dome["alarm"],
            "link": dome["link"],
            "mount": dome["mount"],
        },
        "safety": {
            "safe": safety.get("safe"),
            "status": safety.get("status"),
            "data_age_minutes": safety.get("data_age_minutes"),
            "last_weather_update": safety.get("last_weather_update"),
        },
    }
