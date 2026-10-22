import threading

from backend.safety.monitor import (
    weather_monitor
)


def start_safety():

    threading.Thread(
        target=weather_monitor,
        daemon=True
    ).start()