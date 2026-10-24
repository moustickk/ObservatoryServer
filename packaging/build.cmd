@echo off
rem Construit l'application empaquetee (onedir).
rem   packaging\build.cmd
rem   packaging\build.cmd -Clean
rem
rem Passe par PowerShell avec -ExecutionPolicy Bypass : la strategie par
rem defaut de Windows interdit l'execution des scripts .ps1.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
if errorlevel 1 (
    echo.
    echo Echec de la construction.
    exit /b 1
)
