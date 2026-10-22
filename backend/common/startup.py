from backend.dome.service import (
    DomeService
)

from backend.mount.service import (
    MountService
)

from backend.safety.service import (
    SafetyService
)

from backend.common.service_registry import (
    register
)


def initialize_services():

    register(
        "dome",
        DomeService()
    )

    register(
        "mount",
        MountService()
    )

    register(
        "safety",
        SafetyService()
    )