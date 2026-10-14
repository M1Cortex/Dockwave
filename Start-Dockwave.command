#!/bin/bash
# Dockwave starten - im Finder doppelklicken.
#
# Beim ersten Start wird eine virtuelle Python-Umgebung im Projektordner
# angelegt und PyQt6 installiert. Das dauert einmalig etwa eine Minute.

cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
            PY="$candidate"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "Kein Python 3.9 oder neuer gefunden."
    echo "Installiere es zum Beispiel mit:  brew install python"
    read -r -p "Druecke Enter zum Beenden..."
    exit 1
fi

VENV=".venv"
if [ ! -d "$VENV" ]; then
    echo "Richte Python-Umgebung ein (einmalig)..."
    "$PY" -m venv "$VENV" || {
        echo "Konnte keine Umgebung anlegen."
        read -r -p "Druecke Enter zum Beenden..."
        exit 1
    }
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

if ! python -c "import PyQt6" >/dev/null 2>&1; then
    echo "Installiere PyQt6 (einmalig)..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt || {
        echo "Installation fehlgeschlagen."
        read -r -p "Druecke Enter zum Beenden..."
        exit 1
    }
fi

echo "Dockwave startet. Beenden ueber Rechtsklick > Dock schliessen."
echo "Fehler erscheinen in diesem Fenster."
echo

# Kein "exec": sonst schliesst sich das Fenster sofort bei einem Absturz
# und die Fehlermeldung ist weg.
python main.py "$@"
STATUS=$?

echo
if [ $STATUS -ne 0 ]; then
    echo "Dockwave wurde mit Fehler $STATUS beendet."
    echo "Die vollstaendige Meldung steht oben."
else
    echo "Dockwave wurde beendet."
fi
read -r -p "Druecke Enter zum Schliessen..."