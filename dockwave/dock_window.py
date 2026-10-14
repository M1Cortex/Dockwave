"""Das Dock-Fenster.

Aufbau und Begruendung der Entscheidungen:

* Ein einziges, rahmenloses, transluzentes Widget ohne Layout-Manager.
  Gezeichnet wird selbst per QPainter. Das ist deutlich ruhiger als hunderte
  von Kind-Widgets: pro Frame entsteht genau ein Paint-Ereignis und Qt muss
  keine Geometrie nachberechnen.

* Die Vergroesserung wird pro Frame *direkt* aus der Cursorposition berechnet
  (siehe magnify.py) - ohne Interpolation zwischen Frames. Genau so
  arbeitet der echte macOS-Dock: das Icon sitzt exakt unter dem Mauspfeil.
  Ein weicher Nachzieheffekt wuerde sich hier hackelig anfuehlen.

* Es gibt kein "Anker-Icon", an dem das Layout aufgeraengt wird. Alle
  Positionen ergeben sich stetig aus der Cursorposition, deshalb entsteht
  beim Wechsel von einem Icon zum naechsten kein Sprung.

* Panel und Schlagschatten werden in ein Pixmap gerendert und bei
  Groessenaenderung wiederverwendet. Icons werden in hoher Aufloesung
  einmal geladen und danach nur noch geblittet.

* Eine Gattermaske begrenzt die klickbare Flaeche exakt auf das Panel, damit
  Klicks neben dem Dock an die Programme darunter durchfallen.
"""

import math
import os
import time

from . import icons, platform
from .config import APP, SEPARATOR, STACK, Config
from .magnify import scales_for
from .qt import QtCore, QtGui, QtWidgets

SHADOW = 18          # Rand fuer den Schlagschatten
PANEL_RADIUS = 16    # Eckenradius des Panels
DOT_ROW = 9          # Hoehe der Zeile mit den Laufzeit-Punkten
DRAG_THRESHOLD = 5   # Pixel, ab denen ein Klick zum Ziehen wird
GAP_GROW = 1.12      # Wie stark der Abstand beim Vergroessern mitwaechst
FADE = 40.0          # Pixel, ueber die die Vergroesserung ausklingt


