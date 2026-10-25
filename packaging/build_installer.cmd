@echo off
rem Compile l'installateur Inno Setup.
rem   packaging\build_installer.cmd
rem
rem Suppose que dist\ObservatoryServer existe (packaging\build.cmd).

setlocal

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo Inno Setup introuvable. Installer depuis https://jrsoftware.org/isdl.php
    exit /b 1
)

if not exist "%~dp0..\dist\ObservatoryServer\ObservatoryServer.exe" (
    echo Executable absent : lancer d'abord packaging\build.cmd
    exit /b 1
)

"%ISCC%" "%~dp0ObservatoryServer.iss"
if errorlevel 1 (
    echo.
    echo Echec de la compilation de l'installateur.
    exit /b 1
)

echo.
echo Installateur cree dans dist\
