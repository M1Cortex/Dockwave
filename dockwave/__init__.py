"""Dockwave - eine eigene Dock-Leiste fuer Windows und macOS."""

__version__ = "1.0.0"


def run(argv=None):
    """Programm starten."""
    from .app import run as _run

    return _run(argv)