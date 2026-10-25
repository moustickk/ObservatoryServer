"""Tests de localisation du processus d'un driver ASCOM."""

import sys

import pytest

from backend.mount import driver


@pytest.mark.parametrize(
    "value, expected",
    [
        ('"C:\\Program Files (x86)\\Common Files\\ASCOM\\Telescope\\EQMOD.exe" /Automation',
         "C:\\Program Files (x86)\\Common Files\\ASCOM\\Telescope\\EQMOD.exe"),
        ("C:\\Tools\\driver.exe", "C:\\Tools\\driver.exe"),
        ("C:\\Tools\\driver.exe /unregserver", "C:\\Tools\\driver.exe"),
        ("", None),
        (None, None),
    ],
)
def test_extraction_du_chemin(value, expected):
    assert driver.parse_server_path(value) == expected


def test_un_progid_inconnu_ne_casse_rien():
    assert driver.executable("Inexistant.Telescope") is None
    assert driver.restart("Inexistant.Telescope") is False


@pytest.mark.skipif(sys.platform != "win32", reason="registre Windows")
def test_eqmod_est_localise_si_installe():
    path = driver.executable("EQMOD.Telescope")

    # Sur cette machine EQMOD est installe ; ailleurs, None est acceptable.
    if path is not None:
        assert path.lower().endswith(".exe")
