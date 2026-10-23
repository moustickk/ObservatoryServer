import time

from backend.dome.state import (
    state_data,
    compute_position
)

state_data["state"] = "OPENING"

state_data["position"] = 0

state_data["timestamp"] = time.time()

print()

print("Position initiale")
print(compute_position())

time.sleep(5)

print()

print("Position apres 5 secondes")
print(compute_position())