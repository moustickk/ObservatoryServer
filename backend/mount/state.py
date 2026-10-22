import threading


state_lock = threading.Lock()

connected = False

at_park = False

driver_loaded = False

last_error = None