class DockWindow(QtWidgets.QWidget):
    """Die Dock-Leiste."""

    def __init__(self, config: Config, app_quit=None):
        self.config = config.clamped()
        self._app_quit = app_quit
        self._screen = QtGui.QGuiApplication.primaryScreen()

        super().__init__(None, (QtCore.Qt.WindowType.FramelessWindowHint
                                | QtCore.Qt.WindowType.Tool
                                | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
                                | QtCore.Qt.WindowType.WindowStaysOnTopHint))

        self.setWindowTitle("Dockwave")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # --- Zustand -----------------------------------------------------
        self._pixmaps = []          # hochaufgeloeste Pixmaps je Eintrag
        self._bounds = []           # QRectF je Eintrag (Icon-Flaeche)
        self._cursor_x = -1.0e9
        self._cursor_y = -1.0e9
        self._rest_offset = 0.0    # Lage der Ruheleiste im Fenster
        self._hover_index = -1
        self._panel_rect = QtCore.QRectF()
        self._panel_cache = None    # (Groessenkey, Pixmap)
        self._mask_key = None
        self._dirty = True

        self._running_cache = (0.0, set())
        self._tooltip_index = -2
        self._pending_tip = -1

        self._tip_timer = QtCore.QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.timeout.connect(self._show_tooltip)

        self._press_pos = None
        self._press_index = -1
        self._dragging = False
        self._drag_index = -1
        self._drag_pos = None
        self._drag_target = -1

        self._settings = None     # offenes Einstellungsfenster

        self._build_pixmaps()
        self._recompute_window_geometry()

        self._timer = QtCore.QTimer(self)
        self._timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_frame)

        self._dot_timer = QtCore.QTimer(self)
        self._dot_timer.setInterval(2000)
        self._dot_timer.timeout.connect(self._refresh_dots)

    # ==================================================================
    # Aufbau
    # ==================================================================

    @property
    def _dpr(self):
        if self._screen is None:
            return float(self.devicePixelRatioF())
        return float(self._screen.devicePixelRatio())

    def _build_pixmaps(self):
        dpr = self._dpr
        out = []
        for entry in self.config.entries:
            kind = entry["type"]
            if kind == APP:
                out.append(icons.app_pixmap(entry["path"], dpr))
            elif kind == STACK:
                out.append(icons.stack_pixmap(int(icons.RESERVE_PX * dpr)))
            else:
                out.append(None)
        self._pixmaps = out

    def base_sizes(self):
        """Basisbreite je Eintrag; Trenner sind schmal."""
        base = self.config.effective_size
        return [max(6.0, base * 0.16) if e["type"] == SEPARATOR else float(base)
                for e in self.config.entries]

    @property
    def _abstand(self):
        """Abstand zwischen zwei Icons.

        Der Innenabstand wirkt *auch* dazwischen: er schiebt die Icons
        auseinander und macht die Leiste breiter. Zusammen mit dem Rand
        bestimmt er also, wie viel Luft die Leiste hat.
        """
        return self.config.spacing + self.config.padding

    def _neutral_centers(self):
        """Icon-Mittelpunkte in Dock-Koordinaten (0 = Mitte der Leiste).

        Bewusst nicht in Fensterkoordinaten: nur so laesst sich die Breite der
        Leiste unabhaengig von der Fenstergroesse bestimmen. Beim Zeichnen
        wird alles um einen Versatz in die Fenstermitte geschoben.
        """
        sizes = self.base_sizes()
        spacing = self._abstand
        total = sum(sizes) + spacing * max(0, len(sizes) - 1)
        centers = []
        x = -total / 2.0
        for s in sizes:
            centers.append(x + s / 2.0)
            x += s + spacing
        return centers

    # ==================================================================
    # Fenstergroesse
    # ==================================================================

    def _widest_layout_width(self):
        """Breite, die das Dock im schlimmsten Fall einnimmt.

        Da die Leiste waehrend der Vergroesserung breiter wird, muss das
        Fenster von Anfang an gross genug sein. Ein nachtraegliches Wachsen
        und Schrumpfen des Fensters ist die haeufigste Ursache fuer Ruckler.
        Die Breite ergibt sich, indem die echte Layoutfunktion an allen
        interessanten Cursorpositionen durchlaufen wird.
        """
        n = len(self.config.entries)
        if n == 0:
            return 2 * (self.config.padding + SHADOW) + 60

        neutral = self._neutral_centers()
        sizes = self.base_sizes()

        # Interessante Positionen: jede Icon-Mitte und jeder Icon-Rand.
        samples = set(neutral)
        for c, s in zip(neutral, sizes):
            samples.add(c - s / 2.0)
            samples.add(c + s / 2.0)

        widest = 0.0
        for sample in sorted(samples):
            centers, used, _ = self._centers_and_sizes(sample)
            widest = max(widest, self._panel_width(centers, used))
        return widest + 2 * SHADOW + 4

    def _content_height(self):
        """Hoehe des Iconbereichs."""
        h = self.config.effective_size * self.config.effective_magnification
        if self.config.show_running and not self.config.minimal:
            h += DOT_ROW
        return h

    def _icon_center_y(self):
        """Vertikale Mitte der Icon-Reihe (alle Icons liegen auf dieser Linie).

        Der Innenabstand wirkt bewusst *nicht* auf die Hoehe: er waechst nur
        nach links und nach rechts. Die Leiste soll beim Auseinanderziehen
        nicht in die Hoehe wachsen - dann wuerde sie beim Verschieben des
        Reglers springen, weil sich die Icon-Mitte mitverschiebt.
        """
        return SHADOW + self._content_height() / 2.0

    def _recompute_window_geometry(self):
        screen = self._screen or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        avail = screen.availableGeometry()

        width = int(math.ceil(self._widest_layout_width()))
        # Die Hoehe haengt nur an Icon-Groesse und Vergroesserung, nicht am
        # Innenabstand. Der Innenabstand waechst ausschliesslich in die Breite.
        height = int(math.ceil(self._content_height() + 2 * SHADOW))
        width = max(80, min(width, geo.width()))
        height = max(50, min(height, geo.height()))

        x = geo.x() + (geo.width() - width) // 2
        if self.config.position == "bottom":
            y = geo.y() + geo.height() - height - 2
        elif self.config.position == "top":
            y = geo.y() + 2
        elif self.config.position == "left":
            x = geo.x() + 2
            y = avail.y() + (avail.height() - height) // 2
        else:
            x = geo.x() + geo.width() - width - 2
            y = avail.y() + (avail.height() - height) // 2

        self.setGeometry(x, y, width, height)

        # Lage der Leiste in der Ruhelage. Nur dagegen wird der Cursor
        # gerechnet - das entkoppelt Cursorposition und Leistenbreite.
        #
        # Hier muss dasselbe gerechnet werden wie in _layout(): mittig ist
        # der *Inhalt*, ohne Innenabstand. Waere hier die Gesamtbreite
        # angesetzt, wuerde der Cursor um genau den Innenabstand versetzt
        # gemessen - das Icon unter dem Zeiger waere dann nicht mehr das
        # mittlere, sondern eines daneben.
        rest_centers, rest_sizes = self._rest_layout()
        rest_left, rest_right = self._edges(rest_centers, rest_sizes)
        self._rest_offset = ((self.width() - (rest_right - rest_left))
                             / 2.0 - rest_left)
        self._mask_key = None
        self._panel_cache = None
        self._dirty = True

    # ==================================================================
    # Layout
    # ==================================================================

    def _centers_and_sizes(self, cursor_local, gate=1.0, cursor_y=None):
        """Layout fuer eine Cursorposition, in Dock-Koordinaten.

        Das Modell ist bewusst frei von jedem Anker-Icon und frei von einem
        "Icon folgt dem Zeiger"-Anteil:

        1. Jedes Icon waechst nach der Kurve aus magnify.scales_for().
        2. Der Abstand zweier Icons waechst um die Haelfte ihres gemeinsamen
           Wachstums - so werden Nachbarn weggeschoben, statt sich zu
           ueberlappen.
        3. Der Mittelwert der Verschiebungen wird abgezogen, damit die Leiste
           als Ganzes in der Mitte bleibt.

        Bewusst wird kein Icon am Zeiger ausgerichtet: Das Icon bleibt auf
        seiner Position und waechst nur. Genau das tut der echte macOS-Dock
        auch, und es ist stetig - ein Nachfuehren des Zeigers wuerde die
        Nachbarn nach innen ziehen und sie ueberlappen lassen.

        `gate` blendet die Vergroesserung am Panelrand weich aus. Dadurch gibt
        es beim Ueberqueren der Panelgrenze keinen harten Sprung.

        Weil jede Groesse eine stetige Funktion der Cursorposition ist, gibt
        es beim Wechsel von einem Icon zum naechsten keinen Sprung.
        """
        sizes = self.base_sizes()
        n = len(sizes)
        if n == 0:
            return [], [], []

        neutral = self._neutral_centers()
        max_scale = self.config.effective_magnification
        if cursor_local is None or max_scale <= 1.001 or gate <= 0.0:
            return list(neutral), list(sizes), [1.0] * n

        # Der Abstand wird zweidimensional gerechnet, damit ein Icon von
        # links, rechts, oben und unten gleich reagiert.
        scales = scales_for(neutral, cursor_local, self.config.radius, max_scale,
                            cursor_y=cursor_y, icon_y=self._icon_center_y())
        if gate < 1.0:
            scales = [1.0 + (s - 1.0) * gate for s in scales]

        # Trenner werden nicht vergroessert, sie schieben nur ihre Nachbarn.
        used = [base if self.config.entries[i]["type"] == SEPARATOR else base * sc
                for i, (base, sc) in enumerate(zip(sizes, scales))]
        growth = [u - s for u, s in zip(used, sizes)]

        shift = [0.0] * n
        for j in range(n - 1):
            # Damit sich zwei Icons beim Waechstum nicht ueberlappen, muss
            # ihr Mittelpunktsabstand um die Haelfte des gemeinsamen
            # Wachstums wachsen. GAP_GROW > 1 laesst zusaetzlich eine Luecke.
            # Wichtig: die Haelfte muss links nach links und rechts nach
            # rechts gehen - gleichseitig wuerde der Abstand unveraendert.
            inc = (growth[j] + growth[j + 1]) * GAP_GROW / 2.0
            shift[j] -= inc / 2.0
            shift[j + 1] += inc / 2.0

        centers = [neutral[i] + shift[i] for i in range(n)]

        # An der Mitte der Ausdehnung ausrichten. Damit bleibt die Leiste
        # dort liegen, wo sie liegt, und waechst nur nach aussen - statt
        # bei jeder Vergroesserung zur Fenstermitte zu rutschen.
        left, right = self._edges(centers, used)
        correction = (left + right) / 2.0
        return [c - correction for c in centers], used, scales

    def _edges(self, centers, sizes):
        if not centers:
            return 0.0, 0.0
        left = min(c - s / 2.0 for c, s in zip(centers, sizes))
        right = max(c + s / 2.0 for c, s in zip(centers, sizes))
        return left, right

    def _rest_layout(self):
        """Mittelpunkte und Groessen der Leiste ohne Vergroesserung."""
        sizes = self.base_sizes()
        return self._neutral_centers(), sizes

    def _panel_width(self, centers, sizes):
        if not centers:
            return 0.0
        left, right = self._edges(centers, sizes)
        return right - left + 2 * self.config.padding

    def _activation(self, cursor_x):
        """Wie stark die Vergroesserung gerade wirkt (stetig 0..1)."""
        r = self._panel_rect
        if r.width() <= 0 or cursor_x <= -1.0e8:
            return 0.0
        if r.left() <= cursor_x <= r.right():
            return 1.0
        if cursor_x < r.left():
            t = (cursor_x - (r.left() - FADE)) / FADE
        else:
            t = ((r.right() + FADE) - cursor_x) / FADE
        return max(0.0, min(1.0, t))

    def _layout(self, cursor_x):
        if not self.config.entries:
            self._bounds = []
            self._panel_rect = QtCore.QRectF()
            self._hover_index = -1
            return

        pad = self.config.padding   # wirkt nur nach links und nach rechts
        content_h = self._content_height()
        center_y = SHADOW + content_h / 2.0

        gate = self._activation(cursor_x)
        # Der Cursor wird immer gegen die Ruhelage des Docks gemessen, nicht
        # gegen die gerade vergroesserte. Sonst entsteht eine Rueckkopplung
        # zwischen Leistenbreite und Cursorposition, die springen laesst.
        cursor_local = (cursor_x - self._rest_offset) if cursor_x > -1.0e8 else None

        # Ohne bekannte Hoehe (Zeiger noch nie ueber der Leiste gewesen)
        # faellt die Rechnung auf den waagerechten Abstand zurueck.
        cursor_y = self._cursor_y if self._cursor_y > -1.0e8 else None

        centers, used, _ = self._centers_and_sizes(cursor_local, gate, cursor_y)

        # Die tatsaechliche Leiste mittig im Fenster platzieren.
        #
        # Wichtig: Mittig ist der *Inhalt* - die Icons ohne Innenabstand.
        # Rechnet man mit der Gesamtbreite (Icons plus Innenabstand) und
        # zieht den Innenabstand dann noch einmal ab, sitzt das Panel genau
        # um diesen Betrag zu weit links. Bei breiter Leiste ragt es dann
        # links aus dem Fenster heraus und wird dort eckig abgeschnitten,
        # waehrend rechts die runden Ecken sichtbar bleiben.
        left_edge, right_edge = self._edges(centers, used)
        inhalt = right_edge - left_edge
        offset = (self.width() - inhalt) / 2.0 - left_edge

        hover = -1
        if gate > 0.0:
            neutral = self._neutral_centers()
            best = 1.0e18
            for i, c in enumerate(neutral):
                d = abs(c - cursor_local)
                if d < best:
                    best = d
                    hover = i
        self._hover_index = hover

        self._bounds = [
            QtCore.QRectF(c + offset - s / 2.0, center_y - s / 2.0, s, s)
            for c, s in zip(centers, used)
        ]

        self._panel_rect = QtCore.QRectF(offset + left_edge - pad, SHADOW,
                                         inhalt + 2 * pad, content_h)

        self._update_tooltip(hover)

    def _index_at(self, x, y):
        for i, r in enumerate(self._bounds):
            if r.contains(x, y):
                return i
        return -1

    def _target_index(self, cursor_x):
        for i, r in enumerate(self._bounds):
            if cursor_x < r.center().x():
                return i
        return len(self._bounds)

    # ==================================================================
    # Zeichnen
    # ==================================================================

    def _panel_pixmap(self, width, height, dpr):
        """Panel inklusive Schlagschatten, mit Cache nach Groesse."""
        key = (int(width) // 2 * 2, int(height) // 2 * 2, round(dpr, 2))
        if self._panel_cache is not None and self._panel_cache[0] == key:
            return self._panel_cache[1]

        full = QtCore.QSize(key[0] + SHADOW * 2, key[1] + SHADOW * 2)
        pm = QtGui.QPixmap(full)
        pm.setDevicePixelRatio(dpr)
        pm.fill(QtCore.Qt.GlobalColor.transparent)

        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        body = QtCore.QRectF(SHADOW, SHADOW, key[0], key[1])

        # Schlagschatten in mehreren weichen Durchgaengen. Ein echter
        # Blur-Filter waere pro Frame der teuerste Posten der Animation.
        for i in range(8, 0, -1):
            t = i / 8.0
            grow = SHADOW * t
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, int(52 * (1.0 - t) ** 1.7)), 2.0))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(body.adjusted(-grow, -grow * 0.3, grow, grow * 1.05),
                              PANEL_RADIUS + grow, PANEL_RADIUS + grow)

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 32), 1.0))
        p.setBrush(QtGui.QBrush(QtGui.QColor(40, 42, 48, 182)))
        p.drawRoundedRect(body, PANEL_RADIUS, PANEL_RADIUS)

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 44), 1.0))
        y = body.top() + 1.0
        p.drawLine(QtCore.QLineF(body.left() + PANEL_RADIUS, y,
                                 body.right() - PANEL_RADIUS, y))
        p.end()

        self._panel_cache = (key, pm)
        return pm

    def paintEvent(self, event):
        if not self._bounds:
            return

        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        panel = self._panel_rect
        pm = self._panel_pixmap(panel.width(), panel.height(), self._dpr)
        p.drawPixmap(QtCore.QPointF(panel.left() - SHADOW, panel.top() - SHADOW), pm)

        running = self._running_set() if self.config.show_running else set()

        for i, rect in enumerate(self._bounds):
            entry = self.config.entries[i]
            pixmap = self._pixmaps[i]
            if pixmap is None:
                self._paint_separator(p, rect, panel)
                continue
            if self._dragging and i == self._drag_index:
                continue
            p.drawPixmap(rect, pixmap, QtCore.QRectF(pixmap.rect()))
            if (entry["type"] == APP and self.config.show_running
                    and not self.config.minimal
                    and self._is_running(entry["path"], running)):
                self._paint_running_dot(p, panel, rect)

        if self._dragging and self._drag_pos is not None and self._drag_index >= 0:
            self._paint_drag_ghost(p)
        if self._dragging and 0 <= self._drag_target < len(self._bounds):
            self._paint_drop_marker(p, panel)

        p.end()

    @staticmethod
    def _paint_separator(p, rect, panel):
        h = min(panel.height() * 0.52, 48.0)
        top = panel.center().y() - h / 2.0
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 70), 1.4))
        p.drawLine(QtCore.QLineF(rect.center().x(), top,
                                 rect.center().x(), top + h))

    @staticmethod
    def _paint_running_dot(p, panel, rect):
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 230)))
        p.drawEllipse(QtCore.QPointF(rect.center().x(), panel.bottom() - 5.0), 4.0, 4.0)

    def _paint_drag_ghost(self, p):
        if self._drag_pos is None or not (0 <= self._drag_index < len(self._pixmaps)):
            return
        pixmap = self._pixmaps[self._drag_index]
        if pixmap is None:
            return
        size = self.config.effective_size * 1.1
        pos = self._drag_pos
        target = QtCore.QRectF(pos.x() - size / 2.0, pos.y() - size / 2.0, size, size)
        p.setOpacity(0.92)
        p.drawPixmap(target, pixmap, QtCore.QRectF(pixmap.rect()))
        p.setOpacity(1.0)

    def _paint_drop_marker(self, p, panel):
        rect = self._bounds[self._drag_target]
        x = rect.left() - self._abstand / 2.0 - 1.0
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 210), 3.0))
        p.drawLine(QtCore.QLineF(x, panel.top() + 10, x, panel.bottom() - 10))

    # ==================================================================
    # Laufende Apps
    # ==================================================================

    def _running_set(self):
        now = time.monotonic()
        ts, keys = self._running_cache
        if now - ts < 2.0:
            return keys
        self._running_cache = (now, platform.running_keys())
        return self._running_cache[1]

    @staticmethod
    def _is_running(path, keys):
        if not keys:
            return False
        return platform.is_running(path, keys)

    def _refresh_dots(self):
        if self.config.show_running and not self.config.minimal:
            self._dirty = True

    # ==================================================================
    # Schleife
    # ==================================================================

    def _apply_layer(self):
        """Fenster-Ebene setzen - auch wenn sie zur Laufzeit gewechselt wird.

        Ohne Plattform-Anbindung braucht es ein neues Fenster-Flag, weil Qt
        WindowStaysOnTopHint nur beim Anlegen ausgewertet wird.
        """
        needs_flag = not platform.available() and self.config.layer != "floating"
        if needs_flag and self.testAttribute(
                QtCore.Qt.WidgetAttribute.WA_WState_ExplicitShowHide):
            visible = self.isVisible()
            self.setWindowFlags(self._window_flags())
            if visible:
                self.show()
        platform.apply_window_level(self, self.config.layer)
        self.raise_()

    def _window_flags(self):
        flags = (QtCore.Qt.WindowType.FramelessWindowHint
                 | QtCore.Qt.WindowType.Tool
                 | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus)
        if self.config.layer in ("floating", "top"):
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        return flags

    def start(self):
        self.show()
        self._apply_layer()
        self._timer.start(max(4, int(1000 / max(1, self.config.fps))))
        if self.config.show_running and not self.config.minimal:
            self._dot_timer.start()

    def stop(self):
        self._timer.stop()
        self._dot_timer.stop()

    def closeEvent(self, event):
        # Wichtig: hier wird bewusst NICHT gespeichert. Die Anwendung
        # speichert beim Beenden (siehe app.py), und wenn ein Testlauf das
        # Fenster schliesst, wuerden sonst Testdaten in der echten
        # Konfiguration landen.
        self.stop()
        super().closeEvent(event)

    def _on_frame(self):
        previous = self._hover_index
        self._layout(self._cursor_x)
        self._update_mask()
        if self._dirty or previous != self._hover_index:
            self._dirty = False
            self.update()

    # ==================================================================
    # Maus
    # ==================================================================

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._cursor_x = pos.x()
        self._cursor_y = pos.y()

        if self._press_pos is not None and self._press_index >= 0:
            dx = pos.x() - self._press_pos.x()
            dy = pos.y() - self._press_pos.y()
            if not self._dragging and (abs(dx) > DRAG_THRESHOLD
                                        or abs(dy) > DRAG_THRESHOLD):
                self._dragging = True
                self._drag_index = self._press_index
            if self._dragging:
                self._drag_pos = pos
                self._drag_target = self._target_index(pos.x())

        self._dirty = True

    def mousePressEvent(self, event):
        button = event.button()
        if button == QtCore.Qt.MouseButton.LeftButton:
            pos = event.position()
            self._press_pos = pos
            self._press_index = self._index_at(pos.x(), pos.y())
            self._dragging = False
            self._drag_index = -1
            self._drag_target = -1
        elif button == QtCore.Qt.MouseButton.RightButton:
            pos = event.position()
            index = self._index_at(pos.x(), pos.y())
            self._context_menu(index, event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        index = self._press_index
        was_drag = self._dragging
        drag_index = self._drag_index
        target = self._drag_target

        self._press_pos = None
        self._press_index = -1
        self._dragging = False
        self._drag_index = -1
        self._drag_target = -1
        self._drag_pos = None
        self._dirty = True

        if not was_drag:
            if index >= 0:
                self._activate(index)
        elif (drag_index >= 0 and 0 <= target <= len(self.config.entries)
                and target != drag_index):
            final = target if target < drag_index else target - 1
            self.config.move(drag_index, final)
            self._neu_aufbauen()
            self.config.save()

    def leaveEvent(self, event):
        self._cursor_x = -1.0e9
        self._cursor_y = -1.0e9
        self._tooltip_index = -2
        self._tip_timer.stop()
        QtWidgets.QToolTip.hideText()
        self._dirty = True

    def enterEvent(self, event):
        self._dirty = True

    # ==================================================================
    # Tooltip
    # ==================================================================

    def _update_tooltip(self, hover):
        """Tooltip erst zeigen, wenn der Zeiger kurz auf einem Icon ruht."""
        if hover == self._tooltip_index:
            return
        self._tooltip_index = hover
        self._tip_timer.stop()
        self._pending_tip = hover
        if hover < 0:
            QtWidgets.QToolTip.hideText()
            return
        self._tip_timer.start(350)

    def _show_tooltip(self):
        index = self._pending_tip
        if not (0 <= index < len(self.config.entries)) or not self._bounds:
            return
        if self._cursor_x < -1.0e8:
            return
        entry = self.config.entries[index]
        if entry["type"] == APP:
            text = platform.display_name(entry["path"])
        elif entry["type"] == STACK:
            text = "Alle Programme" if platform.IS_WIN else "Alle Apps"
        else:
            return
        point = self.mapToGlobal(self._bounds[index].center().toPoint())
        QtWidgets.QToolTip.showText(point, text, self)

    # ==================================================================
    # Aktionen
    # ==================================================================

    def _activate(self, index):
        entry = self.config.entries[index]
        if entry["type"] == APP:
            platform.launch(entry["path"])
        elif entry["type"] == STACK:
            from .stack import show_stack_menu
            anchor = self.mapToGlobal(
                QtCore.QPoint(int(self._panel_rect.center().x()),
                              int(self._panel_rect.bottom())))
            show_stack_menu(self, anchor, self.config)

    def _rebuild(self):
        self._build_pixmaps()
        self._recompute_window_geometry()
        self._bounds = []
        self._panel_rect = QtCore.QRectF()
        self._hover_index = -1
        self._dirty = True

    def _neu_aufbauen(self):
        """Nach einer Aenderung neu aufbauen - ohne Sprung und ohne Flackern.

        Die Cursorposition wird vorher in Dock-Koordinaten festgehalten und
        danach wiederhergestellt. Ohne das waere nach dem Verschieben eines
        Groessenreglers ein anderes Icon unter dem Zeiger, und fuer ein Bild
        faellt die Leiste auf ihre Grundgroesse zurueck - beides sieht man
        sofort.
        """
        ruhe_x = (self._cursor_x - self._rest_offset
                  if self._cursor_x > -1.0e8 else None)
        mitte = self._icon_center_y()
        ruhe_y = (self._cursor_y - mitte if self._cursor_y > -1.0e8 else None)

        self._rebuild()

        if ruhe_x is None:
            self._cursor_x = -1.0e9
            self._cursor_y = -1.0e9
        else:
            self._cursor_x = ruhe_x + self._rest_offset
            self._cursor_y = ruhe_y + self._icon_center_y()
        self._layout(self._cursor_x)
        self._update_mask()
        self._dirty = True

    # ==================================================================
    # Einstellungen
    # ==================================================================

    def _anwenden(self, feld):
        """Eine geaenderte Einstellung auf die Leiste uebertragen.

        Das Einstellungsfenster aendert die Werte direkt in der
        Konfiguration; hier passiert das, was sich daraus ergibt.
        """
        if feld == "layer":
            self._apply_layer()
        elif feld == "position":
            self._screen = QtGui.QGuiApplication.primaryScreen()
            self._recompute_window_geometry()
        elif feld == "fps":
            self._timer.setInterval(max(4, int(1000 / max(1, self.config.fps))))
            self._dirty = True
        elif feld == "show_running":
            if self.config.show_running and not self.config.minimal:
                self._dot_timer.start()
            else:
                self._dot_timer.stop()
            self._neu_aufbauen()
        else:
            self._neu_aufbauen()

    def _open_settings(self):
        """Einstellungsfenster oeffnen bzw. ein vorhandenes vorholen."""
        from .settings import SettingsDialog

        if self._settings is not None:
            try:
                self._settings.close()
                self._settings = None
            except RuntimeError:
                pass

        fenster = SettingsDialog(self)
        fenster.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        fenster.destroyed.connect(self._vergisst)
        self._settings = fenster
        fenster.show()
        fenster.raise_()
        fenster.activateWindow()

    def _vergisst(self, *args):
        self._settings = None

    # ==================================================================
    # Kontextmenue
    # ==================================================================

    def _context_menu(self, index, global_pos):
        menu = QtWidgets.QMenu(self)

        menu.addAction("Einstellungen…", self._open_settings)
        menu.addSeparator()

        if 0 <= index < len(self.config.entries):
            entry = self.config.entries[index]
            if entry["type"] == APP:
                path = entry["path"]
                name = platform.display_name(path)
                menu.addAction(name).setEnabled(False)
                menu.addSeparator()
                menu.addAction("Öffnen", lambda: platform.launch(path))
                menu.addAction(_reveal_label(), lambda: platform.reveal(path))
                menu.addSeparator()
                menu.addAction("Aus Dock entfernen", lambda: self._remove(index))
            elif entry["type"] == STACK:
                menu.addAction("Ordner öffnen", lambda: self._activate(index))
                menu.addAction("Ordner ausblenden", lambda: self._remove(index))

        menu.addSeparator()
        menu.addAction(_add_label(), self._add_via_dialog)

        menu.addSeparator()
        menu.addAction("Dock schließen", self.quit_app)
        menu.exec(global_pos)

    def _remove(self, index):
        self.config.remove_index(index)
        self._neu_aufbauen()
        self.config.save()

    def _add_via_dialog(self):
        paths = platform.open_app_panel(self)
        if not paths:
            return
        for path in paths:
            self.config.add_app(path)
        self._neu_aufbauen()
        self.config.save()

    def quit_app(self):
        if self._app_quit:
            self._app_quit()
        else:
            QtWidgets.QApplication.instance().quit()

    # ==================================================================
    # Drag & Drop aus dem Datei-Explorer
    # ==================================================================

    def dragEnterEvent(self, event):
        if self._has_programs(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._has_programs(event.mimeData()):
            self._cursor_x = event.position().x()
            self._cursor_y = event.position().y()
            self._dirty = True
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        added = 0
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            # QUrl liefert auf Windows Schraegstriche - fuer Anzeige und
            # Vergleich in der Konfiguration sind-native Trennzeichen besser.
            path = os.path.normpath(path)
            # Verzeichnisse duerfen mitgezogen werden (Programmordner);
            # eine Datei muss eine der bekannten Endungen haben.
            if os.path.isdir(path) or platform.is_launchable(path):
                if self.config.add_app(path) >= 0:
                    added += 1
        if added:
            self._neu_aufbauen()
            self.config.save()
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _has_programs(mime):
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            path = url.toLocalFile()
            if not path:
                continue
            if platform.is_launchable(path) or os.path.isdir(path):
                return True
        return False

    # ==================================================================
    # Gattermaske
    # ==================================================================

    def _update_mask(self):
        """Klickbaren Bereich exakt auf das Panel begrenzen."""
        panel = self._panel_rect
        if panel.width() <= 0:
            return
        rect = panel.toRect().adjusted(-SHADOW, -SHADOW, SHADOW, SHADOW)
        key = (rect.left(), rect.top(), rect.width() // 2, rect.height() // 2)
        if key == self._mask_key:
            return
        self._mask_key = key
        self.setMask(QtGui.QRegion(rect))

    # ==================================================================
    # Bei Groessenaenderung
    # ==================================================================

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._mask_key = None
        self._panel_cache = None
        self._dirty = True


# ==================================================================
# Beschriftungen, die je nach Plattform anders heissen
# ==================================================================

def _reveal_label():
    return "Im Explorer anzeigen" if platform.IS_WIN else "Im Finder zeigen"


def _add_label():
    return "Programm hinzufügen…" if platform.IS_WIN else "App hinzufügen…"