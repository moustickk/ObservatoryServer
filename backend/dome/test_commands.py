from backend.dome.service import (
    DomeService
)

dome = DomeService()

print()
print("OPEN")
print(dome.open())

print()
input("Appuie sur ENTREE pour continuer...")

print()
print("STOP")
print(dome.stop())

print()
input("Appuie sur ENTREE pour continuer...")

print()
print("CLOSE")
print(dome.close())

print()
input("Appuie sur ENTREE pour continuer...")

print()
print("STOP")
print(dome.stop())