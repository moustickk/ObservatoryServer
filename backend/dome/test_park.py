from backend.dome.service import (
    DomeService
)

dome = DomeService()

print()

print("TEST CLOSE")

result = dome.close()

print()

print("RESULTAT :")
print(result)