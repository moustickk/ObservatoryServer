from backend.safety.parser import (
    parse_weather
)

from backend.safety.evaluator import (
    evaluate_weather
)

from backend.safety.state import (
    weather_data,
    state_lock
)


def process_weather(data):

    weather = parse_weather(
        data
    )

    safe, reasons = evaluate_weather(
        wind=weather.wind,
        clouds=weather.clouds,
        rain_probability=weather.rain_probability,
        rain_mm=weather.rain_mm,
        current_temp=weather.temperature,
        forecast_temp=weather.forecast_temperature
    )

    with state_lock:

        weather_data["wind"] = (
            weather.wind
        )

        weather_data["clouds"] = (
            weather.clouds
        )

        weather_data["rain_probability"] = (
            weather.rain_probability
        )

        