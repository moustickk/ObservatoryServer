"""Tests de l'empaquetage : mode supervise et icone de notification."""

import sys

from backend.common import restart


def test_mode_developpement_non_supervise(monkeypatch):
    monkeypatch.delenv(restart.SUPERVISOR_ENV, raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert restart.supervised() is False


def test_mode_supervise_par_variable(monkeypatch):
    monkeypatch.setenv(restart.SUPERVISOR_ENV, "1")

    assert restart.supervised() is True


def test_mode_supervise_par_executable(monkeypatch):
    monkeypatch.delenv(restart.SUPERVISOR_ENV, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert restart.supervised() is True


def test_le_code_de_redemarrage_est_distinct_dun_arret():
    """0 = quitter, 75 = relancer. Confondre les deux ferait boucler l'icone."""

    assert restart.RESTART_EXIT_CODE != 0


def test_licone_se_dessine():
    from backend.tray import _icon_image

    for color in ("closed", "opened", "error", "starting"):
        image = _icon_image(color)
        assert image.size == (64, 64)
