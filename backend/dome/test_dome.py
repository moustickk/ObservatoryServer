from backend.dome.service import (
    DomeService
)

print("Creating dome...")

dome = DomeService()

print("Dome created")

print("Sending STATUS...")

result = dome.status()

print("RESULT =")
print(repr(result))
