from backend.dome.monitor import (
    sync_state
)

from backend.dome.state import (
    get_state
)

print()

print("SYNC")

result = sync_state()

print()

print("ARDUINO STATE:")
print(result)

print()

print("STATE:")
print(get_state())