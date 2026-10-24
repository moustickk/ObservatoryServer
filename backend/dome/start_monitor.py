import threading

from backend.dome.monitor_loop import (
    monitor_loop
)


def start_monitor():

    threading.Thread(
        target=monitor_loop,
        daemon=True
    ).start()