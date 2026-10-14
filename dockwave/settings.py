"""Das Einstellungsfenster.

Hier liegen saemtliche Einstellungen der Leiste - nichts bleibt im
Rechtsklick-Menue versteckt. Jede Aenderung wirkt sofort, damit man beim
Verschieben des Reglers sieht, was passiert.

Das Fenster ist bewusst knapp gehalten und stellt sich neben die Leiste,
statt sie zu ueberdecken.
"""

from dockwave import platform
from dockwave.config import APP, PADDING_MAX, PADDING_MIN, STACK
from dockwave.qt import QtCore, QtGui, QtWidgets

TITEL = "Dockwave – Einstellungen"

POSITIONS = [("Unten", "bottom"), ("Oben", "top"),
             ("Links", "left"), ("Rechts", "right")]
EBENEN = [("Immer sichtbar", "floating"), ("Auf dem Desktop", "desktop"),
          ("Ganz oben", "top")]


class SettingsDialog(QtWidgets.QDialog):
    """Alle Einstellungen der Dock-Leiste an einem Ort."""

    def __init__(self, dock, parent=None):
        super().__init__(parent)
        self.dock = dock
        self.config = dock.config
        self._regler = {}
        self._fuellt = False

        self.setWindowTitle(TITEL)
        self.setModal(False)
        self._aufbauen()
        self._lesen()
        self._groesse_setzen()
        self._platzieren()

    # ==================================================================
    # Aufbau
    # ==================================================================

    def _aufbauen(self):
        wurzel = QtWidgets.QVBoxLayout(self)
        wurzel.setContentsMargins(12, 10, 12, 10)
        wurzel.setSpacing(8)

        # --- Zahlenwerte -------------------------------------------------
        zahlen = QtWidgets.QGroupBox("Leiste")
        zl = QtWidgets.QGridLayout(zahlen)
        zl.setHorizontalSpacing(10)
        zl.setVerticalSpacing(4)
        zl.setContentsMargins(10, 6, 10, 8)

        self._schieber(zl, 0, "size", "Icon-Größe", 24, 96, "px",
                       lambda w: self._setze("size", w))
        self._schieber(zl, 1, "magnification", "Vergrößerung", 100, 350, "x",
                       lambda w: self._setze("magnification", w / 100.0))
        self._schieber(zl, 2, "radius", "Einflussbereich", 40, 600, "px",
                       lambda w: self._setze("radius", w))
        self._schieber(zl, 3, "spacing", "Abstand", 0, 40, "px",
                       lambda w: self._setze("spacing", w))
        self._schieber(zl, 4, "padding", "Innenabstand", PADDING_MIN, PADDING_MAX, "px",
                       lambda w: self._setze("padding", w))
        self._schieber(zl, 5, "fps", "Bildrate", 24, 144, "fps",
                       lambda w: self._setze("fps", w))
        wurzel.addWidget(zahlen)

        # --- Auswahl und Schalter ----------------------------------------
        wahl = QtWidgets.QGroupBox("Verhalten")
        wl = QtWidgets.QGridLayout(wahl)
        wl.setHorizontalSpacing(10)
        wl.setVerticalSpacing(4)
        wl.setContentsMargins(10, 6, 10, 8)

        self.auswahl_position = self._auswahl(wl, 0, 0, "Position", POSITIONS)
        self.auswahl_position.currentIndexChanged.connect(
            lambda: self._setze("position", self.auswahl_position.currentData()))
        self.auswahl_ebene = self._auswahl(wl, 1, 0, "Ebene", EBENEN)
        self.auswahl_ebene.currentIndexChanged.connect(
            lambda: self._setze("layer", self.auswahl_ebene.currentData()))

        self.anzeige_laufend = QtWidgets.QCheckBox("Laufende Programme")
        self.anzeige_laufend.setToolTip(
            "Zeigt unter jedem Programm, das gerade läuft, einen kleinen Punkt")
        self.anzeige_laufend.toggled.connect(
            lambda w: self._setze("show_running", w))
        self.anzeige_minimal = QtWidgets.QCheckBox("Minimal-Modus")
        self.anzeige_minimal.setToolTip(
            "Kleine Symbole, keine Vergrößerung, keine Punkte")
        self.anzeige_minimal.toggled.connect(lambda w: self._setze("minimal", w))

        # Die Schalter stehen untereinander und ueber beide Spalten. Nebeneinander
        # wuerden ihre Beschriftungen die Spalten so aufziehen, dass das Fenster
        # auf einmal doppelt so breit wird.
        wl.addWidget(self.anzeige_laufend, 2, 0, 1, 2)
        wl.addWidget(self.anzeige_minimal, 3, 0, 1, 2)

        self.anzeige_glas = QtWidgets.QCheckBox("Milchglas")
        self.anzeige_glas.setToolTip(
            "Windows zeichnet den Hintergrund hinter der Leiste weich.\n"
            "Kostet keine Rechenzeit, weil es auf der Grafikkarte passiert.")
        self.anzeige_glas.toggled.connect(lambda w: self._setze("glass", w))
        wl.addWidget(self.anzeige_glas, 4, 0, 1, 2)
        wl.setColumnStretch(1, 1)
        wurzel.addWidget(wahl)

        # --- Programme ----------------------------------------------------
        programme = QtWidgets.QGroupBox("Programme")
        pl = QtWidgets.QVBoxLayout(programme)
        pl.setSpacing(6)
        pl.setContentsMargins(10, 6, 10, 8)

        zeile = QtWidgets.QHBoxLayout()
        self.liste = QtWidgets.QListWidget()
        self.liste.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.liste.setMinimumHeight(110)
        zeile.addWidget(self.liste, 1)

        spalten = QtWidgets.QVBoxLayout()
        spalten.setSpacing(4)
        knoepfe = (("+", "Hinzufügen…", self._programm_hinzufuegen),
                   ("-", "Aus dem Dock entfernen", self._programm_entfernen),
                   ("▲", "Nach oben", lambda: self._programm_verschieben(-1)),
                   ("▼", "Nach unten", lambda: self._programm_verschieben(1)),
                   ("│", "Trenner einfügen", self._programm_trenner))
        for zeichen, hinweis, aktion in knoepfe:
            knopf = QtWidgets.QPushButton(zeichen)
            knopf.setFixedWidth(30)
            knopf.setToolTip(hinweis)
            knopf.clicked.connect(aktion)
            spalten.addWidget(knopf)
        spalten.addStretch(1)
        zeile.addLayout(spalten)
        pl.addLayout(zeile)
        wurzel.addWidget(programme)

        # --- Knöpfe -------------------------------------------------------
        knoepfe = QtWidgets.QHBoxLayout()
        zurueck = QtWidgets.QPushButton("Standard")
        zurueck.setToolTip("Alle Einstellungen auf die Standardwerte "
                           "zurücksetzen; die Programme bleiben stehen")
        zurueck.clicked.connect(self._standard)
        fertig = QtWidgets.QPushButton("Fertig")
        fertig.setDefault(True)
        fertig.clicked.connect(self.close)
        knoepfe.addWidget(zurueck)
        knoepfe.addStretch(1)
        knoepfe.addWidget(fertig)
        wurzel.addLayout(knoepfe)

    def _schieber(self, raster, zeile, feld, beschriftung, minimum, maximum,
                  einheit, aenderung):
        text = QtWidgets.QLabel(beschriftung)
        text.setMinimumWidth(118)
        schieber = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        schieber.setRange(minimum, maximum)
        schieber.setMinimumHeight(18)
        wert = QtWidgets.QLabel()
        wert.setMinimumWidth(56)
        wert.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                          QtCore.Qt.AlignmentFlag.AlignVCenter)

        def bewegt(_wert):
            zahl = schieber.value()
            self._zeige(wert, zahl, einheit)
            aenderung(zahl)

        schieber.valueChanged.connect(bewegt)
        raster.addWidget(text, zeile, 0)
        raster.addWidget(schieber, zeile, 1)
        raster.addWidget(wert, zeile, 2)
        self._regler[feld] = (schieber, wert, einheit)
        return schieber

    def _auswahl(self, raster, zeile, spalte, beschriftung, optionen):
        text = QtWidgets.QLabel(beschriftung)
        auswahl = QtWidgets.QComboBox()
        for name, wert in optionen:
            auswahl.addItem(name, wert)
        raster.addWidget(text, zeile, spalte)
        raster.addWidget(auswahl, zeile, spalte + 1)
        return auswahl

    # ==================================================================
    # Werte lesen und schreiben
    # ==================================================================

    def _lesen(self):
        """Regler fuellen, ohne dass dabei Aenderungen ausgeloest werden."""
        self._fuellt = False
        c = self.config
        self._regler_setzen("size", int(c.size), "px")
        self._regler_setzen("magnification", int(round(c.magnification * 100)), "x")
        self._regler_setzen("radius", int(c.radius), "px")
        self._regler_setzen("spacing", int(c.spacing), "px")
        self._regler_setzen("padding", int(c.padding), "px")
        self._regler_setzen("fps", int(c.fps), "fps")
        self._combo_setzen(self.auswahl_position, c.position)
        self._combo_setzen(self.auswahl_ebene, c.layer)
        self.anzeige_laufend.setChecked(bool(c.show_running))
        self.anzeige_minimal.setChecked(bool(c.minimal))
        self.anzeige_glas.setChecked(bool(c.glass))
        self.anzeige_glas.setEnabled(platform.glass_available())
        self.anzeige_glas.setToolTip(
            self.anzeige_glas.toolTip() if platform.glass_available()
            else "Dieses System zeichnet den Hintergrund nicht weich.")
        self._liste_auffuellen()
        self._fuellt = True

    def _regler_setzen(self, feld, zahl, einheit):
        schieber, wert, _ = self._regler[feld]
        schieber.blockSignals(True)
        schieber.setValue(zahl)
        schieber.blockSignals(False)
        self._zeige(wert, zahl, einheit)

    @staticmethod
    def _zeige(wert, zahl, einheit):
        if einheit == "x":
            wert.setText("%.2f x" % (zahl / 100.0))
        elif einheit == "fps":
            wert.setText("%d" % zahl)
        else:
            wert.setText("%d %s" % (zahl, einheit))

    @staticmethod
    def _combo_setzen(auswahl, wert):
        for i in range(auswahl.count()):
            if auswahl.itemData(i) == wert:
                auswahl.blockSignals(True)
                auswahl.setCurrentIndex(i)
                auswahl.blockSignals(False)
                return

    def _setze(self, feld, wert):
        if not self._fuellt:
            return
        if getattr(self.config, feld) == wert:
            return
        setattr(self.config, feld, wert)
        self.config.clamped()
        self.dock._anwenden(feld)
        self.config.save()

    # ==================================================================
    # Programme
    # ==================================================================

    def _liste_auffuellen(self):
        auswahl = {self.liste.row(aktuell)
                   for aktuell in self.liste.selectedItems()}
        self.liste.clear()
        for eintrag in self.config.entries:
            if eintrag["type"] == APP:
                beschriftung = platform.display_name(eintrag["path"])
            elif eintrag["type"] == STACK:
                beschriftung = "Ordner – alle Programme"
            else:
                beschriftung = "──── Trenner ────"
            self.liste.addItem(beschriftung)
        for zeile in auswahl:
            if 0 <= zeile < self.liste.count():
                self.liste.item(zeile).setSelected(True)

    def _programm_hinzufuegen(self):
        pfade = platform.open_app_panel(self)
        if not pfade:
            return
        for pfad in pfade:
            self.config.add_app(pfad)
        self.config.save()
        self.dock._neu_aufbauen()
        self._liste_auffuellen()

    def _programm_entfernen(self):
        zeilen = sorted((self.liste.row(x) for x in self.liste.selectedItems()),
                        reverse=True)
        if not zeilen:
            return
        for zeile in zeilen:
            self.config.remove_index(zeile)
        self.config.save()
        self.dock._neu_aufbauen()
        self._liste_auffuellen()

    def _programm_verschieben(self, richtung):
        zeilen = [self.liste.row(x) for x in self.liste.selectedItems()]
        if len(zeilen) == 1:
            von = zeilen[0]
        elif not zeilen and self.liste.currentRow() >= 0:
            von = self.liste.currentRow()
        else:
            return
        nach = von + richtung
        if not (0 <= nach < len(self.config.entries)):
            return
        self.config.move(von, nach)
        self.config.save()
        self.dock._neu_aufbauen()
        self._markiere(nach)

    def _markiere(self, zeile):
        """Genau eine Zeile markieren.

        Wichtig ist `clearSelection` davor: die Liste behaelt beim Neuaufbau
        ihre alte Markierung. Ohne das Abwaehlen waeren nach dem Verschieben
        zwei Zeilen markiert - die Pfeile gingen dann nicht mehr, und '-'
        wuerde beide Eintraege loeschen.
        """
        self._liste_auffuellen()
        self.liste.clearSelection()
        self.liste.setCurrentRow(zeile)
        if 0 <= zeile < self.liste.count():
            self.liste.item(zeile).setSelected(True)

    def _programm_trenner(self):
        """Trenner vor dem markierten Eintrag einfuegen, sonst ans Ende."""
        zeilen = [self.liste.row(x) for x in self.liste.selectedItems()]
        stelle = zeilen[0] if zeilen else len(self.config.entries)
        self.config.add_separator(stelle)
        self.config.save()
        self.dock._neu_aufbauen()
        self._markiere(stelle)

    # ==================================================================
    # Sonstiges
    # ==================================================================

    def _standard(self):
        """Alle Regler zuruecksetzen, Programmauswahl bleibt erhalten."""
        from dockwave.config import Config

        frisch = Config()
        frisch.entries = list(self.config.entries)
        for feld in ("size", "magnification", "radius", "spacing", "padding",
                     "fps", "position", "layer", "show_running", "minimal",
                     "glass", "glass_tint"):
            setattr(self.config, feld, getattr(frisch, feld))
        self.config.clamped()
        for feld in ("size", "magnification", "radius", "spacing",
                     "padding", "fps"):
            self.dock._anwenden(feld)
        self.dock._anwenden("layer")
        self.dock._anwenden("glass")
        self.config.save()
        self._lesen()

    def _groesse_setzen(self):
        """Feste, handliche Groesse - unabhaengig von der Beschriftung.

        `setMaximumWidth` greift bei Fenstern unter Windows nicht, deshalb
        wird hier ausdruecklich auf die gewuenschte Breite geschaerft.
        """
        hinweis = self.sizeHint()
        bildschirm = QtGui.QGuiApplication.primaryScreen()
        verfuegbar = (bildschirm.availableGeometry() if bildschirm is not None
                      else None)

        breite = min(520, hinweis.width())
        hoehe = hinweis.height()
        if verfuegbar is not None:
            breite = min(breite, verfuegbar.width() - 40)
            hoehe = min(hoehe, verfuegbar.height() - 40)
        self.resize(max(360, breite), max(240, hoehe))

    def _platzieren(self):
        """Neben die Leiste setzen, damit sie nicht verdeckt wird."""
        bildschirm = QtGui.QGuiApplication.primaryScreen()
        if bildschirm is None:
            return
        bild = bildschirm.availableGeometry()
        leiste = self.dock.geometry()
        rand = 16

        platz_oben = leiste.top() - bild.top()
        platz_unten = bild.bottom() - leiste.bottom()
        hoehe = self.sizeHint().height()

        if hoehe + rand <= platz_unten:
            y = leiste.bottom() + rand // 2
        elif hoehe + rand <= platz_oben:
            y = leiste.top() - hoehe - rand // 2
        else:
            y = bild.center().y() - hoehe // 2

        x = leiste.right() + rand
        if x + self.width() > bild.right():
            x = leiste.left() - self.width() - rand
        if x < bild.left() or x + self.width() > bild.right():
            x = bild.center().x() - self.width() // 2

        self.move(max(bild.left(), x),
                  max(bild.top(), min(y, bild.bottom() - hoehe)))

    def closeEvent(self, event):
        self.config.save()
        super().closeEvent(event)