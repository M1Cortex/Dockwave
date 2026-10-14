"""Testlauf: Dock offscreen instanziieren, Layout ueber Cursorposition pruefen.

Kein Test fuer die Nutzer, nur zur Absicherung waehrend der Entwicklung.
Aufruf:  python3 tools/smoke_test.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _testconfig import schutz                              # noqa: E402
schutz()  # muss vor dem ersten Zugriff auf dockwave.config stehen

from dockwave.config import APP, SEPARATOR, STACK, Config      # noqa: E402
from dockwave.dock_window import DockWindow                    # noqa: E402
from dockwave.qt import QtCore, QtGui, QtWidgets               # noqa: E402

FAILURES = []


def check(condition, message):
    if condition:
        print("  ok   %s" % message)
    else:
        print("  FAIL %s" % message)
        FAILURES.append(message)


def main():
    # Wichtig: Die QApplication muss in einer Variablen stehen bleiben.
    # Ohne Referenz gibt Python sie sofort wieder frei und alles Weitere
    # stuerzt ab.
    app = QtWidgets.QApplication(sys.argv[:1])
    _ = app  # nur zur Haeltung der Referenz noetig

    entries = [
        {"type": APP, "path": "/Applications/Alpha.app"},
        {"type": APP, "path": "/Applications/Beta.app"},
        {"type": SEPARATOR},
        {"type": APP, "path": "/Applications/Gamma.app"},
        {"type": STACK},
    ]
    cfg = Config({"entries": entries, "size": 46, "fps": 60})
    dock = DockWindow(cfg)

    print("\n== Fenstergroesse ==")
    w = dock.width()
    check(w > 200, "Fensterbreite %d px ist sinnvoll" % w)
    check(dock.height() > 50, "Fensterhoehe %d px ist sinnvoll" % dock.height())

    print("\n== Neutralzustand (Cursor weg) ==")
    dock._cursor_x = -1.0e9
    dock._layout(dock._cursor_x)
    check(dock._hover_index == -1, "kein Hover ohne Cursor")
    widths = [r.width() for r in dock._bounds]
    check(all(abs(x - cfg.effective_size) < 0.01 for i, x in enumerate(widths)
              if cfg.entries[i]["type"] != SEPARATOR),
          "alle Icons in Basisgroesse: %s" % ["%.0f" % x for x in widths])
    check(dock._panel_rect.width() <= w,
          "Panel (%d) passt ins Fenster (%d)" % (dock._panel_rect.width(), w))

    print("\n== Hover in der Mitte ==")
    dock._layout(-1.0e9)
    centers = [r.center().x() for r in dock._bounds]
    dock._cursor_x = centers[1]
    dock._layout(dock._cursor_x)
    check(dock._hover_index == 1, "Index 1 ist hovered (ist %d)" % dock._hover_index)
    hovered = dock._bounds[1]
    biggest = max(range(len(dock._bounds)), key=lambda i: dock._bounds[i].width())
    check(biggest == 1, "groesstes Icon ist das hovered (Index %d)" % biggest)
    check(hovered.width() > cfg.effective_size * (cfg.magnification - 0.05),
          "Hover-Icon ist stark vergroessert: %.1f px (Basis %.0f)"
          % (hovered.width(), cfg.effective_size))
    check(abs(hovered.center().x() - centers[1]) < hovered.width() / 2.0,
          "der Zeiger liegt auf dem vergroesserten Icon (Mitte %.1f px daneben)"
          % abs(hovered.center().x() - centers[1]))
    neighbours = [dock._bounds[0].width(), dock._bounds[3].width()]
    check(all(n > cfg.effective_size for n in neighbours),
          "Nachbarn sind mitvergroessert: %s" % ["%.1f" % n for n in neighbours])
    gap = hovered.left() - dock._bounds[0].right()
    check(gap > 0, "Abstand Nachbar/Hover bleibt positiv: %.1f px" % gap)
    check(dock._panel_rect.width() <= w,
          "Panel (%d) passt ins Fenster (%d)" % (dock._panel_rect.width(), w))
    check(dock._panel_rect.left() >= 0 and dock._panel_rect.right() <= w,
          "Panel bleibt im Fenster: %.0f..%.0f"
          % (dock._panel_rect.left(), dock._panel_rect.right()))

    print("\n== Hover am linken Rand ==")
    dock._cursor_x = centers[0] - 2
    dock._layout(dock._cursor_x)
    check(dock._panel_rect.left() >= 0,
          "linkes Panel bleibt im Fenster (%.1f)" % dock._panel_rect.left())
    check(abs(dock._bounds[0].center().x() - dock._cursor_x) < dock._bounds[0].width() / 2.0,
          "auch das Rand-Icon traegt den Zeiger (Mitte %.1f px daneben)"
          % abs(dock._bounds[0].center().x() - dock._cursor_x))

    print("\n== Hover am rechten Rand ==")
    dock._cursor_x = centers[-1] + 2
    dock._layout(dock._cursor_x)
    check(dock._panel_rect.right() <= w,
          "rechtes Panel bleibt im Fenster (%.0f <= %d)"
          % (dock._panel_rect.right(), w))

    print("\n== Stetigkeit ueber 400 Cursorpositionen ==")
    prev = None
    max_jump = 0.0
    worst = None
    for step in range(400):
        x = centers[0] + (centers[-1] - centers[0]) * step / 399.0
        dock._cursor_x = x
        dock._layout(x)
        cur = [(r.center().x(), r.width()) for r in dock._bounds]
        if prev is not None:
            for i, ((cx, cw), (px, pw)) in enumerate(zip(cur, prev)):
                jump = abs(cx - px) + abs(cw - pw)
                if jump > max_jump:
                    max_jump = jump
                    worst = i
        prev = cur
    check(max_jump < 6.0,
          "groesster Positionssprung %.2f px (Icon %s) bleibt fluessig"
          % (max_jump, worst))

    print("\n== Panel waechst und schrumpft stetig ==")
    dock._layout(-1.0e9)
    rest = dock._panel_rect.width()
    # Der Zeiger wird in Fensterguerteln gesetzt - so, wie Qt es spaeter auch
    # liefert. Dock-Koordinaten hier waeren ein Vergleich zweier verschiedener
    # Bezugssysteme und ergaeben je nach Leistenbreite falsche Werte.
    start = dock._bounds[1].left() - 40.0
    span = dock._panel_rect.right() - start
    widths = []
    for step in range(0, 201):
        dock._cursor_x = start + step * span / 200.0
        dock._layout(dock._cursor_x)
        widths.append(dock._panel_rect.width())
    check(max(widths) >= rest, "Panel wird beim Hover breiter: %.0f -> %.0f"
          % (rest, max(widths)))
    check(widths[0] < widths[len(widths) // 2], "Panel waechst von aussen nach innen")
    deltas = [abs(widths[i + 1] - widths[i]) for i in range(len(widths) - 1)]
    check(max(deltas) < 3.0, "kein Sprung beim Panelwechsel (max %.2f px)" % max(deltas))

    print("\n== Positionstreue bei vielen Icons ==")
    many = [{"type": APP, "path": "/Applications/App%02d.app" % i} for i in range(12)]
    dock.config.entries = many
    dock._rebuild()
    dock._layout(-1.0e9)
    rest = [r.center().x() for r in dock._bounds]
    outside = []
    middle = 0.0
    for i, x in enumerate(rest):
        dock._cursor_x = x
        dock._layout(x)
        rect = dock._bounds[i]
        if not rect.contains(x, rect.center().y()):
            outside.append(i)
        if 3 <= i <= 8:
            middle = max(middle, abs(rect.center().x() - x))
    check(not outside,
          "der Zeiger liegt in jedem vergroesserten Icon auf dem Icon (%s)"
          % ("ja" if not outside else "nein bei %s" % outside))
    check(middle < dock.config.effective_size * 0.12,
          "in der Dock-Mitte weicht das Icon nur %.1f px vom Zeiger ab" % middle)

    dock.config.entries = entries
    dock._rebuild()

    print("\n== Abstand und Einflussbereich ==")
    # Der Innenabstand wirkt auch zwischen den Icons, deshalb ist die
    # erwartete Luft nicht der Abstand allein.
    polster = dock.config.padding
    widths = {}
    for spacing in (0, 8, 28):
        dock.config.spacing = spacing
        dock._recompute_window_geometry()
        dock._layout(-1.0e9)
        gap = dock._bounds[1].left() - dock._bounds[0].right()
        widths[spacing] = gap
        check(abs(gap - (spacing + polster)) < 0.5,
              "Abstand %d px + Innenabstand %d px ergibt %d px Luft "
              "(Fenster %d px)" % (spacing, polster, spacing + polster,
                                   dock.width()))
    check(widths[28] > widths[8] > widths[0],
          "mehr Abstand macht die Leiste breiter: %s"
          % ["%.0f" % v for v in widths.values()])
    check(dock._panel_rect.width() <= dock.width(),
          "Panel passt auch bei weitem Abstand ins Fenster (%d <= %d)"
          % (dock._panel_rect.width(), dock.width()))
    dock.config.spacing = 8

    grown = {}
    for radius in (110, 340):
        dock.config.radius = radius
        dock._layout(-1.0e9)
        centers = [r.center().x() for r in dock._bounds]
        dock._cursor_x = centers[1]
        dock._layout(dock._cursor_x)
        grown[radius] = dock._bounds[3].width() if len(dock._bounds) > 3 else 0.0
        dock._layout(-1.0e9)
    check(grown[340] > grown[110],
          "grosser Einflussbereich laesst entferntere Icons mitwachsen "
          "(%.0f -> %.0f px)" % (grown[110], grown[340]))
    dock.config.radius = 190
    dock._recompute_window_geometry()

    print("\n== Reaktion aus allen Richtungen gleich ==")
    dock._layout(-1.0e9)
    dock._cursor_y = dock._icon_center_y()
    # Ein echtes Icon in der Mitte - kein Trenner, der nie mitwaechst.
    normal = [i for i, e in enumerate(cfg.entries) if e["type"] != SEPARATOR]
    ziel = normal[len(normal) // 2]
    cx = dock._bounds[ziel].center().x()
    cy = dock._icon_center_y()
    basis = cfg.effective_size

    # 1) Das Vergroesserungsgesetz selbst: gleicher Abstand in alle
    #    Richtungen muss gleiche Groesse ergeben. Das Gate bleibt dabei
    #    aus, sonst misst man das Ausblenden am Panelrand mit.
    schritte = 13
    strecke = 150.0
    gesetz = {}
    for richtung, punkte in (
        ("links", [(cx - strecke + i * strecke / (schritte - 1), cy)
                   for i in range(schritte)]),
        ("rechts", [(cx + strecke - i * strecke / (schritte - 1), cy)
                    for i in range(schritte)]),
        ("unten", [(cx, cy + strecke - i * strecke / (schritte - 1))
                   for i in range(schritte)]),
        ("oben", [(cx, cy - strecke + i * strecke / (schritte - 1))
                  for i in range(schritte)]),
    ):
        werte = []
        for x, y in punkte:
            lokal = x - dock._rest_offset
            _c, used, _s = dock._centers_and_sizes(lokal, 1.0, y)
            werte.append(used[ziel] / basis)
        gesetz[richtung] = werte

    abweichung = 0.0
    for i in range(schritte):
        werte = [gesetz[k][i] for k in gesetz]
        abweichung = max(abweichung, max(werte) - min(werte))
    check(abweichung < 0.001,
          "alle vier Richtungen ergeben dieselbe Groesse (max %.4f)"
          % abweichung)
    check(min(min(v) for v in gesetz.values()) < 1.25,
          "aus 150 px Entfernung noch klein: %.2f"
          % min(min(v) for v in gesetz.values()))
    check(max(max(v) for v in gesetz.values()) > 1.8,
          "am Ende voll vergroessert: %.2f"
          % max(max(v) for v in gesetz.values()))

    # 2) Der Aufbau muss auch im echten Layout stufenlos sein. Hier bleibt
    #    der Zeiger innerhalb des Panels, damit das Gate nicht stoert.
    innen = min(70.0, max(20.0, (dock._panel_rect.right()
                                  - dock._panel_rect.left()) / 4.0))

    def anfahrt(punkte):
        out = []
        for x, y in punkte:
            dock._cursor_x = x
            dock._cursor_y = y
            dock._layout(x)
            out.append(dock._bounds[ziel].width() / basis)
        return out

    n = schritte - 1
    verlauf = {
        "links": anfahrt([(cx - innen + i * innen / n, cy) for i in range(schritte)]),
        "rechts": anfahrt([(cx + innen - i * innen / n, cy) for i in range(schritte)]),
        "unten": anfahrt([(cx, cy + innen - i * innen / n) for i in range(schritte)]),
        "oben": anfahrt([(cx, cy - innen + i * innen / n) for i in range(schritte)]),
    }
    sprung = max(max(abs(verlauf[k][i + 1] - verlauf[k][i]) for i in range(n))
                 for k in verlauf)
    check(sprung < 0.25, "kein harter Sprung beim Anfahren (max %.3f)" % sprung)
    check(min(verlauf[k][0] for k in verlauf) < 1.75,
          "am Anfang noch nicht voll: %.2f"
          % min(verlauf[k][0] for k in verlauf))

    dock._cursor_y = -1.0e9
    dock._layout(-1.0e9)

    print("\n== Icon-Hoehen ==")
    dock._cursor_x = centers[1]
    dock._layout(dock._cursor_x)
    check(all(abs(r.height() - r.width()) < 0.01 for r in dock._bounds),
          "Icons sind quadratisch")
    check(dock._panel_rect.height() > 0, "Panel hat Hoehe")

    print("\n== Maske / Bedienung ==")
    dock._update_mask()
    mask = dock.mask()
    check(not mask.isEmpty(), "Gattermaske gesetzt")
    check(mask.boundingRect().width() <= w, "Maske passt ins Fenster")

    print("\n== Neuaufbau mit geaenderter Konfiguration ==")
    cfg.size = 68
    cfg.magnification = 2.3
    dock._rebuild()
    dock._layout(-1.0e9)
    check(dock._bounds and abs(dock._bounds[0].width() - 68) < 0.01,
          "Groessenaenderung uebernommen (%.0f px)" % dock._bounds[0].width())
    check(dock._panel_rect.width() <= dock.width(),
          "Fenster waechst mit (Panel %d <= Fenster %d)"
          % (dock._panel_rect.width(), dock.width()))

    print("\n== Rendern ==")
    dock._cursor_x = dock._bounds[1].center().x()
    dock._layout(dock._cursor_x)
    pm = QtGui.QPixmap(dock.size())
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    dock.render(pm)
    check(not pm.isNull(), "Widget laesst sich zeichnen")
    image = pm.toImage()
    painted = sum(1 for y in range(0, image.height(), 2)
                  for x in range(0, image.width(), 2)
                  if QtGui.QColor(image.pixel(x, y)).alpha() > 0)
    check(painted > 200, "%d Pixel wurden tatsaechlich gemalt" % painted)

    print("\n== Schliessen ==")
    dock.close()
    dock.deleteLater()

    print()
    if FAILURES:
        print("%d Test(s) fehlgeschlagen:" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("Alle Tests bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())