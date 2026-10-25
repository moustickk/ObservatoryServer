"""Tests de la lecture des journaux pour l'interface."""

import pytest

from backend.common import logs_api


def make_log(directory, name, count):
    path = directory / name
    path.write_text(
        "\n".join(f"ligne {index:04d}" for index in range(count)) + "\n",
        encoding="utf-8",
    )
    return path


def test_tail_renvoie_la_fin(tmp_path, monkeypatch):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)
    make_log(tmp_path, "server.log", 50)

    lines, size, truncated = logs_api.tail_log("server.log", lines=5)

    assert lines == [f"ligne {index:04d}" for index in range(45, 50)]
    assert size > 0
    assert truncated is False


def test_tail_borne_le_nombre_de_lignes(tmp_path, monkeypatch):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)
    make_log(tmp_path, "tray.log", 10)

    lines, _, _ = logs_api.tail_log("tray.log", lines=2000)

    assert len(lines) == 10


def test_tail_indique_une_troncature(tmp_path, monkeypatch):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logs_api, "MAX_BYTES", 64)
    make_log(tmp_path, "server.log", 500)

    lines, _, truncated = logs_api.tail_log("server.log", lines=200)

    assert truncated is True
    assert lines


def test_un_journal_absent_ne_casse_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)

    lines, size, truncated = logs_api.tail_log("roof.log")

    assert lines == []
    assert size == 0
    assert truncated is False


@pytest.mark.parametrize(
    "name",
    ["..\\..\\Windows\\win.ini", "settings.json", "/etc/passwd", "server.log.tmp"],
)
def test_seuls_les_journaux_connus_sont_lisibles(tmp_path, monkeypatch, name):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)

    with pytest.raises(logs_api.UnknownLog):
        logs_api.tail_log(name)


def test_liste_des_journaux(tmp_path, monkeypatch):
    monkeypatch.setattr(logs_api, "LOG_DIR", tmp_path)
    make_log(tmp_path, "server.log", 3)

    entries = {entry["name"]: entry for entry in logs_api.list_logs()}

    assert entries["server.log"]["exists"] is True
    assert entries["server.log"]["size"] > 0
    assert entries["tray.log"]["exists"] is False
    assert set(entries) == set(logs_api.KNOWN_LOGS)
