_services = {}


def register(
    name,
    instance
):

    _services[name] = instance


def get(
    name
):

    return _services.get(
        name
    )


def all_services():

    return _services
