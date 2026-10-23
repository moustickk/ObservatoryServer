import time

from backend.dome.monitor import (
    sync_state
)


def monitor_loop():

    while True:

        sync_state()

        time.sleep(1)