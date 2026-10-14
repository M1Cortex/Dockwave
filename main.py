#!/usr/bin/env python3
"""Dockwave starten.

Doppelklickbar auf dem Mac (die Datei startet dann ./Start-Dockwave.command),
oder direkt:  python3 main.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dockwave.app import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())