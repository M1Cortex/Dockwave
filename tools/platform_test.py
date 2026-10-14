"""Prueft die Windows-Anbindung.

Hier laufen Dinge, die man sonst nur schwer sieht: Aufloesen von
Verknuepfungen, Shell-Icons, Erkennen laufender Programme, Starten.

Aufruf:  python tools/platform_test.py
"""

import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dockwave import platform                      # noqa: E402
from dockwave.qt import QtGui, QtWidgets            # noqa: E402

FAILURES = []
NOTEPAD = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "notepad.exe")


def check(condition, message):
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        FAILURES.append(message)


def main():
    # Wichtig: Die QApplication muss in einer Variablen stehen bleiben.
    # Ohne Referenz gibt Python sie sofort wieder frei und alles Weitere
    # stuerzt ab.
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _ = app

    print("\n== Plattform ==")
    print("  erkannt: %s" % platform.name())
    check(platform.IS_WIN, "Windows-Backend geladen")
    check(platform.available(), "Windows-Schnittstellen (user32) verfuegbar")

    print("\n== Konfigurationspfad ==")
    cfg_dir = platform.default_config_dir()
    check(cfg_dir and "Dockwave" in cfg_dir, "Config-Ordner: %s" % cfg_dir)

    print("\n== Programm-Endungen ==")
    check(platform.is_launchable("C:/x/Firefox.exe"), ".exe wird erkannt")
    check(platform.is_launchable("C:/x/Chrome.lnk"), ".lnk wird erkannt")
    check(not platform.is_launchable("C:/x/Ordner"), "Ordner ist kein Programm")

    print("\n== Anzeigename ==")
    check(platform.display_name("C:/x/Firefox.exe") == "Firefox",
          "Firefox.exe -> '%s'" % platform.display_name("C:/x/Firefox.exe"))
    check(platform.display_name("C:/x/Steam.lnk") == "Steam",
          "Steam.lnk -> '%s'" % platform.display_name("C:/x/Steam.lnk"))

    print("\n== Shell-Icon ==")
    from dockwave import icons
    pm = icons.app_pixmap(NOTEPAD, 1.0)
    check(pm is not None and not pm.isNull(), "Icon fuer notepad geladen")
    if pm is not None and not pm.isNull():
        image = pm.toImage()
        colored = 0
        for y in range(0, image.height(), 8):
            for x in range(0, image.width(), 8):
                c = QtGui.QColor(image.pixel(x, y))
                if c.alpha() > 0 and (c.red() + c.green() + c.blue()) > 60:
                    colored += 1
        check(colored > 10, "Icon hat echte Bildpunkte (%d Stichproben)" % colored)

    print("\n== Verknuepfung aufloesen ==")
    workdir = tempfile.mkdtemp(prefix="dockwave-lnk-")
    lnk = os.path.join(workdir, "Testverknuepfung.lnk")
    made = _make_shortcut(lnk, NOTEPAD)
    if made:
        target = platform.resolve_shortcut(lnk)
        check(target and target.lower().endswith("notepad.exe"),
              "Verknuepfung zeigt auf: %s" % target)
        key = platform.app_key(lnk)
        check(key.lower().endswith("notepad.exe"),
              "app_key nutzt das Ziel: %s" % key)
    else:
        print("  --  Verknuepfung konnte nicht angelegt werden, uebersprungen")

    print("\n== Icon-Groesse einheitlich ==")
    from dockwave import icons
    from dockwave.qt import QtCore as _QtCore
    from dockwave.qt import QtGui as _QtGui

    def fill(pixmap):
        box = icons._content_box(pixmap.toImage())
        if not box:
            return 0.0
        _x, _y, w, h = box
        return 100.0 * min(w, h) / pixmap.width()

    def synthetic(size, margin):
        """Quadrat mit farbigem Inhalt und transparentem Rand."""
        img = _QtGui.QImage(size, size, _QtGui.QImage.Format.Format_ARGB32)
        img.fill(_QtGui.QColor(0, 0, 0, 0))
        p = _QtGui.QPainter(img)
        p.fillRect(_QtCore.QRect(margin, margin,
                                size - 2 * margin, size - 2 * margin),
                   _QtGui.QColor(20, 160, 220))
        p.end()
        return _QtGui.QPixmap.fromImage(img)

    # 1) _content_box muss Breite UND Hoehe finden. Genau da steckte ein
    #    Fehler: max_y wurde nie gesetzt, wodurch alle Icons leer wurden.
    box = icons._content_box(synthetic(100, 10).toImage())
    check(box is not None and box[2] > 0 and box[3] > 0,
          "_content_box liefert Breite und Hoehe: %s" % (box,))
    check(box is not None and 75 <= box[2] <= 85 and 75 <= box[3] <= 85,
          "_content_box findet den 80x80-Inhalt: %s" % (box,))

    leer = _QtGui.QPixmap(64, 64)
    leer.fill(_QtGui.QColor(0, 0, 0, 0))
    check(icons._content_box(leer.toImage()) is None,
          "vollig transparentes Bild liefert None")

    # 2) Der eigentliche Fix: sehr unterschiedliche Randbreiten muessen nach
    #    dem Zuschneiden gleich wirken.
    roh = [fill(synthetic(256, m)) for m in (4, 30, 90)]
    gleich = [fill(icons.normalize(synthetic(256, m), 256)) for m in (4, 30, 90)]
    check(max(roh) - min(roh) > 40,
          "Ausgangsbilder unterscheiden sich stark: %s"
          % ["%.0f%%" % r for r in roh])
    check(max(gleich) - min(gleich) <= 3,
          "danach sind alle gleich gross: %s" % ["%.0f%%" % g for g in gleich])

    # 3) Und dasselbe mit echten Systemprogrammen.
    echt = [s for s in (NOTEPAD, r"C:\Windows\explorer.exe",
                        r"C:\Windows\System32\cmd.exe") if os.path.exists(s)]
    if echt:
        werte = [fill(icons.app_pixmap(s, 1.0)) for s in echt]
        check(max(werte) - min(werte) <= 12,
              "echte Systemprogramme liegen nah beieinander: %s"
              % ["%.0f%%" % w for w in werte])
        check(min(werte) >= 75,
              "kein Systemprogramm auffaellig klein (min %.0f%%)" % min(werte))

    check(fill(icons.stack_pixmap(256)) >= 75,
          "Ordner-Symbol fuellt das Raster (%.0f%%)"
          % fill(icons.stack_pixmap(256)))

    print("\n== Kategorie ==")
    cat = platform.category(r"C:\Program Files\Steam\steam.exe")
    check(bool(cat), "Kategorie erkannt: %s" % cat)

    print("\n== Laufende Programme ==")
    explorer = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe")
    check(platform.is_running(explorer),
          "explorer.exe laeuft immer und wird erkannt")
    check(not platform.is_running(os.path.join(
        os.environ.get("WINDIR", r"C:\Windows"), "gibtsnicht12345.exe")),
        "nicht vorhandenes Programm gilt als nicht laufend")

    print("\n== Starten und wiedererkennen ==")
    if os.path.exists(NOTEPAD):
        before = len(platform.running_keys())
        check(platform.launch(NOTEPAD), "notepad wurde gestartet")
        time.sleep(2.0)
        keys = platform.running_keys()
        # notepad.exe ist unter Windows 11 ein Starter, der sich in den
        # echten Notepad unter WindowsApps weiterleitet. Genau dafuer gibt
        # es den Dateinamen-Vergleich als zweite Stufe.
        check(platform.is_running(NOTEPAD, keys),
              "notepad wird nach dem Start erkannt (%d -> %d Programme)"
              % (before, len(keys)))
        _kill_notepad()
    else:
        print("  --  notepad.exe nicht gefunden, uebersprungen")

    print("\n== Fenster-Ebene ==")
    from dockwave.config import Config
    from dockwave.dock_window import DockWindow

    cfg = Config({"entries": [{"type": "stack"}]})
    dock = DockWindow(cfg)
    dock.show()
    ok = True
    for layer in ("desktop", "floating", "top"):
        try:
            dock._apply_layer()
            ok = True
        except Exception as exc:  # pragma: no cover
            print("     %s -> %s" % (layer, exc))
            ok = False
    check(ok, "alle drei Ebenen lassen sich setzen")
    check(bool(dock.windowHandle() and dock.windowHandle().winId()),
          "Fenster hat ein gültiges Handle")
    dock.close()

    print()
    if FAILURES:
        print("%d Test(s) fehlgeschlagen:" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("Alle Plattformtests bestanden.")
    return 0


def _make_shortcut(path, target):
    """Legt eine echte .lnk-Datei an (PowerShell, einmalig)."""
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath = '%s'; $s.Save()" % (path, target)
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, timeout=20)
        return os.path.exists(path) and res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _kill_notepad():
    subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    sys.exit(main())