"""Verification manuelle de la chaine meteo / securite.

    .\\.venv\\Scripts\\python.exe -m backend.safety.manual_check
"""

import json

from backend.safety.evaluator import evaluate_weather
from backend.safety.weather_provider import get_weather


def main():

    weather = get_weather()
    safe, reasons = evaluate_weather(weather)

    print("Meteo brute :")
    print(json.dumps(weather, indent=2, ensure_ascii=False))

    print()
    print("Evaluation :", "SAFE" if safe else "UNSAFE")

    for reason in reasons:
        print("  -", reason)

    return 0 if safe else 2


if __name__ == "__main__":
    raise SystemExit(main())
