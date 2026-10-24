import threading

from datetime import datetime


state_lock = threading.Lock()

is_safe = False

current_status = "Initialisation..."

last_weather_update = None

last_good_timestamp = None

last_good_data = None

weather_data = {
    "wind": 0,
    "clouds": 0,
    "rain_probability": 0,
    "rain_mm": 0,
    "temperature": 0
}


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