from backend.common.logs import (
    dome_log
)


def mount_log(message):

    dome_log(
        f"MOUNT | {message}"
    )