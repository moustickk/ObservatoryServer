import threading
import time

from datetime import datetime


state_lock = threading.Lock()

is_safe = False

current_status = "Initialisation..."

last_weather_update = None

last_good_timestamp = None

last_good_data = None

weather_data = {
    "wind": 0,
    "wind_gust": 0,
    "clouds": 0,
    "rain_probability": 0,
    "rain_mm": 0,
    "temperature": 0
}


# Verdict force depuis l'interface, pour les essais. Toujours limite dans le
# temps : on ne veut pas qu'un oubli laisse le toit ouvert sous la pluie (ou
# ferme) pour de bon.
forced_value = None

forced_until = 0.0


def _now():
    return time.time()


def set_forced(value, seconds):

    global forced_value
    global forced_until

    with state_lock:

        if value is None:

            forced_value = None
            forced_until = 0.0
            return

        forced_value = str(value).strip().upper()
        forced_until = _now() + max(0.0, float(seconds))


def forced_state():
    """Retourne (valeur, secondes restantes), ou (None, 0)."""

    global forced_value
    global forced_until

    with state_lock:

        if forced_value is None:

            return None, 0

        remaining = forced_until - _now()

        if remaining <= 0:

            forced_value = None
            forced_until = 0.0
            return None, 0

        return forced_value, int(remaining)


def weather_age_minutes():

    if last_good_timestamp is None:

        return -1

    return int(
        (
            datetime.now()
            - last_good_timestamp
        ).total_seconds() / 60
    )


def update_cache(data):

    global last_good_data
    global last_good_timestamp

    last_good_data = data

    last_good_timestamp = datetime.now()


def cache_valid(cache_timeout_minutes):

    if last_good_timestamp is None:

        return False

    age = (
        datetime.now()
        - last_good_timestamp
    ).total_seconds() / 60

    return age <= cache_timeout_minutes


def set_safe(status):

    global is_safe
    global current_status

    with state_lock:

        is_safe = True

        current_status = status


def set_unsafe(status):

    global is_safe
    global current_status

    with state_lock:

        is_safe = False

        current_status = status