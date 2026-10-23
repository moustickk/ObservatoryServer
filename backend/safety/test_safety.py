from backend.safety.weather_provider import (
    get_weather
)

from backend.safety.engine import (
    process_weather
)

from backend.safety.service import (
    SafetyService
)


weather = get_weather()

process_weather(
    weather
)

service = SafetyService()

print()

print("SAFE :", service.is_safe())

print()

print(service.status())

print()

print(service.device_state())