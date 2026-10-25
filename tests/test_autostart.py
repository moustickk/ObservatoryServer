"""Tests du demarrage automatique et de la rotation du journal serveur."""

import sys
from logging.handlers import RotatingFileHandler

import pytest

from backend import server
from backend.common import autostart


windows_only = pytest.mark.skipif(
    sys.platform != "win32",
    reason="raccourci Windows",
)


# -- demarrage automatique ----------------------------------------------


@windows_only
def test_le_raccourci_est_cree_puis_supprime(tmp_path, monkeypatch):
    path = tmp_path / "ObservatoryServer.lnk"
    monkeypatch.setattr(autostart, "shortcut_path", lambda: path)

    assert autostart.is_enabled() is False

    assert autostart.set_enabled(True) is True
    assert path.is_file()

    assert autostart.set_enabled(False) is False
    assert not path.exists()


@windows_only
def test_supprimer_un_raccourci_absent_ne_casse_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "shortcut_path", lambda: tmp_path / "absent.lnk")

    assert autostart.set_enabled(False) is False


def test_la_cible_est_lanceur_en_developpement(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    executable, arguments = autostart.target()

    assert executable
    assert "launcher.py" in arguments


# -- icone dans la zone de notification ---------------------------------


def test_le_chemin_avec_guid_est_developpe():
    from backend.common import tray_icon

    stored = r"{6D809377-6AF0-444B-8957-A3773F02200E}\ObservatoryServer\ObservatoryServer.exe"

    expanded = tray_icon.expand_path(stored)

    assert expanded is not None
    assert expanded.lower().endswith(
        r"observatoryserver\observatoryserver.exe".lower()
    )
    assert not expanded.startswith("{")


def test_la_comparaison_ignore_la_casse(tmp_path):
    from backend.common import tray_icon

    executable = tmp_path / "ObservatoryServer.exe"
    executable.write_text("", encoding="utf-8")

    assert tray_icon.matches(str(executable).upper(), str(executable)) is True

    other = tmp_path / "Autre.exe"
    other.write_text("", encoding="utf-8")

    assert tray_icon.matches(str(other), str(executable)) is False


def test_le_statut_est_indisponible_hors_application(monkeypatch):
    from backend.common import tray_icon

    monkeypatch.delattr(sys, "frozen", raising=False)

    status = tray_icon.status()

    assert status["supported"] is False
    assert status["promoted"] is False


# -- rotation du journal serveur ----------------------------------------


def test_le_journal_serveur_tourne(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "LOG_DIR", tmp_path)

    handler = server.file_handler()

    try:
        assert isinstance(handler, RotatingFileHandler)
        assert handler.maxBytes == 5 * 1024 * 1024
        assert handler.backupCount == 5
    finally:
        handler.close()


def test_la_rotation_borne_reellement_le_fichier(tmp_path, monkeypatch):
    """Ecrit au-dela de la limite et verifie qu'un fichier .1 apparait."""

    monkeypatch.setattr(server, "LOG_DIR", tmp_path)
    monkeypatch.setattr(server, "LOG_MAX_BYTES", 1024)

    handler = server.file_handler()
    handler.setLevel(1)

    import logging

    logger = logging.getLogger("test.rotation")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(1)

    try:
        for index in range(200):
            logger.info("ligne de remplissage numero %d", index)
    finally:
        logger.handlers = []
        handler.close()

    assert (tmp_path / "server.log").exists()
    assert (tmp_path / "server.log.1").exists()
    assert (tmp_path / "server.log").stat().st_size <= 1024
