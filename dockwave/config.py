"""Konfiguration und Persistenz des Docks."""

import json
import os
import shutil

from . import platform

APP_DIR = platform.default_config_dir()
CONFIG_PATH = os.path.join(APP_DIR, "dock.json")

# Eintragsarten
APP = "app"            # eine .app / .bundle
SEPARATOR = "separator"
STACK = "stack"        # der "Ordner", der alle Apps gruppiert zeigt

LAYERS = ("desktop", "floating", "top")
POSITIONS = ("bottom", "top", "left", "right")


class Config:
    """Alle Einstellungen des Docks inklusive der Icon-Reihenfolge."""

    def __init__(self, data=None):
        data = data or {}

        # --- Icon-Reihe ---------------------------------------------------
        self.entries = self._clean_entries(data.get("entries", []))

        # --- Erscheinungsbild --------------------------------------------
        self.size = int(data.get("size", 46))            # Basisgroesse in px
        self.magnification = float(data.get("magnification", 1.85))
        self.radius = int(data.get("radius", 190))       # Einflussradius in px
        self.spacing = int(data.get("spacing", 8))       # Abstand zwischen Icons
        self.padding = int(data.get("padding", 10))      # Innenabstand der Leiste

        # --- Verhalten ----------------------------------------------------
        self.position = data.get("position", "bottom")
        # Unter Windows liegt "hinter allen Fenstern" praktisch hinter
        # allem - dort ist im Vordergrund die sinnvolle Voreinstellung.
        self.layer = data.get(
            "layer", "floating" if platform.IS_WIN else "desktop")
        self.fps = int(data.get("fps", 60))
        self.minimal = bool(data.get("minimal", False))
        self.show_running = bool(data.get("show_running", True))

        # --- Standard-Apps beim ersten Start ------------------------------
        if not self.entries:
            self.entries = self._default_entries()

    # ------------------------------------------------------------------
    @staticmethod
    def _clean_entries(raw):
        """Unbekanntes entfernen, Reihenfolge erhalten."""
        out = []
        if not isinstance(raw, list):
            return out
        for item in raw:
            if isinstance(item, str):
                out.append({"type": APP, "path": item})
            elif isinstance(item, dict):
                kind = item.get("type", APP)
                if kind == APP and item.get("path"):
                    out.append({"type": APP, "path": str(item["path"])})
                elif kind in (SEPARATOR, STACK):
                    out.append({"type": kind})
        return out

    @staticmethod
    def _default_entries():
        """Ein paar sinnvolle Starter, die auf diesem System existieren."""
        return [{"type": APP, "path": path} for path in platform.sample_apps()]

    # ------------------------------------------------------------------
    def save(self):
        """Atomar auf die Platte schreiben, mit Sicherung des Vorgaengers."""
        try:
            os.makedirs(APP_DIR, exist_ok=True)

            # Vor dem Ueberschreiben die bisherige Fassung sichern. Ein
            # versehentliches Leerschreiben - etwa durch ein Programm, das
            # im Test die echte Datei benutzt - waere so rueckgaengig zu machen.
            if os.path.exists(CONFIG_PATH):
                try:
                    shutil.copy2(CONFIG_PATH, CONFIG_PATH + ".bak")
                except OSError:
                    pass

            data = {
                "entries": self.entries,
                "size": self.size,
                "magnification": self.magnification,
                "radius": self.radius,
                "spacing": self.spacing,
                "padding": self.padding,
                "position": self.position,
                "layer": self.layer,
                "fps": self.fps,
                "minimal": self.minimal,
                "show_running": self.show_running,
            }
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, CONFIG_PATH)
            return True
        except OSError:
            return False

    @classmethod
    def load(cls):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return cls(json.load(fh))
        except (OSError, ValueError):
            return cls()

    # ------------------------------------------------------------------
    def app_paths(self):
        return [e["path"] for e in self.entries if e["type"] == APP]

    def index_of_app(self, path):
        for i, e in enumerate(self.entries):
            if e["type"] == APP and e["path"] == path:
                return i
        return -1

    def add_app(self, path):
        """Fuegt eine App hinzu, falls sie nicht schon in der Leiste steht."""
        if not path:
            return -1
        if self.index_of_app(path) >= 0:
            return -1
        self.entries.append({"type": APP, "path": path})
        return len(self.entries) - 1

    def remove_index(self, index):
        if 0 <= index < len(self.entries):
            del self.entries[index]
            return True
        return False

    def move(self, frm, to):
        """Verschiebt einen Eintrag (fuer Drag & Drop Sortierung)."""
        if frm == to or not (0 <= frm < len(self.entries)):
            return False
        item = self.entries.pop(frm)
        self.entries.insert(max(0, min(to, len(self.entries))), item)
        return True

    # ------------------------------------------------------------------
    @property
    def effective_magnification(self):
        """Im Minimal-Modus wird kaum/noch gar nicht verzoegert."""
        return 1.0 if self.minimal else self.magnification

    @property
    def effective_size(self):
        return max(28, int(self.size * (0.82 if self.minimal else 1.0)))

    def clamped(self):
        """Werte auf sinnvolle Bereiche begrenzen."""
        self.size = min(128, max(24, int(self.size)))
        self.magnification = min(3.5, max(1.0, float(self.magnification)))
        self.radius = min(600, max(40, int(self.radius)))
        self.spacing = min(40, max(0, int(self.spacing)))
        self.padding = min(40, max(2, int(self.padding)))
        self.fps = min(144, max(24, int(self.fps)))
        if self.position not in POSITIONS:
            self.position = "bottom"
        if self.layer not in LAYERS:
            self.layer = "desktop"
        return self