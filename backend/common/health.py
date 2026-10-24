_health = {}


def set_status(
    service,
    status
):

    _health[service] = status


def get_status():

    return _health