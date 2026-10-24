# -*- mode: python ; coding: utf-8 -*-
"""Recette PyInstaller (onedir) de l'application installee.

    .\\.venv\\Scripts\\pyinstaller.exe --noconfirm --clean packaging\\ObservatoryServer.spec

ou, plus simplement : `packaging\\build.ps1`.

Points d'attention :

- `backend/web` doit etre embarque, sinon l'interface manque a l'appel
  (`app.py` la cherche a cote de lui) ;
- uvicorn charge ses boucles et protocoles par import dynamique : on les
  collecte explicitement, sinon le serveur demarre puis echoue a l'ecoute ;
- `console=False` : l'application ne doit pas ouvrir de fenetre noire. Le
  serveur enfant est lance avec CREATE_NO_WINDOW et sa sortie redirigee vers
  `%ProgramData%\\ObservatoryServer\\logs\\server.log`.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).parent

hiddenimports = collect_submodules("uvicorn")

hiddenimports += [
    "win32com.client",
    "pythoncom",
    "pywintypes",
]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "backend" / "web"), "backend/web"),
        (str(ROOT / "assets" / "observatory.ico"), "assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ObservatoryServer",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "observatory.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ObservatoryServer",
)
