import threading


state_lock = threading.Lock()

is_safe = False

current_status = "Initialisation..."

last_weather_update = None

last_good_timestamp = None

last_good_data = None

weather_data = {
    "wind": 0,
    "clouds": 0,
    "rain_probability": 0,
    "rain_mm": 0,
    "temperature": 0
}