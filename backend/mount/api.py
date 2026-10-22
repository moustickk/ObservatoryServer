from backend.mount.state import (
    connected,
    at_park,
    last_error
)


def get_mount_status():

    return {
        "connected": connected,
        "at_park": at_park,
        "last_error": last_error
    }