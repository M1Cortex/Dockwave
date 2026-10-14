"""Plattformabstraktion: eine Schnittstelle, zwei Backends.

macOS : platform_mac  (AppKit, echte App-Icons, .app-Bundles)
Windows: platform_win (Shell, .exe/.lnk, Z-Reihenfolge)

Alles andere im Projekt spricht nur mit diesem Modul. Fehlt auf einer
Plattform eine Faehigkeit, faellt die Funktion auf einen einfacheren Weg
zurueck statt zu scheitern.
"""

import sys

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

if IS_MAC:
    from . import platform_mac as _impl
elif IS_WIN:
    from . import platform_win as _impl
else:  # pragma: no cover - Linux und andere
    from . import platform_null as _impl

LAUNCHABLE = _impl.LAUNCHABLE if hasattr(_impl, "LAUNCHABLE") else (
    (".app",) if IS_MAC else (".exe", ".lnk"))


def name():
    return "macOS" if IS_MAC else ("Windows" if IS_WIN else sys.platform)


def available():
    """Gibt es eine vollstaendige Anbindung?"""
    return _impl.available()


def is_launchable(path):
    return _impl.is_launchable(path)


def display_name(path):
    return _impl.display_name(path)


def resolve(path):
    """Verknuepfungen aufloesen, damit das richtige Icon erscheint."""
    fn = getattr(_impl, "resolve_shortcut", None)
    return fn(path) if fn else path


def resolve_shortcut(path):
    """Wie resolve(), aber mit dem Namen des Backends."""
    return resolve(path)


def launch(path):
    return _impl.launch(path)


def reveal(path):
    return _impl.reveal(path)


def running_keys():
    """Menge der Kennungen gerade laufender Programme."""
    return _impl.running_keys()


def is_running(path, keys=None):
    """Laeuft dieses Programm gerade?"""
    return _impl.is_running(path, keys)


def app_key(path):
    """Vergleichsschluessel einer Programmdatei."""
    return _impl.app_key(path)


def category(path):
    return _impl.category(path)


def apply_window_level(widget, layer):
    return _impl.apply_window_level(widget, layer)


def glass_available():
    """Kann das System den Hintergrund hinter dem Fenster weichzeichnen?"""
    fn = getattr(_impl, "glass_available", None)
    return bool(fn()) if fn else False


def apply_glass(widget, enabled, tint=0x30FFFFFF):
    """Hintergrund hinter dem Fenster weichzeichnen (Acrylic/Blur)."""
    fn = getattr(_impl, "apply_glass", None)
    return bool(fn(widget, enabled, tint)) if fn else False


def open_app_panel(parent=None):
    return _impl.open_app_panel(parent)


def icon_pixmap(path, pixel_size):
    """Plattformspezifisches App-Icon, oder None."""
    fn = getattr(_impl, "icon_pixmap", None)
    return fn(path, pixel_size) if fn else None


def default_config_dir():
    return _impl.default_config_dir()


def acquire_single_instance():
    """False, wenn bereits eine Kopie laeuft."""
    fn = getattr(_impl, "acquire_single_instance", None)
    return fn() if fn else True


def app_extensions():
    """Endungen, die das Dock als Programm akzeptiert (fuer Drag & Drop)."""
    return _impl.LAUNCHABLE


def extra_starters():
    """Vorschlaege fuer den allerersten Start."""
    return getattr(_impl, "EXTRA_STARTERS", [])


def sample_apps():
    """Ein paar sinnvolle Starter, die auf diesem System existieren."""
    fn = getattr(_impl, "sample_apps", None)
    return list(fn()) if fn else []