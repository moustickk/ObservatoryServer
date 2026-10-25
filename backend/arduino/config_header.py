"""Generation du fichier `roof_config.h` a partir des reglages.

Le firmware lit ses parametres dans cet en-tete. L'interface web le regenere
avant chaque compilation : c'est ce qui permet de changer un brochage ou une
temporisation sans ouvrir l'IDE Arduino.

Chaque valeur reste protegee par `#ifndef` : une option de compilation
(`-DROOF_MAX_TRAVEL_MS=50000`) reste prioritaire sur le fichier.
"""

from datetime import datetime


def build_header(settings, now=None):
    """Retourne le contenu complet de `roof_config.h`."""

    now = now or datetime.now()

    max_travel_ms = int(float(settings.get("max_travel_time", 50)) * 1000)

    lines = [
        "/*",
        " * roof_config.h - parametres du controleur de toit.",
        " *",
        f" * Genere par ObservatoryServer le {now:%d-%m-%Y %H:%M:%S}.",
        " * Les modifications manuelles seront ecrasees au prochain",
        " * televersement : passer par l'interface web.",
        " */",
        "",
        "#ifndef ROOF_CONFIG_H",
        "#define ROOF_CONFIG_H",
        "",
        "/* -- Brochage -------------------------------------------------------",
        " * Fins de course NORMALEMENT FERMES, cables entre la broche et GND,",
        " * avec la resistance de tirage interne. HIGH = en butee (ou fil coupe).",
        " */",
        f"#define PIN_LIMIT_OPEN        {int(settings['pin_limit_open'])}",
        f"#define PIN_LIMIT_CLOSED      {int(settings['pin_limit_closed'])}",
        "",
        "/* Driver BTS7960 : RPWM/LPWM portent le sens et la vitesse. */",
        f"#define PIN_BTS_RPWM          {int(settings['pin_bts_rpwm'])}",
        f"#define PIN_BTS_LPWM          {int(settings['pin_bts_lpwm'])}",
        f"#define PIN_BTS_REN           {int(settings['pin_bts_ren'])}",
        f"#define PIN_BTS_LEN           {int(settings['pin_bts_len'])}",
        "",
        "/* -- Temporisations --------------------------------------------------",
        f" * ROOF_MAX_TRAVEL_MS vient de max_travel_time ({settings.get('max_travel_time')} s).",
        " * Il doit rester egal cote serveur et cote firmware.",
        " */",
        f"#define ROOF_MAX_TRAVEL_MS    {max_travel_ms}UL",
        f"#define ROOF_NO_MOTION_MS     {int(settings['roof_no_motion_ms'])}UL",
        f"#define ROOF_DEBOUNCE_MS      {int(settings['roof_debounce_ms'])}UL",
        f"#define ROOF_DIRECTION_DEAD_MS {int(settings['roof_direction_dead_ms'])}UL",
        f"#define ROOF_RAMP_START_MS    {int(settings['roof_ramp_start_ms'])}UL",
        f"#define ROOF_RAMP_STOP_MS     {int(settings['roof_ramp_stop_ms'])}UL",
        "",
        "/* -- Vitesses -------------------------------------------------------- */",
        f"#define ROOF_PWM_MIN          {int(settings['roof_pwm_min'])}",
        f"#define ROOF_PWM_MAX          {int(settings['roof_pwm_max'])}",
        "",
        "/* -- Liaison serie --------------------------------------------------- */",
        f"#define ROOF_BAUDRATE         {int(settings['baudrate'])}UL",
        "#define ROOF_LINE_MAX         32",
        "",
        "#endif /* ROOF_CONFIG_H */",
        "",
    ]

    return "\n".join(lines)
