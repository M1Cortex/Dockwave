@echo off
rem Dockwave beenden, falls es noch laeuft.

setlocal
cd /d "%~dp0"

rem Sucht nur nach Prozessen, deren Kommandozeile wirklich dieses Projekt
rem enthaelt - nicht nach jedem Python-Prozess im System.
for /f "tokens=2 delims=," %%P in ('wmic process where "name='python.exe'" get processid,commandline /format:csv 2^>nul ^| find "Dockwave"') do (
    if not "%%P"=="" (
        echo Beende Dockwave ^(PID %%P^)...
        taskkill /PID %%P /T /F >nul 2>&1
    )
)

rem Zweiter Versuch fuer neuere Windows-Versionen ohne wmic.
for /f "tokens=2" %%P in ('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" ^| Where-Object { $_.CommandLine -like '*main.py*' } ^| ForEach-Object { $_.ProcessId }" 2^>nul') do (
    if not "%%P"=="" (
        echo Beende Dockwave ^(PID %%P^)...
        taskkill /PID %%P /T /F >nul 2>&1
    )
)

echo Fertig.
timeout /t 2 >nul
endlocal