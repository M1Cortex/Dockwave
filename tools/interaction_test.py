"""Bedientest: Mausereignisse, Klicks, Ziehen, Drop, Speichern.

Aufruf:  python3 tools/interaction_test.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Eigene Konfiguration benutzen, damit die echte nicht angefasst wird.
import dockwave.config as config_mod                       # noqa: E402
from _testconfig import schutz                              # noqa: E402
schutz()

from dockwave.config import APP, STACK, Config             # noqa: E402
from dockwave.dock_window import DockWindow                 # noqa: E402
from dockwave.qt import QtCore, QtGui, QtWidgets            # noqa: E402

FAILURES = []
LAUNCHED = []


def check(condition, message):
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        FAILURES.append(message)


def main():
    # Wichtig: Die QApplication muss in einer Variablen stehen bleiben.
    # Ohne Referenz gibt Python sie sofort wieder frei und alles Weitere
    # stuerzt ab.
    app = QtWidgets.QApplication(sys.argv[:1])
    _ = app  # nur zur Haeltung der Referenz noetig

    # Programmstart abfaengig machen, damit keine App wirklich startet.
    import dockwave.dock_window as dw
    dw.platform.launch = lambda path: LAUNCHED.append(path)

    entries = [
        {"type": APP, "path": "/Applications/Alpha.app"},
        {"type": APP, "path": "/Applications/Beta.app"},
        {"type": APP, "path": "/Applications/Gamma.app"},
        {"type": STACK},
    ]
    cfg = Config({"entries": entries})
    dock = DockWindow(cfg)
    dock.resize(dock.width(), dock.height())
    dock.show()

    def move(x, y=None):
        dock._cursor_x = x
        dock._layout(x)
        if y is None:
            y = dock._bounds[0].center().y()
        return QtGui.QGuiApplication.sendEvent(
            dock, QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseMove,
                QtCore.QPointF(x, y),
                QtCore.QPointF(x, y),
                QtCore.Qt.MouseButton.NoButton,
                QtCore.Qt.MouseButton.NoButton,
                QtCore.Qt.KeyboardModifier.NoModifier))

    def press(x, y):
        return QtGui.QGuiApplication.sendEvent(
            dock, QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QPointF(x, y), QtCore.QPointF(x, y),
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.KeyboardModifier.NoModifier))

    def release(x, y):
        return QtGui.QGuiApplication.sendEvent(
            dock, QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QPointF(x, y), QtCore.QPointF(x, y),
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.MouseButton.NoButton,
                QtCore.Qt.KeyboardModifier.NoModifier))

    dock._layout(-1.0e9)
    centers = [r.center().x() for r in dock._bounds]
    mid_y = dock._bounds[0].center().y()

    print("\n== Klick startet die App ==")
    press(centers[0], mid_y)
    release(centers[0], mid_y)
    check(LAUNCHED == ["/Applications/Alpha.app"],
          "Alpha wurde gestartet: %s" % LAUNCHED)

    print("\n== Ziehen im Dock sortiert um ==")
    before = [e.get("path", e["type"]) for e in dock.config.entries]
    press(centers[0], mid_y)
    move(centers[1], mid_y)
    dock._layout(dock._cursor_x)
    check(dock._dragging, "Zustand 'ziehen' ist aktiv")
    check(dock._drag_target == 1, "Einfuegeposition ist 1 (ist %d)" % dock._drag_target)
    move(centers[2], mid_y)
    dock._layout(dock._cursor_x)
    release(centers[2], mid_y)
    after = [e.get("path", e["type"]) for e in dock.config.entries]
    check(before != after, "Reihenfolge hat sich geaendert")
    check(after.index("/Applications/Beta.app") < after.index("/Applications/Alpha.app"),
          "Beta steht jetzt vor Alpha: %s" % after)
    check(not dock._dragging, "Ziehzustand ist beendet")

    print("\n== Ziehen ans Ende ==")
    dock._layout(-1.0e9)
    centers = [r.center().x() for r in dock._bounds]
    dragged = dock.config.entries[0].get("path")
    press(centers[0], mid_y)
    move(dock.width() + 10, mid_y)
    release(dock.width() + 10, mid_y)
    paths = [e.get("path") for e in dock.config.entries if e["type"] == APP]
    check(paths[-1] == dragged,
          "%s wurde ans Ende gezogen: %s" % (dragged, paths))

    print("\n== Doppelte Eintraege werden abgelehnt ==")
    n = len(dock.config.entries)
    dock.config.add_app("/Applications/Alpha.app")
    dock.config.add_app("/Applications/Delta.app")
    check(len(dock.config.entries) == n + 1,
          "nur die neue App kam dazu (%d -> %d)" % (n, len(dock.config.entries)))

    print("\n== Drop aus dem Datei-Explorer ==")
    from dockwave import platform

    ext = platform.app_extensions()[0]
    base = r"C:\Programme\Test" if platform.IS_WIN else "/Applications"
    first = os.path.join(base, "Epsilon" + ext)
    second = os.path.join(base, "Zeta" + ext)
    urls = [QtCore.QUrl.fromLocalFile(first),
            QtCore.QUrl.fromLocalFile(second)]
    mime = QtCore.QMimeData()
    mime.setUrls(urls)

    n = len(dock.config.entries)
    dock.dropEvent(QtGui.QDropEvent(
        QtCore.QPointF(dock.width() / 2, mid_y),
        QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier))
    new = [e.get("path") for e in dock.config.entries]
    wanted = {os.path.normcase(first), os.path.normcase(second)}
    have = {os.path.normcase(p) for p in new if p}
    check(wanted <= have,
          "beide Programme aus dem Drop uebernommen (%s)" % (wanted - have or "vollstaendig"))
    check(len(dock.config.entries) == n + 2, "genau zwei Eintraege ergaenzt")

    print("\n== Unbrauchbares wird abgelehnt ==")
    mime2 = QtCore.QMimeData()
    not_a_program = os.path.join(base, "Notiz.txt")
    mime2.setUrls([QtCore.QUrl.fromLocalFile(not_a_program)])
    n = len(dock.config.entries)
    dock.dropEvent(QtGui.QDropEvent(
        QtCore.QPointF(dock.width() / 2, mid_y),
        QtCore.Qt.DropAction.CopyAction, mime2,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier))
    check(len(dock.config.entries) == n, "Textdatei ignoriert")

    print("\n== Ordner-Menue ==")
    from dockwave.stack import build_stack_menu

    menu = build_stack_menu(dock, dock.config)
    check(menu is not None, "Ordner-Menue laesst sich bauen")
    if menu is not None:
        top = [a for a in menu.actions() if a.menu() is not None]
        check(len(top) > 0, "Kategorien vorhanden: %s"
              % ", ".join(a.text() for a in top[:4]))
        leaves = [a for sub in top for a in sub.menu().actions()]
        check(len(leaves) > 0, "%d Programme aufgefuehrt" % len(leaves))
        check(all(a.icon().isNull() is False for a in leaves),
              "jeder Eintrag hat ein Icon")
        check(any(a.text() for a in leaves),
              "erster Eintrag heisst '%s'" % (leaves[0].text() if leaves else ""))

    print("\n== Icon-Hilfswege ==")
    from dockwave import icons
    from dockwave.qt import QtGui as _QtGui

    image = _QtGui.QImage(40, 30, _QtGui.QImage.Format.Format_ARGB32)
    image.fill(_QtGui.QColor(10, 200, 90))
    pm = icons._to_pixmap(image, 64)
    check(not pm.isNull() and pm.width() == 64,
          "_to_pixmap skaliert auf %dx%d" % (pm.width(), pm.height()))
    placeholder = icons.placeholder_pixmap(48)
    check(not placeholder.isNull(), "Platzhalter wird gezeichnet")
    stack_icon = icons.stack_pixmap(64)
    check(not stack_icon.isNull(), "Ordner-Symbol wird gezeichnet")

    print("\n== Kontextmenue der Leiste ==")
    # Ruft alle Zweige des Rechtsklick-Menues auf, ohne es anzuzeigen.
    built = []
    original_exec = QtWidgets.QMenu.exec

    def fake_exec(self, *args, **kwargs):
        built.append(self)
        return None

    QtWidgets.QMenu.exec = fake_exec
    try:
        dock._context_menu(0, QtCore.QPoint(10, 10))
        dock._context_menu(-1, QtCore.QPoint(10, 10))
    finally:
        QtWidgets.QMenu.exec = original_exec
    check(len(built) == 2,
          "Kontextmenue laesst sich mit und ohne Ziel aufbauen")
    if built:
        labels = [a.text() for a in built[0].actions()]
        check(any("Öffnen" in t or "Explorer" in t or "Finder" in t
                  for t in labels),
              "Programmeintrag hat Aktionen: %s" % ", ".join(labels[:4]))

    print("\n== Persistenz ==")
    check(dock.config.save(), "Konfiguration liess sich speichern")
    check(os.path.exists(config_mod.CONFIG_PATH), "Datei liegt unter %s"
          % config_mod.CONFIG_PATH)
    again = Config.load()
    check([e.get("path") for e in again.entries] == [e.get("path") for e in dock.config.entries],
          "Neu geladen liefert dieselbe Reihenfolge")

    print("\n== Fenster liegt auf dem Bildschirm ==")
    screen = QtGui.QGuiApplication.primaryScreen().geometry()
    g = dock.geometry()
    check(screen.contains(g), "Dock-Fenster (%d,%d %dx%d) liegt im Bildschirm %s"
          % (g.x(), g.y(), g.width(), g.height(), screen))

    print("\n== Ereignisschleife laeuft ==")
    ticks = []
    timer = QtCore.QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    QtCore.QTimer.singleShot(400, app_quit)
    QtWidgets.QApplication.instance().exec()
    timer.stop()
    check(len(ticks) > 10, "Ereignisschleife lief (%d Takte in 400 ms)" % len(ticks))

    dock.close()
    print()
    if FAILURES:
        print("%d Test(s) fehlgeschlagen:" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("Alle Bedientests bestanden.")
    return 0


def app_quit():
    QtWidgets.QApplication.instance().quit()


if __name__ == "__main__":
    sys.exit(main())