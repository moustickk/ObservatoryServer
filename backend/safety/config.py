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

# Rafales : plus severes que le vent moyen pour la meme valeur. Une rafale
# peut soulever un toit roulant la ou le vent moyen ne le fait pas.
MAX_WIND_GUST = get(
    "max_wind_gust",
    70.0
)

# Fenetre de prevision prise en compte, en heures. On retient le PIRE cas de
# la fenetre, pas seulement l'heure suivante : c'est ce qui evite d'ouvrir
# juste avant une averse annoncee dans deux heures.
LOOKAHEAD_HOURS = int(
    get(
        "lookahead_hours",
        1
    )
)

# Age au-dela duquel une mesure meteo n'est plus exploitable. Passe ce delai,
# la securite est declaree UNSAFE meme si la derniere mesure etait bonne.
MAX_WEATHER_AGE_MINUTES = get(
    "weather_max_age_minutes",
    30
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