"""Testlauf: das Einstellungsfenster.

Deckt ab: Vollstaendigkeit der Regler, sofortige Wirkung, Programme
verwalten, Fenstergroesse und Position.

WICHTIG: Dieser Test benutzt ausschliesslich ein temporaeres
Konfigurationsverzeichnis. Die echte dock.json wird nie angefasst.

Aufruf:  python tools/settings_test.py
"""

import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dockwave.config as config_mod                        # noqa: E402
from dockwave.config import APP, SEPARATOR, STACK, Config    # noqa: E402
from dockwave.dock_window import DockWindow                  # noqa: E402
from dockwave.qt import QtCore, QtWidgets              # noqa: E402
from dockwave.settings import SettingsDialog          # noqa: E402

FAILURES = []
PRUEFUNGEN = [0]

# Felder, die im Fenster bedienbar sein muessen - eine feste Liste, damit
# eine neue Einstellung nicht stillschweigend fehlt.
SOLL_FELDER = ("size", "magnification", "radius", "spacing", "padding",
               "fps", "position", "layer", "show_running", "minimal")


def check(condition, message):
    PRUEFUNGEN[0] += 1
    if condition:
        print("  ok   %s" % message)
    else:
        print("  FAIL %s" % message)
        FAILURES.append(message)


def _temp_konfiguration():
    """Die echte Konfiguration fuer diesen Lauf unsichtbar machen."""
    echtes_dir = config_mod.APP_DIR
    echter_pfad = config_mod.CONFIG_PATH
    temp = tempfile.mkdtemp(prefix="dockwave-test-")
    config_mod.APP_DIR = temp
    config_mod.CONFIG_PATH = os.path.join(temp, "dock.json")
    return temp, echtes_dir, echter_pfad


def _zuruecksetzen():
    config_mod.APP_DIR, config_mod.CONFIG_PATH = ECHTES_DIR, ECHTER_PFAD


def main():
    global ECHTES_DIR, ECHTER_PFAD

    # Wichtig: Die QApplication muss in einer Variablen stehen bleiben.
    app = QtWidgets.QApplication(sys.argv[:1])
    _ = app

    temp, ECHTES_DIR, ECHTER_PFAD = _temp_konfiguration()
    try:
        laufen()
    finally:
        _zuruecksetzen()
        shutil.rmtree(temp, ignore_errors=True)

    print("\n%d Pruefungen, %d Fehler" % (PRUEFUNGEN[0], len(FAILURES)))
    return 1 if FAILURES else 0


