"""Anwendungseinstieg: Argumente auswerten, Fenster aufbauen, Ereignisschleife."""

import argparse
import os
import sys

from . import __version__


def build_parser():
    win = sys.platform == "win32"
    p = argparse.ArgumentParser(
        prog="dockwave",
        description="Eine eigene Dock-Leiste mit weicher Icon-Vergroesserung.",
    )
    p.add_argument("--version", action="version",
                   version="Dockwave %s" % __version__)
    p.add_argument("--position", choices=("bottom", "top", "left", "right"),
                   help="Wo die Leiste sitzt (Standard: oben).")
    p.add_argument("--layer", choices=("desktop", "floating", "top"),
                   help="desktop = hinter Fenstern, floating = immer sichtbar, "
                        "top = ganz oben (Standard: desktop).")
    p.add_argument("--size", type=int, help="Icon-Groesse in Pixeln.")
    p.add_argument("--magnification", type=float,
                   help="Vergroesserungsfaktor, 1.0 schaltet sie ab.")
    p.add_argument("--radius", type=int,
                   help="Einflussradius der Vergroesserung in Pixeln.")
    p.add_argument("--fps", type=int, help="Bildrate (Standard 60, erlaubt bis 144).")
    p.add_argument("--minimal", action="store_true", help="Kompakter Modus.")
    p.add_argument("--no-stack", action="store_true",
                   help="Den Ordner-Eintrag nicht anzeigen.")
    p.add_argument("--reset", action="store_true",
                   help="Gespeicherte Konfiguration loeschen und neu beginnen.")
    p.add_argument("--dump-config", action="store_true",
                   help="Aktuelle Konfiguration anzeigen und beenden.")
    if win:
        p.add_argument("--topmost", action="store_true",
                       help="Leiste immer im Vordergrund zeigen.")
    return p


def _apply_args(config, args, save=True):
    changed = False
    for name in ("position", "layer", "size", "magnification", "radius", "fps"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(config, name, value)
            changed = True
    if getattr(args, "minimal", False):
        config.minimal = True
        changed = True
    if getattr(args, "topmost", False):
        config.layer = "floating"
        changed = True
    if args.no_stack:
        config.entries = [e for e in config.entries if e["type"] != "stack"]
        changed = True
    if changed and save:
        config.clamped()
        config.save()
    return config


def run(argv=None):
    args = build_parser().parse_args(argv)

    # Qt wird erst danach geladen, damit --help auch ohne PyQt6 funktioniert.
    from . import platform
    from .config import CONFIG_PATH, Config
    from .dock_window import DockWindow
    from .qt import QtWidgets

    if args.reset:
        try:
            os.remove(CONFIG_PATH)
        except OSError:
            pass

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("Dockwave")
    app.setApplicationDisplayName("Dockwave")
    app.setQuitOnLastWindowClosed(False)

    # Auf macOS kein Dock-Symbol und kein Menueleisten-Umschalten.
    if platform.IS_MAC and platform.available():
        try:
            backend = platform._impl
            backend.AppKit.NSApplication.sharedApplication().setActivationPolicy_(
                backend.AppKit.NSApplicationActivationPolicyAccessory)
        except Exception:
            pass

    config = _apply_args(Config.load(), args, save=not args.dump_config)

    if args.dump_config:
        print("Plattform: %s" % platform.name())
        print("Konfiguration: %s" % CONFIG_PATH)
        for entry in config.entries:
            print(entry)
        for key in ("size", "magnification", "radius", "spacing", "padding",
                    "position", "layer", "fps", "minimal", "show_running"):
            print("%-14s %s" % (key, getattr(config, key)))
        return 0

    # Zwei Docks wuerden sich ueberlagern - der zweite Start beendet sich.
    if not platform.acquire_single_instance():
        print("Dockwave laeuft bereits. Beenden ueber Rechtsklick "
              "auf die Leiste > Dock schliessen.")
        return 0

    # Den Ordner-Eintrag hinten anhaengen, falls er fehlt.
    if not any(e["type"] == "stack" for e in config.entries):
        config.entries.append({"type": "stack"})
        config.save()

    window = DockWindow(config)
    window.start()

    try:
        return app.exec()
    finally:
        window.stop()
        config.save()


if __name__ == "__main__":
    sys.exit(run())