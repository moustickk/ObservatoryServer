"""Outil de diagnostic manuel du toit.

A lancer sur la machine de l'observatoire uniquement :

    .\\.venv\\Scripts\\python.exe -m backend.dome.manual_control status
    .\\.venv\\Scripts\\python.exe -m backend.dome.manual_control open

La commande passe par DomeService : l'interlock monture s'applique donc
comme via l'API. En mode reel, une confirmation est demandee.
"""

import argparse
import json
import sys

from backend.common import settings_manager
from backend.dome.serial_link import LinkError, build_roof_link
from backend.dome.service import DomeService
from backend.mount.link import build_mount_link


def main(argv=None):

    parser = argparse.ArgumentParser(description="Controle manuel du toit")
    parser.add_argument(
        "command",
        choices=["status", "open", "close", "stop"],
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="ne pas demander de confirmation (materiel reel)",
    )
    args = parser.parse_args(argv)

    settings = settings_manager.load_settings()
    link = build_roof_link(settings)
    mount = build_mount_link(settings)
    dome = DomeService(link, mount, settings)

    try:
        if args.command == "status":
            print(json.dumps(dome.status(), indent=2, ensure_ascii=False))
            return 0

        if not settings.get("simulation") and not args.yes:
            print(f"Commande '{args.command}' sur le MATERIEL REEL ({link.description}).")
            if input("Taper 'oui' pour confirmer : ").strip().lower() != "oui":
                print("Annule.")
                return 1

        result = getattr(dome, args.command)()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 2

    except LinkError as ex:
        print(f"Liaison toit indisponible : {ex}", file=sys.stderr)
        return 3

    finally:
        link.close()


if __name__ == "__main__":
    sys.exit(main())
