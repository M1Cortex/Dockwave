"""Icon-Beschaffung und -Cache.

Die Icons werden einmal in hoher Aufloesung gerendert und danach nur noch
skaliert gezeichnet. Das ist der entscheidende Punkt fuer eine ruhige
Animation: pro Frame wird ein bereits fertiges Bild geblittet, nicht neu
gerastert.
"""

import os

from . import platform
from .qt import QtCore, QtGui, QtWidgets

# Grosse der Pixel-Caches: so fein aufgeloest, dass auch das groesste
# verzoegerte Icon noch scharf bleibt.
RESERVE_PX = 256

_cache = {}


def _shell_icon(path, px):
    """Icon ueber die System-Shell - die beste Quelle auf Windows."""
    try:
        provider = QtWidgets.QFileIconProvider()
        icon = provider.icon(QtCore.QFileInfo(str(path)))
        if not icon.isNull():
            pm = icon.pixmap(QtCore.QSize(px, px))
            if not pm.isNull():
                return pm
    except Exception:
        pass
    return None


def _bundle_icon(path, px):
    """Icon direkt aus einem .app-Bundle (.icns)."""
    resources = os.path.join(path, "Contents", "Resources")
    icns = None
    try:
        for name in sorted(os.listdir(resources)):
            if name.lower().endswith(".icns"):
                icns = os.path.join(resources, name)
                break
    except OSError:
        icns = None

    if icns:
        reader = QtGui.QImageReader(icns)
        if reader.canRead():
            image = reader.read()
            if not image.isNull():
                return _to_pixmap(image, px)
    return None


def _qt_fallback(app_path, px):
    """Letzter Versuch: QIcon direkt auf den Pfad."""
    icon = QtGui.QIcon(app_path)
    if not icon.isNull():
        pm = icon.pixmap(QtCore.QSize(px, px))
        if not pm.isNull():
            return pm
    return None


def _to_pixmap(image, px):
    if px > 0:
        image = image.scaled(px, px,
                             QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                             QtCore.Qt.TransformationMode.SmoothTransformation)
    return QtGui.QPixmap.fromImage(image)


def _content_box(image):
    """Umschliessendes Rechteck aller sichtbaren Pixel.

    Windows-Icons haben unterschiedlich viel transparenten Rand: eine
    256-Pixel-Grafik aus dem System kommt oft nur zu ~52 % Fuellung, eine
    128-Pixel zu ~68 %. Beim Skalieren auf dieselbe Kachel wirkt die
    256er dann deutlich kleiner. Deshalb schneiden wir den Rand ab.
    """
    if image.isNull():
        return None

    img = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return None

    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    data = memoryview(ptr)

    step = 1 if max(w, h) <= 96 else 2
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(0, h, step):
        row = y * w * 4
        for x in range(0, w, step):
            if data[row + x * 4 + 3] > 12:      # BGRA -> Alphakanal
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0 or max_y < 0:
        return None
    return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def normalize(pixmap, target_px, fill=0.92):
    """Schneidet den transparenten Rand ab und zentriert neu.

    Dadurch sehen alle Icons gleich gross aus, egal mit welcher
    Aufloesung und wie viel Leerraum Windows sie mitliefert.
    """
    if pixmap is None or pixmap.isNull():
        return pixmap
    box = _content_box(pixmap.toImage())
    if box is None:
        return pixmap

    x, y, w, h = box
    if w >= pixmap.width() * 0.98 and h >= pixmap.height() * 0.98:
        return pixmap                     # randlos, nichts zu tun

    inner = max(1, int(target_px * fill))
    cropped = pixmap.copy(QtCore.QRect(x, y, w, h))
    scaled = cropped.scaled(inner, inner,
                            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation)

    out = QtGui.QPixmap(target_px, target_px)
    out.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(out)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(QtCore.QPoint((target_px - scaled.width()) // 2,
                                     (target_px - scaled.height()) // 2), scaled)
    painter.end()
    return out


def app_pixmap(app_path, dpr=1.0):
    """Hochaufloestes Pixmap fuer ein Programm, dauerhaft gecacht."""
    px = int(RESERVE_PX * max(1.0, float(dpr)))
    key = ("app", app_path, px)
    hit = _cache.get(key)
    if hit is not None:
        return hit

    # Verknuepfungen zuerst aufloesen: eine .lnk zeigt sonst nur den
    # generischen Pfeil statt des echten Programmsymbols.
    real = platform.resolve(app_path)

    pm = platform.icon_pixmap(real, px)          # macOS: AppKit
    if pm is None or pm.isNull():
        pm = _shell_icon(real, px)               # Windows: Shell
    if pm is None or pm.isNull():
        pm = _bundle_icon(real, px)              # macOS: .icns
    if pm is None or pm.isNull():
        pm = _qt_fallback(real, px)
    if pm is None or pm.isNull():
        pm = placeholder_pixmap(px)

    # Rand abschneiden, damit alle Icons gleich wirken.
    pm = normalize(pm, px)

    _cache[key] = pm
    return pm


def placeholder_pixmap(px):
    """Neutraler Ersatz, falls kein Icon gefunden wird."""
    key = ("placeholder", px)
    hit = _cache.get(key)
    if hit is not None:
        return hit

    pm = QtGui.QPixmap(px, px)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QtGui.QBrush(QtGui.QColor(120, 124, 134, 90)))
    p.setPen(QtGui.QPen(QtGui.QColor(220, 224, 232, 150), max(1.0, px / 64)))
    r = QtCore.QRectF(px * 0.18, px * 0.18, px * 0.64, px * 0.64)
    p.drawRoundedRect(r, px * 0.18, px * 0.18)
    p.end()
    _cache[key] = pm
    return pm


# ----------------------------------------------------------------------
# Platzhalter fuer die eingebauten Symbole
# ----------------------------------------------------------------------

def stack_pixmap(px):
    """Ordner-Symbol: ein Stapel Apps."""
    return _vector_pixmap(px, "stack")


def _vector_pixmap(px, kind):
    key = (kind, px)
    hit = _cache.get(key)
    if hit is not None:
        return hit

    pm = QtGui.QPixmap(px, px)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    u = px / 64.0  # Einheitsraster

    if kind == "stack":
        # Drei uebereinanderliegende Karten = Ordner/Stapel. Die Proportionen
        # sind so gewaehlt, dass das Symbol zusammen mit den App-Icons gleich
        # gross wirkt (~85 % des Rasters).
        card_w = 58.0 * u
        card_h = 20.0 * u
        step = 16.0 * u
        top0 = 8.0 * u
        for i, alpha in enumerate((90, 150, 255)):
            top = top0 + i * step
            x = (px - card_w) / 2.0
            rect = QtCore.QRectF(x, top, card_w, card_h)
            p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, alpha)))
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 1.5 * u))
            p.drawRoundedRect(rect, 5 * u, 5 * u)
        # Inhalt der obersten Karte andeuten
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QBrush(QtGui.QColor(120, 170, 255, 235)))
        w = 30 * u
        x = (px - w) / 2.0
        p.drawRoundedRect(QtCore.QRectF(x, top0 + 7 * u, w, 7 * u), 2 * u, 2 * u)
    p.end()

    _cache[key] = pm
    return pm


def clear_cache():
    _cache.clear()