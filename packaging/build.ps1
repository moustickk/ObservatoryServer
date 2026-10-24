# Construit l'application empaquetee (onedir).
#
#     .\packaging\build.ps1
#     .\packaging\build.ps1 -Clean
#
# Resultat : dist\ObservatoryServer\ObservatoryServer.exe

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $python)) {
    throw "Environnement introuvable : $python"
}

# L'icone doit exister avant PyInstaller.
& $python "packaging\make_icon.py"
if ($LASTEXITCODE -ne 0) { throw "Generation de l'icone impossible" }

if ($Clean) {
    Remove-Item -Recurse -Force "$root\build", "$root\dist" -ErrorAction SilentlyContinue
}

& $pyinstaller --noconfirm --clean --distpath "$root\dist" --workpath "$root\build" "packaging\ObservatoryServer.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue (code $LASTEXITCODE)" }

$exe = Join-Path $root "dist\ObservatoryServer\ObservatoryServer.exe"

if (-not (Test-Path $exe)) {
    throw "Executable absent : $exe"
}

Write-Host ""
Write-Host "Construit : $exe"
