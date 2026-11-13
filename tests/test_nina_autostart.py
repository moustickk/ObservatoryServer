"""Tests du demarrage automatique de NINA."""

from pathlib import Path

from backend.common import settings_manager
from backend.common import nina


def test_le_chemin_configure_est_utilise(monkeypatch, tmp_path):
    exe = tmp_path / "NINA.exe"
    exe.write_bytes(b"")

    monkeypatch.setattr(
        nina, "get", lambda key, default=None: str(exe) if key == "nina_path" else default
    )

    assert nina.detect_path() == str(exe)


def test_le_chemin_est_detecte_dans_program_files(monkeypatch, tmp_path):
    folder = tmp_path / "N.I.N.A. - Nighttime Imaging 'N' Astronomy"
    folder.mkdir()
    exe = folder / "NINA.exe"
    exe.write_bytes(b"")

    monkeypatch.setattr(nina, "_roots", lambda: [tmp_path])
    monkeypatch.setattr(nina, "get", lambda key, default=None: "")

    assert nina.detect_path() == str(exe)


def test_pas_de_second_lancement_si_nina_tourne(monkeypatch):
    monkeypatch.setattr(nina, "detect_path", lambda: "NINA.exe")
    monkeypatch.setattr(nina, "is_running", lambda: True)

    def interdit(*args, **kwargs):
        raise AssertionError("Popen ne doit pas etre appele")

    monkeypatch.setattr(nina, "subprocess", type("S", (), {"Popen": interdit}))

    assert nina.launch() is False


def test_lancement_si_nina_est_absent(monkeypatch):
    appel = {}

    class FauxSubprocess:
        @staticmethod
        def Popen(args, **kwargs):
            appel["args"] = args
            appel["kwargs"] = kwargs

    monkeypatch.setattr(nina, "detect_path", lambda: "NINA.exe")
    monkeypatch.setattr(nina, "is_running", lambda: False)
    monkeypatch.setattr(nina, "subprocess", FauxSubprocess)

    assert nina.launch() is True
    assert appel["args"] == ["NINA.exe"]


def test_is_running_lit_la_sortie_oem(monkeypatch):
    """tasklist ecrit en OEM : un decodage UTF-8 ferait echouer la detection."""

    class Resultat:
        stdout = (
            b'"System","4","Services","0","1 000 K"\n'
            b'"NINA.exe","11536","Console","1","500 000 K"\n'
            b'"processus_accentu\xe9.exe","1234","Console","1","1 000 K"\n'
        )

    class FauxSubprocess:
        @staticmethod
        def run(*args, **kwargs):
            return Resultat()

    monkeypatch.setattr(nina, "subprocess", FauxSubprocess)

    assert nina.is_running() is True



def test_autostart_desactive_ne_fait_rien(monkeypatch):
    monkeypatch.setattr(nina, "get_bool", lambda key, default=False: False)
    monkeypatch.setattr(
        nina,
        "server_ready",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ne doit pas attendre")),
    )

    assert nina.autostart(11111) is False


def test_autostart_attend_le_serveur_puis_lance(monkeypatch):
    monkeypatch.setattr(nina, "get_bool", lambda key, default=False: True)
    monkeypatch.setattr(nina, "server_ready", lambda port: True)
    monkeypatch.setattr(nina, "LAUNCH_DELAY_SECONDS", 0)
    monkeypatch.setattr(nina, "launch", lambda: True)

    assert nina.autostart(11111) is True


def test_autostart_ne_lance_pas_si_serveur_injoignable(monkeypatch):
    monkeypatch.setattr(nina, "get_bool", lambda key, default=False: True)
    monkeypatch.setattr(nina, "server_ready", lambda port: False)
    monkeypatch.setattr(
        nina,
        "launch",
        lambda: (_ for _ in ()).throw(AssertionError("ne doit pas lancer")),
    )

    assert nina.autostart(11111) is False


def test_les_reglages_nina_sont_dans_le_schema():
    items = {
        item["key"]: item
        for item in settings_manager.schema()["settings"]
    }

    assert items["nina_autostart"]["label"] == "Démarrer NINA automatiquement"
    assert items["nina_path"]["label"] == "Chemin de NINA"
    assert items["nina_autostart"]["requires_restart"] is True
