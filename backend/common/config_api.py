"""Lecture des reglages et de leur schema."""

from backend.common.settings_manager import as_dict, schema


def get_config():
    return as_dict()


def get_schema():
    return schema()
