"""Anbindung an macOS (PyObjC / AppKit).

Alles hier ist optional: fehlt PyObjC, laeuft das Dock trotzdem - es fallen
nur die AppKit-Icon_loader, die Fenster-Ebene und die Laufzeit-Erkennung aus.
"""

import os
import subprocess
import sys

IS_MAC = sys.platform == "darwin"

LAUNCHABLE = (".app", ".bundle")
EXTRA_STARTERS = []

objc = None
AppKit = None
Quartz = None
FOUNDATION = None
_ok = False

if IS_MAC:
    try:
        import objc as _objc
        import AppKit as _AppKit
        import Quartz as _Quartz
        import Foundation as _Foundation

        objc = _objc
        AppKit = _AppKit
        Quartz = _Quartz
        FOUNDATION = _Foundation
        _ok = True
    except Exception:
        _ok = False


def available():
    """True, wenn die volle AppKit-Anbindung zur Verfuegung steht."""
    return _ok


def is_launchable(path):
    return bool(path) and path.lower().endswith(LAUNCHABLE)


def display_name(path):
    """Anzeigename ohne Endung - wie er im Dock steht."""
    name = os.path.basename(str(path).rstrip("/"))
    for ext in LAUNCHABLE:
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return name


def default_config_dir():
    return os.path.join(os.path.expanduser("~"),
                        "Library", "Application Support", "Dockwave")


def acquire_single_instance():
    """Nur eine Kopie gleichzeitig. Auf macOS nicht blockierend geprueft."""
    return True


# ----------------------------------------------------------------------
# Identitaet einer App
# ----------------------------------------------------------------------

def bundle_id(app_path):
    """Liest CFBundleIdentifier aus der Info.plist."""
    plist = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(plist, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    try:
        import plistlib

        return plistlib.loads(data).get("CFBundleIdentifier")
    except Exception:
        return None


def category(app_path):
    """Liest die App-Kategorie fuer die Gruppierung im Ordner."""
    import plistlib

    try:
        with open(os.path.join(app_path, "Contents", "Info.plist"), "rb") as fh:
            return plistlib.load(fh).get("NSApplicationCategoryType") or "Sonstiges"
    except Exception:
        return "Sonstiges"


def app_key(path):
    """Vergleichsschluessel: die Bundle-ID, sonst der Pfad."""
    return bundle_id(path) or os.path.normcase(os.path.abspath(str(path)))


def running_keys():
    """Alle Bundle-IDs gerade laufender Apps."""
    if not _ok:
        return frozenset()
    try:
        out = set()
        for app in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            bid = app.bundleIdentifier()
            if bid:
                out.add(str(bid))
        return frozenset(out)
    except Exception:
        return frozenset()


def is_running(path, keys=None):
    keys = running_keys() if keys is None else keys
    return bool(keys) and app_key(path) in keys


# ----------------------------------------------------------------------
# Starten
# ----------------------------------------------------------------------

def launch(app_path):
    """Startet eine App ueber den Finder-Mechanismus."""
    try:
        subprocess.Popen(["open", "-a", str(app_path)],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def reveal(path):
    """Im Finder markiert anzeigen."""
    try:
        subprocess.Popen(["open", "-R", str(path)],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------
# Fenster-Ebene
# ----------------------------------------------------------------------

def apply_window_level(widget, layer):
    """Setzt die Fenster-Ebene, damit das Dock an der gewuenschten Stelle liegt.

    "desktop"  -> ueber Hintergrundbild, hinter allen normalen Fenstern
    "floating" -> ueber normalen Fenstern (wie der echte Dock)
    "top"      -> knapp unter der Menue-Leiste

    Ohne PyObjC bleibt nur die Qt-Variante, die dann auf "floating" faellt.
    """
    if not _ok or widget is None:
        return

    keys = {
        # Knapp ueber den Desktop-Icons: sichtbar auf dem Schreibtisch,
        # aber hinter jedem normalen App-Fenster.
        "desktop": getattr(Quartz, "kCGDesktopIconWindowLevelKey", None),
        "floating": getattr(Quartz, "kCGDockWindowLevelKey", None),
        "top": getattr(Quartz, "kCGMainMenuWindowLevelKey", None),
    }
    key = keys.get(layer) or keys["floating"]

    try:
        win = widget.windowHandle()
        if win is None:
            return
        view = objc.objc_object(c_void_p=int(win.winId()))
        ns_window = view.window()
        if ns_window is None:
            return

        level = Quartz.CGWindowLevelForKey(key)
        if layer == "top":
            level -= 1          # knapp unter der Menue-Leiste bleiben
        ns_window.setLevel_(level)
    except Exception:
        pass


def sample_apps():
    """Ein paar sinnvolle Starter, die auf jedem Mac vorhanden sind."""
    candidates = [
        "/System/Applications/Finder.app",
        "/System/Applications/Safari.app",
        "/System/Applications/Mail.app",
        "/System/Applications/Messages.app",
        "/System/Applications/Maps.app",
        "/System/Applications/Notes.app",
        "/System/Applications/Music.app",
        "/System/Applications/Photos.app",
        "/System/Applications/Terminal.app",
    ]
    return [p for p in candidates if os.path.exists(p)]


# ----------------------------------------------------------------------
# Icons
# ----------------------------------------------------------------------

def icon_pixmap(app_path, pixel_size):
    """Laedt das echte macOS-App-Icon als QPixmap."""
    if not _ok:
        return None
    try:
        from .qt import QtCore, QtGui

        ns_image = AppKit.NSWorkspace.sharedWorkspace().iconForFile_(app_path)
        if ns_image is None:
            return None

        data = None
        for getter in ("PNGRepresentation", "TIFFRepresentation"):
            try:
                data = getattr(ns_image, getter)()
                if data:
                    break
            except Exception:
                data = None
        if not data:
            return None

        loader = QtGui.QPixmap()
        if not loader.loadFromData(bytes(data)):
            return None
        if pixel_size > 0:
            loader = loader.scaled(
                pixel_size, pixel_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation)
        return loader
    except Exception:
        return None


# ----------------------------------------------------------------------
# Dateiauswahl
# ----------------------------------------------------------------------

def open_app_panel(parent=None):
    """Oeffnet den echten NSOpenPanel fuer die Auswahl von .app Bundles."""
    if _ok:
        try:
            panel = AppKit.NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(True)
            panel.setCanChooseDirectories_(False)
            panel.setAllowsMultipleSelection_(True)
            # Ohne das werden .app Bundles "betreten" statt ausgewaehlt.
            panel.setTreatsFilePackagesAsDirectories_(False)
            try:
                panel.setAllowedContentTypes_(["public.application"])
            except Exception:
                try:
                    panel.setAllowedFileTypes_(["app"])
                except Exception:
                    pass
            panel.setMessage_("Apps zum Dock hinzufuegen")
            if panel.runModal() != AppKit.NSModalResponseOK:
                return None
            return [str(url.path()) for url in panel.URLs() if url.path()]
        except Exception:
            pass

    from .qt import QtWidgets

    paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
        parent, "Apps zum Dock hinzufuegen", "/Applications", "Programme (*.app)")
    return list(paths) if paths else None