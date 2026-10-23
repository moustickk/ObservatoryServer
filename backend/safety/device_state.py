from backend.safety import state


def get_device_state():

    return [
        {
            "Name": "IsSafe",
            "Value": state.is_safe
        },
        {
            "Name": "Wind",
            "Value": state.weather_data["wind"]
        },
        {
            "Name": "CloudCover",
            "Value": state.weather_data["clouds"]
        },
        {
            "Name": "RainProbability",
            "Value": state.weather_data["rain_probability"]
        },
        {
            "Name": "RainMM",
            "Value": state.weather_data["rain_mm"]
        },
        {
            "Name": "Temperature",
            "Value": state.weather_data["temperature"]
        },
        {
            "Name": "DataAgeMinutes",
            "Value": state.weather_age_minutes()
        }
    ]