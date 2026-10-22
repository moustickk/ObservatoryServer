import threading

from backend.dome.runtime import (
    set_running
)


def start_monitor():

    set_running(True)

    threading.Thread(
        daemon=True
    ).start()