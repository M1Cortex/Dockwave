"""Schutzhut fuer die Testlaeufe.

Die Tests bauen eine Dock-Leiste mit erfundenen Programmen (`App00.app` ...)
und rufen am Ende `dock.close()` auf. Sobald beim Schließen gespeichert
wird, landen diese erfundenen Programme in der echten Konfiguration des
Benutzers - genau das ist einmal passiert.

Dieses Modul schiebt deshalb Config-Verzeichnis und -Datei auf ein
temporaeres Verzeichnis um. Der Aufruf muss **vor** dem ersten Zugriff auf
`dockwave.config` stehen:

    import sys, os
    sys.path.insert(0, ...)
    from _testconfig import schutz   # noqa: E402  (setzt die Umleitung)
    schutz()                         # noqa: E402
    from dockwave.config import Config   # erst danach

Der Pfad zur echten Datei steht in `ECHTER_PFAD`, falls ein Test nachsehen
will, ob sie unangetastet blieb.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dockwave.config as config_mod

ECHTER_PFAD = config_mod.CONFIG_PATH
ECHTES_DIR = config_mod.APP_DIR
_VERZEICHNIS = None


def schutz():
    """Die echte Konfiguration fuer diesen Lauf unerreichbar machen."""
    global _VERZEICHNIS
    if _VERZEICHNIS is not None:
        return _VERZEICHNIS
    _VERZEICHNIS = tempfile.mkdtemp(prefix="dockwave-test-")
    config_mod.APP_DIR = _VERZEICHNIS
    config_mod.CONFIG_PATH = os.path.join(_VERZEICHNIS, "dock.json")
    return _VERZEICHNIS


def zuruecksetzen():
    """Die echte Pfade wiederherstellen und das Temp-Verzeichnis loeschen."""
    global _VERZEICHNIS
    import shutil
    config_mod.APP_DIR, config_mod.CONFIG_PATH = ECHTES_DIR, ECHTER_PFAD
    if _VERZEICHNIS:
        shutil.rmtree(_VERZEICHNIS, ignore_errors=True)
    _VERZEICHNIS = None


def unveraendert():
    """True, wenn die echte Konfiguration seit Prozessbeginn unberuehrt ist."""
    if not os.path.exists(ECHTER_PFAD):
        return True
    with open(ECHTER_PFAD, "rb") as fh:
        return b"App%02d" not in fh.read()