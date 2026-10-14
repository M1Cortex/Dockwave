@echo off
rem Dockwave starten - im Explorer doppelklicken.
rem
rem Beim ersten Start wird eine virtuelle Python-Umgebung im Projektordner
rem angelegt und PyQt6 installiert. Das dauert einmalig etwa eine Minute.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY="
for %%V in (python3.12 python3.11 python3.10 python3 py) do (
    if not defined PY (
        %%V -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY=%%V"
    )
)

if not defined PY (
    echo Kein Python 3.9 oder neuer gefunden.
    echo Installiere es von https://www.python.org/downloads/ ^(Haken bei "Add to PATH" setzen^)
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Richte Python-Umgebung ein ^(einmalig^)...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo Konnte keine Umgebung anlegen.
        pause
        exit /b 1
    )
)

set "VPY=%CD%\.venv\Scripts\python.exe"

"%VPY%" -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo Installiere PyQt6 ^(einmalig^)...
    "%VPY%" -m pip install --quiet --upgrade pip
    "%VPY%" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo Installation fehlgeschlagen.
        pause
        exit /b 1
    )
)

echo Dockwave startet. Beenden ueber Rechtsklick ^> Dock schliessen.
echo Fehler erscheinen in diesem Fenster.
echo.

rem Kein "start" per Doppelklick am Ende, sonst schliesst sich das Fenster
rem sofort und man sieht keine Fehlermeldung.
"%VPY%" main.py %*
set "STATUS=%ERRORLEVEL%"

echo.
if not "%STATUS%"=="0" (
    echo Dockwave wurde mit Fehler %STATUS% beendet. Die Meldung steht oben.
) else (
    echo Dockwave wurde beendet.
)
pause
endlocal