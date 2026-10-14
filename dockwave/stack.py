"""Der "Ordner": zeigt alle Programme des Docks nach Kategorie gruppiert."""

from collections import defaultdict

from . import platform
from .config import APP
from .qt import QtCore, QtGui, QtWidgets

ICON_PX = 44  # 2x fuer Retina

CATEGORY_NAMES = {
    "productivity": "Produktivität",
    "utilities": "Dienstprogramme",
    "developer tools": "Entwickler-Werkzeuge",
    "graphics & design": "Grafik & Design",
    "graphics": "Grafik",
    "photo video": "Fotos & Video",
    "photo": "Fotos",
    "video": "Video",
    "music": "Musik",
    "games": "Spiele",
    "entertainment": "Unterhaltung",
    "education": "Bildung",
    "business": "Wirtschaft",
    "finance": "Finanzen",
    "social networking": "Soziale Netzwerke",
    "sports": "Sport",
    "travel": "Reisen",
    "weather": "Wetter",
    "news": "News",
    "medical": "Medizin",
    "reference": "Nachschlagen",
    "lifestyle": "Lifestyle",
    "books": "Bücher",
    "navigation": "Navigation",
    "shopping": "Einkaufen",
    "food & drink": "Essen & Trinken",
    "action": "Aktionsprogramme",
    "system": "System",
    "security": "Sicherheit",
    "internet": "Internet",
    "keyboard": "Tastatur",
    "mouse": "Maus",
    "servers": "Server",
}


def _pretty_category(raw):
    """'public.app-category.productivity' -> 'Produktivität'."""
    if not raw:
        return "Sonstiges"
    name = raw.rsplit(".", 1)[-1]
    name = name.replace("-", " ").replace("_", " ").strip()
    return CATEGORY_NAMES.get(name.lower(), name.capitalize())


def _entry_icon(path):
    """Kleines Icon fuer einen Menueeintrag."""
    from . import icons

    pm = icons.app_pixmap(path, 1.0)
    if pm is None or pm.isNull():
        return QtGui.QIcon()
    scaled = pm.scaled(ICON_PX // 2, ICON_PX // 2,
                       QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                       QtCore.Qt.TransformationMode.SmoothTransformation)
    return QtGui.QIcon(scaled)


def build_stack_menu(parent, config):
    """Baut das Menue mit allen Programmen des Docks, nach Kategorie.

    Getrennt von show_stack_menu, damit es sich testen laesst - ein
    exec() wuerde im Test blockieren.
    """
    paths = [e["path"] for e in config.entries if e["type"] == APP]
    if not paths:
        return None

    groups = defaultdict(list)
    for path in paths:
        groups[_pretty_category(platform.category(path))].append(path)

    menu = QtWidgets.QMenu(parent)
    menu.setObjectName("DockwaveStackMenu")

    for category in sorted(groups):
        sub = menu.addMenu(category)
        for path in sorted(groups[category],
                           key=lambda p: platform.display_name(p).lower()):
            action = sub.addAction(_entry_icon(path), platform.display_name(path))
            action.triggered.connect(lambda _checked=False, p=path: platform.launch(p))
    return menu


def show_stack_menu(parent, global_pos, config):
    """Oeffnet das Menue an der angegebenen Bildschirmposition."""
    menu = build_stack_menu(parent, config)
    if menu is not None:
        menu.exec(global_pos)