def laufen():
    eintraege = [
        {"type": APP, "path": "/usr/bin/Alpha.app"},
        {"type": APP, "path": "/usr/bin/Beta.app"},
        {"type": SEPARATOR},
        {"type": APP, "path": "/usr/bin/Gamma.app"},
        {"type": STACK},
    ]
    cfg = Config({"entries": eintraege, "size": 46, "fps": 60,
                  "position": "bottom", "layer": "floating"})
    dock = DockWindow(cfg)
    dock.show()

    dialog = SettingsDialog(dock)
    _ = dialog

    print("\n== Das Fenster ist klein genug ==")
    dialog.show()
    dialog.adjustSize()
    breite, hoehe = dialog.width(), dialog.height()
    bildschirm = dialog.screen().availableGeometry() if dialog.screen() else None
    check(breite <= 620, "Fensterbreite %d px bleibt handlich" % breite)
    check(hoehe <= 560, "Fensterhoehe %d px bleibt handlich" % hoehe)
    if bildschirm is not None:
        check(hoehe <= bildschirm.height(),
              "Fensterhoehe passt auf den Bildschirm (%d von %d)"
              % (hoehe, bildschirm.height()))
        check(breite <= bildschirm.width(),
              "Fensterbreite passt auf den Bildschirm (%d von %d)"
              % (breite, bildschirm.width()))

    print("\n== Jede Einstellung hat ein Bedienelement ==")
    bedienbar = set(dialog._regler)
    auswahlen = {"position": dialog.auswahl_position,
                 "layer": dialog.auswahl_ebene}
    for feld, box in auswahlen.items():
        werte = {box.itemData(i) for i in range(box.count())}
        erlaubt = set(config_mod.POSITIONS if feld == "position"
                      else config_mod.LAYERS)
        check(werte == erlaubt, "%s bietet genau %s"
              % (feld, ", ".join(sorted(werte))))
        bedienbar.add(feld)
    schalter = {"show_running": dialog.anzeige_laufend,
                "minimal": dialog.anzeige_minimal}
    bedienbar |= set(schalter)
    for feld in SOLL_FELDER:
        check(feld in bedienbar, "%s ist bedienbar" % feld)
    ueber = bedienbar - set(SOLL_FELDER)
    check(not ueber, "keine Bedienelemente ohne Wirkung (%s)"
          % (", ".join(sorted(ueber)) or "-"))
    check(all(w is not None for w in schalter.values()),
          "die beiden Schalter sind vorhanden")

    print("\n== Die Regler zeigen den gespeicherten Stand ==")
    for feld in ("size", "spacing", "padding", "fps"):
        schieber = dialog._regler[feld][0]
        check(schieber.value() == int(getattr(cfg, feld)),
              "%s steht auf %d wie gespeichert" % (feld, schieber.value()))
    check(dialog._regler["magnification"][0].value()
          == int(round(cfg.magnification * 100)),
          "magnification steht auf %.2f wie gespeichert" % cfg.magnification)
    check(dialog.anzeige_laufend.isChecked() == cfg.show_running,
          "Schalter 'Laufende Programme' stimmt")
    check(dialog.anzeige_minimal.isChecked() == cfg.minimal,
          "Schalter 'Minimal-Modus' stimmt")
    check(dialog.liste.count() == len(cfg.entries),
          "Programmliste zeigt alle %d Eintraege" % len(cfg.entries))

    print("\n== Ein Regler wirkt sofort ==")
    vorher = (dock.width(), dock.height())
    schieber = dialog._regler["size"][0]
    schieber.setValue(72)
    check(cfg.size == 72, "Icon-Groesse uebernommen (%d)" % cfg.size)
    check(dock.width() != vorher[0] or dock.height() != vorher[1],
          "die Leiste hat sich neu aufgebaut (%s -> %s)"
          % (vorher, (dock.width(), dock.height())))
    check(os.path.exists(config_mod.CONFIG_PATH),
          "die Aenderung wurde gespeichert")
    import json
    with open(config_mod.CONFIG_PATH, encoding="utf-8") as fh:
        check(json.load(fh)["size"] == 72, "und wirklich auf die Platte")

    print("\n== Werte ausserhalb des Bereichs werden begrenzt ==")
    dialog._regler["spacing"][0].setValue(40)
    dialog._setze("radius", 9999)
    check(cfg.radius == 600, "Einflussbereich begrenzt auf 600 (%d)" % cfg.radius)
    dialog._setze("fps", 5)
    check(cfg.fps == 24, "Bildrate begrenzt auf 24 (%d)" % cfg.fps)
    dialog._setze("padding", 999)
    check(cfg.padding == 40, "Innenabstand begrenzt auf 40 (%d)" % cfg.padding)

    print("\n== Position und Ebene wirken auf das Fenster ==")
    unten = dock.y()
    dialog._setze("position", "top")
    check(dock.y() < unten, "Position 'Oben' verschiebt die Leiste nach oben")
    dialog._setze("position", "bottom")
    check(dock.y() >= unten - 2, "Position 'Unten' setzt sie zurueck")
    dialog._setze("layer", "top")
    check(cfg.layer == "top", "Ebene 'Ganz oben' uebernommen")
    dialog._setze("layer", "floating")

    print("\n== Programme verwalten ==")
    vorher = len(cfg.entries)
    cfg.add_app("/usr/bin/Delta.app")
    dialog._liste_auffuellen()
    check(dialog.liste.count() == vorher + 1,
          "Programm hinzugefuegt (%d -> %d)" % (vorher, dialog.liste.count()))

    zeile = dialog.liste.row(dialog.liste.item(0))
    dialog.liste.item(zeile).setSelected(True)
    dialog._programm_verschieben(1)
    check(cfg.entries[1]["path"] == "/usr/bin/Alpha.app",
          "Programm eine Stelle nach rechts: %s"
          % cfg.entries[1]["path"].split("/")[-1])
    dialog.liste.item(dialog.liste.row(dialog.liste.item(0))).setSelected(True)
    dialog.liste.item(dialog.liste.row(dialog.liste.item(0))).setSelected(True)
    dialog.liste.clearSelection()
    dialog.liste.item(1).setSelected(True)
    dialog._programm_verschieben(-1)
    check(cfg.entries[0]["path"] == "/usr/bin/Alpha.app",
          "und wieder eine Stelle zurueck nach links")

    dialog.liste.clearSelection()
    dialog.liste.item(0).setSelected(True)
    dialog.liste.item(1).setSelected(True)
    dialog._programm_entfernen()
    check(dialog.liste.count() == vorher - 1,
          "zwei Programme auf einmal entfernt (%d)" % dialog.liste.count())

    print("\n== 'Standard wiederherstellen' ==")
    standard = Config()          # einmalig lesen - spart das Startmenue
    dialog._regler["size"][0].setValue(90)
    dialog._regler["spacing"][0].setValue(30)
    anzahl = len(cfg.entries)
    dialog._standard()
    check(cfg.size == standard.size,
          "Icon-Groesse zurueck auf %d" % cfg.size)
    check(cfg.spacing == standard.spacing,
          "Abstand zurueck auf %d" % cfg.spacing)
    check(len(cfg.entries) == anzahl,
          "die Programmauswahl bleibt erhalten (%d)" % len(cfg.entries))
    check(dialog._regler["size"][0].value() == cfg.size,
          "der Regler zeigt den neuen Wert wieder an")

    print("\n== Das Fenster legt sich neben die Leiste ==")
    dock._recompute_window_geometry()
    dialog._platzieren()
    ueberlappung = dialog.geometry().intersects(dock.geometry())
    check(not ueberlappung,
          "Fenster und Leiste ueberlappen sich nicht (Fenster %s, Leiste %s)"
          % (dialog.geometry().getRect(), dock.geometry().getRect()))

    print("\n== Schliessen speichert ==")
    dialog._setze("radius", 300)
    dialog.close()
    with open(config_mod.CONFIG_PATH, encoding="utf-8") as fh:
        check(json.load(fh)["radius"] == 300, "der letzte Stand liegt auf der Platte")

    print("\n== Das Rechtsklick-Menue wiederholt nichts ==")
    dock._rebuild()

    def _menue_lesen(index):
        """Das Menue aufbauen, aber nicht anzeigen."""
        gefangen = {}

        def statt_anzeigen(self, pos):
            gefangen["text"] = [a.text() for a in self.actions() if a.text()]

        original = QtWidgets.QMenu.exec
        QtWidgets.QMenu.exec = statt_anzeigen
        try:
            dock._context_menu(index, QtCore.QPoint(10, 10))
        finally:
            QtWidgets.QMenu.exec = original
        return gefangen.get("text", [])

    am_icon = _menue_lesen(next(i for i, e in enumerate(dock.config.entries)
                            if e["type"] == APP))
    am_ordner = _menue_lesen(next((i for i, e in enumerate(dock.config.entries)
                                   if e["type"] == STACK), -1))
    leer = _menue_lesen(-1)

    check("Einstellungen…" in leer,
          "das Menue fuehrt zum Einstellungsfenster")
    check("Aus Dock entfernen" in am_icon,
          "am Programm steht weiterhin 'Aus Dock entfernen'")
    check("Öffnen" in am_icon, "am Programm steht weiterhin 'Öffnen'")
    check("Ordner ausblenden" in am_ordner,
          "am Ordner steht weiterhin 'Ordner ausblenden'")
    check("Dock schließen" in leer, "das Menue kann das Dock beenden")

    doppelt = ("Position", "Ebene", "Icon-Größe", "Abstand", "Einflussbereich",
               "Vergrößerung", "Minimal-Modus", "Laufende Programme")
    gefunden = sorted({t for t in doppelt
                       if any(t == x or x.startswith(t) for x in leer)})
    check(not gefunden, "im Menue steht keine Einstellung doppelt (%s)"
          % (", ".join(gefunden) or "-"))
    check(len(leer) <= 4,
          "das Menue ist kurz geworden: %s" % ", ".join(leer))

    dock.close()


if __name__ == "__main__":
    ECHTES_DIR, ECHTER_PFAD = None, None
    sys.exit(main())