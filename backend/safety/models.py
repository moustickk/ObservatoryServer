from dataclasses import dataclass


@dataclass
class WeatherData:

    wind: float

    clouds: float

    rain_probability: float

    rain_mm: float

    temperature: float

    forecast_temperature: float