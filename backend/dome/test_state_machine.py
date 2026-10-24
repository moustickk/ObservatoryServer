from backend.dome.service import (
    DomeService
)

from backend.dome.state import (
    get_state
)

dome = DomeService()

print()
print("STATE AVANT")
print(get_state())

print()
print("OPEN")
print(dome.open())

print()
print("STATE APRES OPEN")
print(get_state())

print()
input("Entrée...")

print()
print("STOP")
print(dome.stop())

print()
print("STATE APRES STOP")
print(get_state())
