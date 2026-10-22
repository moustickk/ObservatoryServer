import threading

from backend.safety.monitor import (
    weather_monitor
)

from backend.safety.runtime import (
    set_running
)


def start_monitor():

    set_running(True)

    threading.Thread(
        target=weather_monitor,
        daemon=True
    ).start()