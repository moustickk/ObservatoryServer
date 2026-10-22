from backend.common.config import (
    get
)


LAT = 48.119722
LON = -1.200556

MAX_WIND_SPEED = get(
    "max_wind_speed",
    40.0
)

MAX_RAIN_PROBABILITY = get(
    "max_rain_probability",
    30
)

MAX_RAIN_MM = get(
    "max_rain_mm",
    0.1
)

MAX_CLOUD_COVER = get(
    "max_cloud_cover",
    80
)

MIN_TEMPERATURE = get(
    "min_temperature",
    0.5
)

CACHE_TIMEOUT_MINUTES = get(
    "weather_cache_minutes",
    30
)

UPDATE_INTERVAL = get(
    "weather_update_seconds",
    600
)