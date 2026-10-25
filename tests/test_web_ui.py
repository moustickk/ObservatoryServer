"""Tests de l'interface web locale (phase 8).

Pas de navigateur ni de client HTTP dans les tests : on verifie que les
fichiers sont la, qu'ils sont servis, et que le JavaScript appelle bien les
endpoints qui existent. Le rendu lui-meme se verifie a l'oeil, ou par un
appel HTTP sur le serveur demarre.
"""

from backend.app import WEB_DIR, app


def test_les_fichiers_de_l_interface_existent():
    for name in ("index.html", "style.css", "app.js"):
        path = WEB_DIR / name
        assert path.is_file(), name
        assert path.stat().st_size > 200, name


def test_l_interface_est_montee_sur_le_serveur():
    mounted = {
        getattr(route, "path", None)
        for route in app.routes
    }

    assert "/ui" in mounted


def test_la_page_reference_ses_ressources():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    assert 'href="style.css"' in html
    assert 'src="app.js"' in html
    assert 'lang="fr"' in html


def test_le_javascript_appelle_les_endpoints_reels():
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    for endpoint in (
        "/api/health",
        "/api/safety/status",
        "/api/config/schema",
        "/api/dome/open",
        "/api/dome/close",
        "/api/dome/stop",
        "/api/mount/park",
        "/api/server/restart",
        "/api/mount/drivers",
        "/api/logs",
    ):
        assert endpoint in js, endpoint


def test_les_endpoints_appeles_existent_vraiment():
    """Un renommage cote serveur doit faire echouer ce test, pas l'UI."""

    routes = {
        getattr(route, "path", None)
        for route in app.routes
    }

    for endpoint in (
        "/api/health",
        "/api/safety/status",
        "/api/config/schema",
        "/api/dome/open",
        "/api/dome/close",
        "/api/dome/stop",
        "/api/mount/park",
        "/api/server/restart",
        "/api/mount/drivers",
        "/api/logs",
    ):
        assert endpoint in routes, endpoint


def test_le_processus_de_redemarrage_est_du_python_valide():
    from backend.common.restart import restarter_source

    compile(restarter_source(), "<restarter>", "exec")


# -- acces local ---------------------------------------------------------


def test_les_commandes_sont_locales_mais_alpaca_reste_ouvert():
    from backend.app import requires_local_client

    assert requires_local_client("/ui/") is True
    assert requires_local_client("/api/dome/open") is True
    assert requires_local_client("/api/config/schema") is True
    assert requires_local_client("/docs") is True

    # NINA doit pouvoir commander le toit depuis une autre machine.
    assert requires_local_client("/api/v1/dome/0/openshutter") is False
    assert requires_local_client("/management/v1/configureddevices") is False
