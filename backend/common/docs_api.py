"""Documentation embarquee, rendue en HTML pour l'interface.

Trois documents seulement, choisis explicitement : un nom libre permettrait
de lire n'importe quel fichier de la machine via l'URL.

Les fichiers sont embarques dans l'executable (voir la recette PyInstaller) :
la documentation reste consultable sur le poste d'observatoire, sans dépôt ni
lecteur Markdown.
"""

from pathlib import Path

import re

import markdown

from backend.common.paths import APP_DIR


DOCUMENTS = {
    "guide": ("Guide utilisateur", "README.md"),
    "recette": ("Recette de mise en service", "docs/RECETTE.md"),
    "firmware": ("Firmware du toit", "firmware/RoofController/README.md"),
}

EXTENSIONS = ("tables", "fenced_code", "sane_lists")

_IMAGE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)

# Section « Aperçu » du README : uniquement des captures du depot, qui ne se
# resolvent pas dans l'application et laissent des tableaux vides.
_APERCU = re.compile(r"^## Aper[çc]u\s*$.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)


class UnknownDocument(KeyError):
    pass


def _path(relative):
    return APP_DIR / relative


def list_documents():

    result = []

    for key, (title, relative) in DOCUMENTS.items():
        result.append({
            "key": key,
            "title": title,
            "available": _path(relative).is_file(),
        })

    return result


def render(name):

    if name not in DOCUMENTS:
        raise UnknownDocument(name)

    title, relative = DOCUMENTS[name]

    path = _path(relative)

    if not path.is_file():
        raise UnknownDocument(name)

    text = path.read_text(encoding="utf-8")

    # La galerie de captures n'a pas de sens dans l'application elle-meme.
    text = _APERCU.sub("", text)

    html = markdown.markdown(text, extensions=list(EXTENSIONS))

    # Toute autre image du depot resterait cassee dans l'application.
    html = _IMAGE.sub("", html)

    return {
        "key": name,
        "title": title,
        "html": html,
    }
