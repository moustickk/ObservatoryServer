import threading


state_lock = threading.Lock()

connected = False

state = "UNKNOWN"

position = -1

last_motion = "CLOSING"