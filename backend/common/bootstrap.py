from backend.common.startup import (
    initialize_services
)

from backend.common.runtime import (
    get_runtime_info
)


def bootstrap():

    initialize_services()

    return get_runtime_info()
