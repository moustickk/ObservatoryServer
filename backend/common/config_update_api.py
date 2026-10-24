from backend.common.settings_manager import (
    load_settings,
    save_settings
)


def convert_value(value):

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    try:

        if "." in value:

            return float(value)

        return int(value)

    except Exception:

        return value


def update_config(
    key,
    value
):

    settings = load_settings()

    settings[key] = convert_value(
        value
    )

    save_settings(
        settings
    )

    return settings