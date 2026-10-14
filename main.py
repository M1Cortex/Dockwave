#!/usr/bin/env python3
"""Dockwave starten.

Doppelklickbar auf dem Mac (die Datei startet dann ./Start-Dockwave.command),
oder direkt:  python3 main.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _log_dir():
    """Ort fuer die Absturz-Logdatei.

    Neben der Programmdatei, wenn dort geschrieben werden darf (dann auch
    bei der gepackten .exe), sonst im Benutzerprofil.
    """
    if getattr(sys, "frozen", False):
        basis = os.path.dirname(sys.executable)
    else:
        basis = os.path.dirname(os.path.abspath(__file__))
    if os.access(basis, os.W_OK):
        return basis
    return os.path.join(os.path.expanduser("~"), "AppData", "Roaming")


def _sturz_fehler_fangen():
    """Schreibt Abstuerze in eine Logdatei und zeigt einen Hinweis.

    Ohne Fenster fuer die Konsole - etwa bei der gepackten .exe - waere
    ein Absturz sonst voellig lautlos.

    Qt wird erst nach dem Schreiben der Logdatei geladen: genau dann, wenn
    es fehlt, ist das Log die einzige Chance, etwas mitzubekommen.
    """
    def behandler(typ, wert, tb):
        text = "".join(traceback.format_exception(typ, wert, tb))
        pfad = os.path.join(_log_dir(), "dockwave-fehler.log")
        try:
            with open(pfad, "a", encoding="utf-8") as fh:
                fh.write(text)
                fh.write("\n" + "-" * 60 + "\n")
        except OSError:
            pfad = "(keine Datei schreibbar)"
        try:
            from dockwave.qt import QtWidgets

            QtWidgets.QMessageBox.critical(
                None, "Dockwave wurde beendet",
                "Es ist ein unerwarteter Fehler aufgetreten:\n\n%s\n\n"
                "Einzelheiten stehen in:\n%s" % (wert, pfad))
        except Exception:
            pass

    sys.excepthook = behandler


if __name__ == "__main__":
    _sturz_fehler_fangen()
    from dockwave.app import run

    sys.exit(run())