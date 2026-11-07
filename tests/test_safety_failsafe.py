"""Tests de la meteo fail-safe (phase 5).

Aucun appel reseau : la reponse Open-Meteo est fabriquee sur mesure.

Ce que ces tests protegent :
 - on retient le pire cas de la fenetre, pas seulement l'heure suivante ;
 - les rafales comptent autant que le vent moyen ;
 - une panne du fournisseur ne peut jamais produire SAFE ;
 - une mesure UNSAFE gardee en cache reste UNSAFE (regression de l'ancien
   code, qui declarait SAFE des que le cache etait recent).
"""

from datetime import datetime

import pytest

from backend.common import settings_manager
from backend.safety.config import current
from backend.safety.evaluator import evaluate_weather
from backend.safety.monitor import failure_decision
from backend.safety.weather_provider import build_url, parse_weather


# -- lecture de la reponse Open-Meteo ------------------------------------


def test_le_modele_meteo_est_transmis_a_open_meteo():
    auto = build_url("best_match")

    # « best_match » est le defaut du fournisseur : pas de parametre inutile.
    assert "models=" not in auto

    ecmwf = build_url("ecmwf_ifs025")

    assert ecmwf.startswith("https://api.open-meteo.com/v1/forecast")
    assert "models=ecmwf_ifs025" in ecmwf


def payload():
    return {
        "utc_offset_seconds": 7200,
        "current": {
            "temperature_2m": 4.5,
            "wind_speed_10m": 25,
            "wind_gusts_10m": 80,
            "cloud_cover": 70,
        },
        "hourly": {
            "time": [
                "2026-10-24T17:00",
                "2026-10-24T18:00",
                "2026-10-24T19:00",
                "2026-10-24T20:00",
            ],
            "precipitation_probability": [10, 20, 95, 100],
            "precipitation": [0, 0, 1.2, 3.0],
            "temperature_2m": [5, 4, 1, -2],
            "wind_gusts_10m": [20, 30, 75, 90],
        },
    }


def test_on_retient_le_pire_cas_de_la_fenetre():
    """Fenetre de 1 h depuis 18:00 : on ignore 20:00 (100 % de pluie)."""

    weather = parse_weather(payload(), now=datetime(2026, 10, 24, 18, 30))

    assert weather["rain_probability"] == 95
    assert weather["rain_mm"] == 1.2
    assert weather["forecast_temperature"] == 1
    assert weather["wind_gust"] == 80
    assert weather["wind"] == 25
    assert weather["clouds"] == 70


def test_la_rafale_la_plus_forte_prime_sur_le_vent_moyen():
    data = payload()
    data["current"]["wind_gusts_10m"] = 120

    weather = parse_weather(data, now=datetime(2026, 10, 24, 18, 0))

    assert weather["wind_gust"] == 120


def test_une_reponse_en_erreur_est_rejetee():
    with pytest.raises(ValueError):
        parse_weather({"error": True, "reason": "rate limit"})


def test_une_reponse_sans_serie_horaire_est_rejetee():
    with pytest.raises(ValueError):
        parse_weather({"current": {}, "hourly": {}})


def test_une_fenetre_sans_prevision_est_rejetee():
    """Heures d'un autre jour : on refuse plutot que d'utiliser n'importe quoi."""

    with pytest.raises(ValueError):
        parse_weather(payload(), now=datetime(2026, 11, 1, 12, 0))


# -- seuils -------------------------------------------------------------


def safe_weather():
    return {
        "wind": 10,
        "wind_gust": 15,
        "clouds": 20,
        "rain_probability": 5,
        "rain_mm": 0,
        "temperature": 12,
        "forecast_temperature": 10,
    }


def test_meteo_calme_est_sure():
    safe, reasons = evaluate_weather(safe_weather())

    assert safe is True
    assert reasons == []


def test_une_rafale_fait_refuser():
    weather = safe_weather()
    weather["wind_gust"] = current().max_wind_gust + 5

    safe, reasons = evaluate_weather(weather)

    assert safe is False
    assert any("RAFALES" in reason for reason in reasons)


def test_un_vent_moyen_fait_refuser():
    weather = safe_weather()
    weather["wind"] = current().max_wind_speed + 5

    safe, reasons = evaluate_weather(weather)

    assert safe is False
    assert any("VENT" in reason for reason in reasons)


def test_le_gel_est_detecte_sur_la_fenetre():
    weather = safe_weather()
    weather["forecast_temperature"] = current().min_temperature - 1

    safe, reasons = evaluate_weather(weather)

    assert safe is False
    assert "RISQUE GEL" in reasons


# -- panne du fournisseur -----------------------------------------------


def test_sans_mesure_une_panne_est_unsafe():
    safe, message = failure_decision(None, -1)

    assert safe is False
    assert "AUCUNE DONNEE" in message


def test_une_mesure_recente_et_sure_reste_sure():
    safe, message = failure_decision(safe_weather(), 5, max_age_minutes=30)

    assert safe is True
    assert "CACHE 5 min" in message


def test_une_mesure_perimee_est_unsafe():
    safe, message = failure_decision(safe_weather(), 31, max_age_minutes=30)

    assert safe is False
    assert "PERIMEES" in message


def test_une_mesure_recente_mais_dangereuse_reste_dangereuse():
    """Regression : l'ancien code declarait SAFE sur un cache recent."""

    danger = safe_weather()
    danger["rain_probability"] = 100

    safe, message = failure_decision(danger, 5, max_age_minutes=30)

    assert safe is False
    assert "PLUIE" in message


# -- application a chaud -------------------------------------------------


def _isoler_reglages(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_manager, "_settings", None)
    settings_manager.load_settings()


def test_un_seuil_modifie_s_applique_sans_redemarrage(monkeypatch, tmp_path):
    """Le seuil doit etre relu a chaque evaluation, pas fige a l'import."""

    _isoler_reglages(monkeypatch, tmp_path)

    weather = safe_weather()
    weather["clouds"] = 50

    assert evaluate_weather(weather)[0] is True

    settings_manager.update_setting("max_cloud_cover", 20)

    safe, reasons = evaluate_weather(weather)

    assert safe is False
    assert any("NUAGES" in reason for reason in reasons)


def test_le_modele_modifie_s_applique_sans_redemarrage(monkeypatch, tmp_path):
    _isoler_reglages(monkeypatch, tmp_path)

    assert "models=" not in build_url()

    settings_manager.update_setting("weather_model", "ecmwf_ifs025")

    assert "models=ecmwf_ifs025" in build_url()


def test_la_fenetre_de_prevision_s_applique_sans_redemarrage(monkeypatch, tmp_path):
    _isoler_reglages(monkeypatch, tmp_path)

    moment = datetime(2026, 10, 24, 17, 30)

    assert parse_weather(payload(), now=moment)["window_hours"] == 1

    settings_manager.update_setting("lookahead_hours", 3)

    assert parse_weather(payload(), now=moment)["window_hours"] == 3

