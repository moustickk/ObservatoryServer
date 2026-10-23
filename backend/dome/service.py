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


class DomeService:

    def __init__(self):

        self.roof = RoofController(
            SERIAL_PORT,
            BAUDRATE
        )

    def open(self):

        log_open()

        return self.roof.open()

    def close(self):

        log_close()

        return self.roof.close()

    def stop(self):

        log_stop()

        return self.roof.stop()

    def status(self):

        return self.roof.status()