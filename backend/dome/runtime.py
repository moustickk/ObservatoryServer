monitor_running = False


def is_running():

    return monitor_running


def set_running(value):

    global monitor_running

    monitor_running = value