"""Lecture des reglages."""

from backend.common.settings_manager import as_dict


def get_config():
    return as_dict()
