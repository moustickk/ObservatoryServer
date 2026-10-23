from backend.safety.status import (
    get_status
)

from backend.safety.device_state import (
    get_device_state
)


class SafetyService:

    def status(self):

        return get_status()

    def device_state(self):

        return get_device_state()

    def is_safe(self):

        return get_status()["safe"]