"""Kompatibilitaetsschicht: PyQt6 bevorzugt, PySide6 als Alternative.

Alle Module importieren Qt-Zugriff ausschliesslich ueber diese Datei, damit der
Wechsel zwischen den beiden Bindings an einer Stelle passiert.
"""

QT_API = None

try:  # pragma: no cover - abhaengig von der Umgebung
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtCore import pyqtSlot as Slot

    QT_API = "PyQt6"
except ImportError:  # pragma: no cover
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        from PySide6.QtCore import Signal, Slot

        QT_API = "PySide6"
    except ImportError:
        raise ImportError(
            "Weder PyQt6 noch PySide6 gefunden.\n"
            "Installiere eines davon:  pip install PyQt6\n"
            "bzw.                     pip install PySide6"
        )

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Signal",
    "Slot",
    "QT_API",
]