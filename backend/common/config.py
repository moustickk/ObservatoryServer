from backend.common.settings import (
    settings
)


def get(
    key,
    default=None
):

    return settings.get(
        key,
        default
    )