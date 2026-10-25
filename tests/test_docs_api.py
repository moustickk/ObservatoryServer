"""Tests de la documentation embarquee."""

import pytest

from backend.common import docs_api


def test_trois_documents_sont_proposes():
    documents = docs_api.list_documents()

    assert [doc["key"] for doc in documents] == ["guide", "recette", "firmware"]
    assert all(doc["available"] for doc in documents)


def test_le_guide_est_rendu_en_html():

    document = docs_api.render("guide")

    assert document["title"] == "Guide utilisateur"
    assert "<h1>" in document["html"]
    # Les tableaux Markdown doivent etre convertis, pas laisses en texte.
    assert "<table>" in document["html"]


def test_la_recette_est_rendue():

    document = docs_api.render("recette")

    assert "Recette" in document["title"]
    assert "Sécurité" in document["html"] or "securite" in document["html"].lower()


@pytest.mark.parametrize(
    "name",
    ["../../README.md", "settings.json", "HANDOFF", "inconnu"],
)
def test_seuls_les_documents_connus_sont_lisibles(name):

    with pytest.raises(docs_api.UnknownDocument):
        docs_api.render(name)
