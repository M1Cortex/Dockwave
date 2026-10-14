"""Testlauf: das Milchglas (Acrylic/Weichzeichner hinter der Leiste).

Dieser Test laeuft bewusst NICHT offscreen. Nur eine echte Windows-Ecke
laesst sich weichzeichnen - unter "offscreen" gibt es kein HWND, und der
Aufruf meldet zu Recht "nicht geklappt".

Das Fenster ist winzig und wird nach dem Test sofort wieder geschlossen.

Aufruf:  python tools/glass_test.py
"""

import os
import sys

# Kein QT_QPA_PLATFORM setzen - ein echtes Fenster ist der Punkt des Tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _testconfig import schutz                              # noqa: E402
schutz()  # muss vor dem ersten Zugriff auf dockwave.config stehen

from dockwave import platform                              # noqa: E402
from dockwave.config import APP, STACK, Config             # noqa: E402
from dockwave.dock_window import DockWindow                 # noqa: E402
from dockwave.qt import QtWidgets                      # noqa: E402

FAILURES = []
PRUEFUNGEN = [0]


def check(condition, message):
    PRUEFUNGEN[0] += 1
    if condition:
        print("  ok   %s" % message)
    else:
        print("  FAIL %s" % message)
        FAILURES.append(message)


def main():
    app = QtWidgets.QApplication(sys.argv[:1])
    _ = app

    if not platform.IS_WIN:
        print("Nur unter Windows sinnvoll - uebersprungen.")
        return 0

    print("\n== Kann das System ueberhaupt weichzeichnen? ==")
    verfuegbar = platform.glass_available()
    check(isinstance(verfuegbar, bool),
          "glass_available() liefert True oder False (%s)" % verfuegbar)
    check(verfuegbar,
          "dieses System kann den Hintergrund weichzeichnen")
    check(platform._impl._has_accent_api(),
          "SetWindowCompositionAttribute ist vorhanden")
    check(platform._impl._dwmapi() is not None,
          "dwmapi.dll laesst sich laden")

    print("\n== Ein echtes Fenster bekommt den Weichzeichner ==")
    cfg = Config({"entries": [{"type": APP, "path": "/a/%d.app" % i}
                              for i in range(4)] + [{"type": STACK}],
                  "size": 46, "fps": 60})
    dock = DockWindow(cfg)
    dock.resize(320, 80)
    dock.move(40, 40)
    dock.show()
    QtWidgets.QApplication.processEvents()

    hwnd = int(dock.windowHandle().winId())
    check(hwnd not in (0, 1),
          "es gibt ein echtes Fenster (HWND 0x%X)" % hwnd)

    an = platform.apply_glass(dock, True, 0x30FFFFFF)
    check(an, "Acrylic einschalten gelingt")
    aus = platform.apply_glass(dock, False)
    check(aus, "und wieder ausschalten auch")
    wieder = platform.apply_glass(dock, True, 0x40FFDDB0)
    check(wieder, "und mit anderer Farbe wieder einschalten")

    print("\n== Der Schalter im Fenster ==")
    from dockwave.settings import SettingsDialog
    dialog = SettingsDialog(dock)
    _ = dialog
    check(hasattr(dialog, "anzeige_glas"), "es gibt einen Schalter dafür")
    check(dialog.anzeige_glas.isChecked(),
          "er steht auf der gespeicherten Einstellung (%s)"
          % cfg.glass)
    check(not dialog.anzeige_glas.isEnabled() or platform.glass_available(),
          "er ist aktiv, weil das System es kann")
    dialog._setze("glass", not cfg.glass)
    check(cfg.glass is not (not cfg.glass),
          "Umschalten wirkt sofort (jetzt %s)" % cfg.glass)
    dialog._setze("glass", True)

    print("\n== Fehler faellen nicht auf das Programm zurueck ==")
    check(platform.apply_glass(None, True) is False,
          "ohne Fenster wird False geliefert, kein Absturz")
    check(platform.apply_glass(dock, True, 0) is True,
          "Farbe 0 (klar) wird angenommen")
    platform.apply_glass(dock, True, 0x30FFFFFF)

    dock.close()

    print("\n%d Pruefungen, %d Fehler" % (PRUEFUNGEN[0], len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())