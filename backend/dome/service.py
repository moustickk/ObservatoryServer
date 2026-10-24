import time

from backend.dome.config import (
    SERIAL_PORT,
    BAUDRATE
)

from backend.dome.serial_controller import (
    RoofController
)

from backend.dome.logging import (
    log_open,
    log_close,
    log_stop
)

from backend.dome.state import (
    state_data,
    save_current_state,
    compute_position
)

from backend.mount.api import (
    ensure_mount_parked
)


class DomeService:

    def __init__(self):

        self.roof = RoofController(
            SERIAL_PORT,
            BAUDRATE
        )

        self.last_motion = "CLOSING"

    def open(self):

        if not ensure_mount_parked():

            return False

        self.last_motion = "OPENING"

        position = compute_position()

        if position < 0:

            position = 0

        response = self.roof.open()

        log_open()

        state_data["state"] = "OPENING"
        state_data["position"] = position
        state_data["timestamp"] = time.time()

        save_current_state()

        return response

    def close(self):

        if not ensure_mount_parked():

            return False

        self.last_motion = "CLOSING"

        position = compute_position()

        if position < 0:

            position = 100

        response = self.roof.close()

        log_close()

        state_data["state"] = "CLOSING"
        state_data["position"] = position
        state_data["timestamp"] = time.time()

        save_current_state()

        return response

    def stop(self):

        state_data["position"] = (
            compute_position()
        )

        response = self.roof.stop()

        log_stop()

        state_data["state"] = (
            self.last_motion
        )

        save_current_state()

        return response

    def status(self):

        return self.roof.status()