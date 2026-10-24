from backend.common.constants import (
    APP_NAME,
    VERSION
)


def get_runtime_info():

    return {
        "application": APP_NAME,
        "version": VERSION
    }