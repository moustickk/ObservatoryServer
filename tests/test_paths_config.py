"""Tests des chemins de donnees et du schema de configuration (phase 7).

Ce que ces tests protegent :
 - une installation (executable) ecrit dans %ProgramData%, jamais dans le
   dossier du programme ;
 - la variable d'environnement reste prioritaire, pour les tests et les
   installations portables ;
 - les journaux utilisent les memes chemins que le reste (plus de calcul
   `__file__.parents[...]` duplique) ;
 - chaque reglage a un type, un groupe et une description dans le schema.
"""

import json
import sys

import pytest

from backend.common import paths, settings_manager
from backend.common import logger


# -- chemins -------------------------------------------------------------


def test_chemin_de_developpement(monkeypatch):
    monkeypatch.delenv(paths.OVERRIDE_ENV, raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert paths.default_data_dir() == paths.APP_DIR / "data"


def test_chemin_installe_dans_programdata(monkeypatch, tmp_path):
    monkeypatch.delenv(paths.OVERRIDE_ENV, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))

    assert paths.default_data_dir() == tmp_path / "ObservatoryServer"


def test_variable_denvironnement_prioritaire(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "programdata"))
    monkeypatch.setenv(paths.OVERRIDE_ENV, str(tmp_path / "ailleurs"))

    assert paths.default_data_dir() == tmp_path / "ailleurs"


def test_les_journaux_utilisent_les_chemins_communs():
    """logger calculait son propre LOG_DIR : deux sources de verite."""

    assert logger.LOG_DIR == paths.LOG_DIR


# -- schema --------------------------------------------------------------


def test_le_schema_couvre_tous_les_reglages():
    data = settings_manager.schema()
    described = {item["key"]: item for item in data["settings"]}

    assert set(described) == set(settings_manager.DEFAULT_SETTINGS)


def test_chaque_reglage_a_un_groupe_et_une_description():
    for item in settings_manager.schema()["settings"]:
        assert item["group"] in settings_manager.SETTING_GROUPS, item["key"]
        assert item["description"], item["key"]


def test_les_types_refletent_les_valeurs_par_defaut():
    types = {
        item["key"]: item["type"]
        for item in settings_manager.schema()["settings"]
    }

    assert types["simulation"] == "bool"
    assert types["full_travel_time"] == "int"
    assert types["min_temperature"] == "float"
    assert types["serial_port"] == "str"


def test_les_valeurs_autorisees_sont_exposees():
    items = {
        item["key"]: item
        for item in settings_manager.schema()["settings"]
    }

    assert items["mount_check_mode"]["choices"] == ["strict", "disabled"]
    assert "choices" not in items["simulation"]


def test_les_identifiants_alpaca_sont_en_lecture_seule():
    items = {
        item["key"]: item
        for item in settings_manager.schema()["settings"]
    }

    assert items["dome_unique_id"]["read_only"] is True
    assert items["safety_unique_id"]["read_only"] is True
    assert items["serial_port"]["read_only"] is False


def test_lapi_refuse_de_changer_un_identifiant_stable():
    with pytest.raises(ValueError) as caught:
        settings_manager.update_setting(
            "dome_unique_id",
            "00000000-0000-0000-0000-000000000000",
        )

    assert "NINA" in str(caught.value)


# -- premier demarrage ---------------------------------------------------


def test_premier_demarrage_cree_le_fichier(monkeypatch, tmp_path):
    settings_file = tmp_path / "config" / "settings.json"

    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(settings_manager, "_settings", None)

    settings = settings_manager.load_settings()

    assert settings_file.exists()

    written = json.loads(settings_file.read_text(encoding="utf-8"))
    assert written["simulation"] == settings["simulation"]
    assert written["serial_port"] == "COM4"


def test_un_fichier_illisible_est_ecarte(monkeypatch, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{ ceci n'est pas du json", encoding="utf-8")

    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(settings_manager, "_settings", None)

    settings = settings_manager.load_settings()

    assert settings["simulation"] is True  # retour aux valeurs par defaut
    assert settings_file.exists()
    assert (tmp_path / "settings.json.bad").exists()
