"""Testlauf: das Einstellungsfenster.

Deckt ab: Vollstaendigkeit der Regler, sofortige Wirkung, Programme
verwalten, Fenstergroesse und Position.

WICHTIG: Dieser Test benutzt ausschliesslich ein temporaeres
Konfigurationsverzeichnis. Die echte dock.json wird nie angefasst.

Aufruf:  python tools/settings_test.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dockwave.config as config_mod                        # noqa: E402
from _testconfig import schutz, zuruecksetzen               # noqa: E402
schutz()  # muss vor dem ersten Zugriff auf dockwave.config stehen

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


def main():
    # Wichtig: Die QApplication muss in einer Variablen stehen bleiben.
    app = QtWidgets.QApplication(sys.argv[:1])
    _ = app

    try:
        laufen()
    finally:
        zuruecksetzen()

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

    print("\n== Trenner einfuegen ==")

    def _trenner():
        return sum(1 for e in cfg.entries if e["type"] == SEPARATOR)

    anzahl = len(cfg.entries)
    dialog.liste.clearSelection()
    dialog._programm_trenner()
    check(cfg.entries[-1]["type"] == SEPARATOR,
          "ohne Auswahl landet der Trenner am Ende")
    check(dialog.liste.count() == anzahl + 1,
          "die Liste zeigt den neuen Trenner (%d)" % dialog.liste.count())

    dialog.liste.clearSelection()
    dialog.liste.item(0).setSelected(True)
    davor = cfg.entries[0]["type"]
    dialog._programm_trenner()
    check(cfg.entries[0]["type"] == SEPARATOR,
          "der Trenner steht vor dem markierten Eintrag")
    check(cfg.entries[1]["type"] == davor,
          "der markierte Eintrag rueckt einen Platz weiter")

    stand = _trenner()
    dialog.liste.clearSelection()
    dialog._programm_trenner()
    check(_trenner() == stand + 1,
          "mehrere Trenner sind moeglich (%d)" % _trenner())

    letzte = max(i for i, e in enumerate(cfg.entries) if e["type"] == SEPARATOR)
    erster_app = next(i for i, e in enumerate(cfg.entries) if e["type"] == APP)
    check(dock._pixmaps[letzte] is None,
          "der Trenner bekommt kein Icon, sondern wird gezeichnet")
    dock._layout(dock.width() / 2.0)
    check(len(dock._bounds) == len(cfg.entries),
          "jeder Trenner belegt einen Platz in der Leiste (%d von %d)"
          % (len(dock._bounds), len(cfg.entries)))
    check(dock.base_sizes()[letzte] < dock.base_sizes()[erster_app],
          "der Trenner ist schmaler als ein Icon (%.0f zu %.0f px)"
          % (dock.base_sizes()[letzte], dock.base_sizes()[erster_app]))

    with open(config_mod.CONFIG_PATH, encoding="utf-8") as fh:
        gespeichert = json.load(fh)
    check(sum(1 for e in gespeichert["entries"] if e["type"] == SEPARATOR)
          == _trenner(), "die Trenner liegen auf der Platte")

    dialog.liste.clearSelection()
    zeile = next(i for i in range(dialog.liste.count())
                 if cfg.entries[i]["type"] == SEPARATOR)
    dialog.liste.item(zeile).setSelected(True)
    vor_entfernen = _trenner()
    dialog._programm_entfernen()
    check(_trenner() == vor_entfernen - 1,
          "ein Trenner laesst sich wieder entfernen (%d)" % _trenner())

    print("\n== Innenabstand ==")

    def _masse():
        """Alle Groessen, die der Innenabstand beeinflussen darf."""
        dock._layout(dock._cursor_x)
        panel = dock._panel_rect
        return {
            "panel_breit": panel.width(),
            "panel_hoch": panel.height(),
            "panel_links": panel.left(),
            "fenster": (dock.width(), dock.height()),
            "icons": [round(b.width(), 2) for b in dock._bounds],
            "abstaende": [round(dock._bounds[i + 1].left()
                                - dock._bounds[i].right(), 2)
                          for i in range(len(dock._bounds) - 1)],
            "linker_abstand": round(dock._bounds[0].left() - panel.left(), 2),
            "rechter_abstand": round(panel.right() - dock._bounds[-1].right(), 2),
        }

    dock._cursor_x = -1.0e9          # Zeiger weg: reine Ruhelage
    dock._cursor_y = -1.0e9

    schieber = dialog._regler["padding"][0]
    check((schieber.minimum(), schieber.maximum()) == (2, 40),
          "der Regler laeuft von %d bis %d px"
          % (schieber.minimum(), schieber.maximum()))

    schieber.setValue(2)
    eng = _masse()
    schieber.setValue(40)
    weit = _masse()
    schieber.setValue(10)
    normal = _masse()

    # Rundungsabstand: die Rechnung laeuft ueber Gleitkommazahlen.
    def _ist(ist, soll):
        return abs(ist - soll) < 0.01

    check(_ist(weit["panel_breit"] - eng["panel_breit"],
              2 * (40 - 2) + (40 - 2) * (len(weit["icons"]) - 1)),
          "das Panel waechst um Rand *und* Iconabstand (%.1f zu %.1f px)"
          % (eng["panel_breit"], weit["panel_breit"]))
    check(_ist(weit["panel_hoch"] - eng["panel_hoch"], 2 * (40 - 2)),
          "die Panelhoehe genauso (%.1f zu %.1f px)"
          % (eng["panel_hoch"], weit["panel_hoch"]))
    schritt = 10 - 2
    erwartet = 2 * schritt + schritt * len(normal["abstaende"])
    check(_ist(normal["panel_breit"] - eng["panel_breit"], erwartet),
          "und auch dazwischen stimmt es: Rand %dx%d, Iconabstaende %dx%d"
          % (normal["panel_breit"] - eng["panel_breit"], schritt,
             len(normal["abstaende"]), schritt))

    check(eng["linker_abstand"] == 2 and weit["linker_abstand"] == 40,
          "links steht der eingestellte Abstand: %d px bzw. %d px"
          % (eng["linker_abstand"], weit["linker_abstand"]))
    check(eng["rechter_abstand"] == 2 and weit["rechter_abstand"] == 40,
          "rechts genauso: %d px bzw. %d px"
          % (eng["rechter_abstand"], weit["rechter_abstand"]))

    check(eng["icons"] == weit["icons"],
          "die Icons selbst bleiben gleich gross (%s px)"
          % eng["icons"][0])
    check(weit["abstaende"][0] - eng["abstaende"][0] == 40 - 2,
          "die Icons ruecken um den Innenabstand auseinander: %d -> %d px"
          % (eng["abstaende"][0], weit["abstaende"][0]))
    check(weit["abstaende"] == [cfg.spacing + 40] * len(weit["abstaende"]),
          "der Abstand ist 'Abstand' + Innenabstand = %d px"
          % weit["abstaende"][0])
    check(cfg.spacing == 28,
          "der eigene Regler 'Abstand' bleibt unberuehrt (%d px)" % cfg.spacing)
    check(weit["fenster"][0] > eng["fenster"][0]
          and weit["fenster"][1] > eng["fenster"][1],
          "das Fenster waechst mit: %s zu %s" % (eng["fenster"], weit["fenster"]))

    schieber.setValue(20)
    check(cfg.padding == 20, "der Wert steht in der Konfiguration (%d)"
          % cfg.padding)
    with open(config_mod.CONFIG_PATH, encoding="utf-8") as fh:
        check(json.load(fh)["padding"] == 20, "und ist gespeichert")

    dialog._setze("padding", 999)
    check(cfg.padding == 40, "zu grosse Werte werden begrenzt (%d)" % cfg.padding)
    dialog._setze("padding", -5)
    check(cfg.padding == 2, "zu kleine Werte ebenso (%d)" % cfg.padding)

    schieber.setValue(10)
    dock._layout(dock._cursor_x)
    flaeche = dock.mask().boundingRect()
    check(flaeche.width() >= dock._panel_rect.width(),
          "die klickbare Flaeche folgt dem Panel (%d >= %.0f px)"
          % (flaeche.width(), dock._panel_rect.width()))

    print("\n== Innenabstand beim Vergrößern ==")
    for wert in (2, 40):
        schieber.setValue(wert)
        dock._cursor_x = dock._bounds[1].center().x()
        dock._cursor_y = dock._bounds[1].center().y()
        dock._layout(dock._cursor_x)
        panel = dock._panel_rect
        groesstes = max(dock._bounds, key=lambda b: b.width())
        oben = groesstes.top() - panel.top()
        unten = panel.bottom() - groesstes.bottom()
        check(oben >= wert - 0.01 and unten >= wert - 0.01,
              "bei %d px Innenabstand ragt das groesste Icon nicht ueber "
              "den Rand (oben %.0f, unten %.0f)" % (wert, oben, unten))
        check(dock._bounds[1].center().x() == groesstes.center().x()
              or abs(dock._bounds[1].center().x()
                     - groesstes.center().x()) < 1.0,
              "das groesste Icon liegt noch unter dem Zeiger")
    schieber.setValue(10)
    dock.leaveEvent(None)
    dock._layout(-1.0e9)

    print("\n== Das Fenster waechst mit ==")
    dialog.show()
    dialog.adjustSize()
    klein = (dialog.liste.width(), dialog.liste.height())
    dialog.resize(dialog.width() + 420, dialog.height() + 220)
    QtWidgets.QApplication.processEvents()
    gross = (dialog.liste.width(), dialog.liste.height())
    check(gross[0] > klein[0] + 300,
          "die Programmliste wird breiter: %d -> %d px" % (klein[0], gross[0]))
    check(gross[1] > klein[1] + 150,
          "die Programmliste wird hoeher: %d -> %d px" % (klein[1], gross[1]))
    for beschriftung, box in (("Leiste", 0), ("Verhalten", 1), ("Programme", 2)):
        gruppe = [w for w in dialog.findChildren(QtWidgets.QGroupBox)
                  if w.title() == beschriftung][0]
        check(gruppe.width() > dialog.width() * 0.9,
              "die Gruppe '%s' fuellt das verbreiterte Fenster (%d px)"
              % (beschriftung, gruppe.width()))
    dialog.resize(dialog.sizeHint())
    QtWidgets.QApplication.processEvents()

    print("\n== Die Pfeile bleiben benutzbar ==")
    dock._neu_aufbauen()
    anfang = [dict(e) for e in cfg.entries]

    def _knopf(zeichen):
        for b in dialog.findChildren(QtWidgets.QPushButton):
            if b.text() == zeichen:
                b.click()
                return
        raise AssertionError("Knopf %r fehlt" % zeichen)

    def _markiert():
        return [dialog.liste.row(x) for x in dialog.liste.selectedItems()]

    dialog.liste.clearSelection()
    dialog.liste.item(0).setSelected(True)
    _knopf("▼")
    check(len(_markiert()) == 1,
          "nach 'runter' ist genau eine Zeile markiert (%s)" % _markiert())
    check(cfg.entries != anfang, "das Programm ist tatsaechlich gewandert")

    _knopf("▼")          # genau der Schritt, der vorher ins Leere lief
    check(len(_markiert()) == 1,
          "der zweite Klick geht auch noch (%s)" % _markiert())
    check(cfg.entries[2]["type"] == SEPARATOR,
          "und der Stapel wandert weiter")

    gewandert = cfg.entries[2].get("path")
    _knopf("▲")
    check(cfg.entries[1].get("path") == gewandert,
          "'hoch' funktioniert wieder (%s)"
          % (cfg.entries[1].get("path") or cfg.entries[1]["type"]))

    trenn_stelle = next((i for i, e in enumerate(cfg.entries)
                      if e["type"] == SEPARATOR
                      and i + 1 < len(cfg.entries)), None)
    check(trenn_stelle is not None,
          "es gibt einen Trenner, den man verschieben kann")
    if trenn_stelle is not None:
        dialog.liste.clearSelection()
        dialog.liste.item(trenn_stelle).setSelected(True)
        _knopf("▼")
        check(len(_markiert()) == 1,
              "auch beim Trenner bleibt es bei einer Markierung (%s)"
              % _markiert())
        check(cfg.entries[trenn_stelle + 1]["type"] == SEPARATOR,
              "'runter' schiebt den Trenner nach unten")
        _knopf("▲")
        check(cfg.entries[trenn_stelle]["type"] == SEPARATOR,
              "'hoch' holt ihn zurueck (Stelle %d)" % trenn_stelle)

    anzahl = len(cfg.entries)
    dialog.liste.clearSelection()
    dialog.liste.item(0).setSelected(True)
    _knopf("▼")
    _knopf("▲")
    check(len(cfg.entries) == anzahl,
          "es geht nichts verloren (%d Eintraege)" % len(cfg.entries))
    check(dialog.liste.count() == anzahl, "die Liste ist vollstaendig")

    print("\n== Ein Groessenregler laesst die Leiste nicht springen ==")

    def _unter_dem_zeiger():
        dock._layout(dock._cursor_x)
        return dock._hover_index, [round(b.width(), 1) for b in dock._bounds]

    dock._cursor_x = dock._bounds[1].center().x()
    dock._cursor_y = dock._bounds[1].center().y()
    for feld, wert in (("padding", 24), ("size", 60), ("padding", 8),
                       ("spacing", 30), ("size", 46)):
        vorher, breiten = _unter_dem_zeiger()
        dialog._regler[feld][0].setValue(wert)
        nachher, breiten_neu = _unter_dem_zeiger()
        check(vorher == nachher,
              "%s=%d: dasselbe Icon bleibt unter dem Zeiger (%s)"
              % (feld, wert, vorher))
        check(dock._bounds != [],
              "%s=%d: die Leiste ist sofort gezeichnet" % (feld, wert))
        grund = dock.config.effective_size
        check(max(breiten_neu) > grund * 1.05,
              "%s=%d: das Icon darunter ist vergroessert (%.0f statt %.0f px)"
              % (feld, wert, max(breiten_neu), grund))
        _ = breiten
    dock.leaveEvent(None)

    print("\n== Das Rechtsklick-Menue wiederholt nichts ==")
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
    sys.exit(main())