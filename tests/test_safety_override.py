"""Tests du verdict meteo force (essais sans attendre la pluie)."""

import pytest

from backend.safety import state
from backend.safety.service import SafetyService
from backend.safety.status import get_status


@pytest.fixture(autouse=True)
def reset_override():
    state.set_forced(None, 0)
    state.is_safe = True
    state.current_status = "SAFE"
    yield
    state.set_forced(None, 0)


def test_le_verdict_force_prime_sur_la_mesure():
    state.set_forced("UNSAFE", 600)

    status = get_status()

    assert status["safe"] is False
    assert status["forced"] is True
    assert status["forced_value"] == "UNSAFE"
    assert "FORCE" in status["status"]


def test_un_verdict_force_safe_prime_aussi():
    state.is_safe = False
    state.current_status = "UNSAFE"

    state.set_forced("SAFE", 600)

    assert get_status()["safe"] is True


def test_le_forcage_expire(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(state, "_now", lambda: clock["now"])

    state.set_forced("SAFE", 60)

    assert get_status()["forced"] is True

    clock["now"] += 61

    assert get_status()["forced"] is False


def test_retour_au_verdict_reel():
    service = SafetyService()

    state.set_forced("UNSAFE", 600)
    result = service.force("auto")

    assert result["forced"] is False
    assert get_status()["safe"] is True  # mesure reelle : SAFE dans ce test


def test_une_valeur_inconnue_est_refusee():
    with pytest.raises(ValueError):
        SafetyService().force("peut-etre")


def test_la_duree_est_bornee():
    result = SafetyService().force("unsafe", 999)

    assert result["remaining_seconds"] <= 3600


def test_alpaca_voit_le_verdict_force():
    """Le SafetyMonitor doit refleter le forcage, pas la mesure."""
    state.is_safe = True

    state.set_forced("UNSAFE", 600)

    assert SafetyService().is_safe() is False


def test_le_forcage_reveille_l_agent():
    """Pas besoin d'attendre le cycle : l'agent doit etre reveille."""

    state.wakeup.clear()

    SafetyService().force("unsafe", 1)

    assert state.wakeup.is_set()
