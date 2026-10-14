#!/bin/bash
# Dockwave beenden, falls es noch laeuft.

cd "$(dirname "$0")" || exit 1

# Sucht nur nach Prozessen, deren Kommandozeile wirklich dieses Projekt
# enthaelt - nicht nach jedem python-Prozess im System.
PIDS=$(pgrep -f "Dockwave/main[.]py" || true)

if [ -z "$PIDS" ]; then
    echo "Dockwave laeuft nicht."
    exit 0
fi

echo "Beende Dockwave (PID: $PIDS)..."
kill $PIDS 2>/dev/null
sleep 1
kill -9 $PIDS 2>/dev/null
echo "Erledigt."