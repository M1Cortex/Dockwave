# Dockwave

Eine eigene Dock-Leiste fuer **Windows** (und macOS). Die Icons schweben und
vergroessern sich unter dem Mauspfeil, genau wie im echten macOS-Dock – aber
du bestimmst selbst, welche Programme darin stehen.

Die Aufgabeleiste von Windows bleibt unangetastet. Dockwave legt sich als
zusaetzliche Leiste darueber.

Lizenz: [MIT](LICENSE) · Autor: Stanislaw Schatilo

---

## Schnellstart (Windows)

1. Den Ordner `Dockwave` auspacken, z. B. nach `C:\Dockwave`
2. **Python installieren** – noch nicht vorhanden? Von
   [python.org](https://www.python.org/downloads/) laden, bei der
   Installation den Haken bei **„Add python.exe to PATH"** setzen
3. `Start-Dockwave.bat` doppelklicken

Beim ersten Mal richtet die Datei eine eigene Umgebung ein und installiert
PyQt6. Das dauert etwa eine Minute. Danach startet das Dock sofort.

Falls sich beim Doppelklick ein schwarzes Fenster öffnet und sofort wieder
schließt: im cmd-Fenster die Fehlermeldung lesen oder den Start
manuell versuchen:

```bat
cd C:\Dockwave
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

### Beenden

Rechtsklick auf die Leiste → **Dock schließen**
oder `Stop-Dockwave.bat` doppelklicken.

### Autostart

`Win + R` → `shell:startup` → Verknüpfung auf
`Dockwave\.venv\Scripts\python.exe` erstellen und im Feld „Ziel" ergänzen:
`"C:\Dockwave\main.py"`

---

## Bedienung

| Aktion | Wie |
|---|---|
| Programm starten | Klick auf das Icon |
| Programm hinzufügen | Aus dem Startmenü oder Explorer auf die Leiste ziehen |
| Programm hinzufügen | Rechtsklick → **Programm hinzufügen…** |
| Reihenfolge ändern | Icon gedrückt halten und an die neue Stelle ziehen |
| Programm entfernen | Rechtsklick auf das Icon → **Aus Dock entfernen** |
| Alle Programme sehen | Klick auf das Ordner-Symbol ganz rechts |
| Einstellungen | Rechtsklick auf eine freie Stelle der Leiste → **Einstellungen…** |

Deine Auswahl wird gespeichert und beim nächsten Start wiederhergestellt.

Zum ersten Start füllt das Dock sich mit Programmen aus deinem Startmenü –
also mit dem, was du selbst benutzt.

### Einstellungsfenster

Rechtsklick auf eine freie Stelle der Leiste → **Einstellungen…**

Darin liegen **alle** Einstellungen der Leiste. Jeder Regler wirkt sofort –
beim Verschieben siehst du, was passiert. Das Fenster legt sich neben die
Leiste und verdeckt sie nicht.

| Gruppe | Einstellungen |
|---|---|
| **Leiste** | Icon-Größe, Vergrößerung, Einflussbereich, Abstand, Innenabstand, Bildrate |
| **Verhalten** | Position, Ebene, laufende Programme zeigen, Minimal-Modus |
| **Programme** | Hinzufügen, entfernen, sortieren, Trenner setzen |

**Abstand** ist der Grundabstand zwischen den Icons. **Innenabstand** kommt
dazu und wirkt an zwei Stellen: als zusätzliche Luft zwischen den Icons und
als Abstand vom Rand des Panels. Beide Regler bleiben unabhängig; der
tatsächliche Abstand zweier Icons ist ihre Summe.

**Standard** setzt die Zahlenwerte zurück und lässt die Programme unberührt.
Beim Schließen wird gespeichert.

Die fünf Knöpfe neben der Programmliste:

| Knopf | Wirkung |
|---|---|
| `+` | Programme auswählen und anhängen |
| `-` | Markierte Einträge entfernen |
| `▲` `▼` | Markierten Eintrag verschieben |
| `│` | Trenner **vor** dem markierten Eintrag einfügen, sonst ans Ende |

### Rechtsklick-Menü

Das Menü ist bewusst kurz und enthält nur, was man im Alltag braucht.
**Einstellungen stehen ausschließlich im Einstellungsfenster** — nicht doppelt
hier.

* **Einstellungen…** – das ganze Fenster an einem Ort
* **Programm hinzufügen…** – Dateiauswahl für mehrere Programme
* **Dock schließen** – Programm beenden

Rechtsklick **auf ein Programm** zusätzlich:

* **Öffnen**
* **Im Explorer anzeigen**
* **Aus Dock entfernen**

Rechtsklick **auf den Ordner** zusätzlich:

* **Ordner öffnen**
* **Ordner ausblenden**

---

## Warum es sich flüssig anfühlt

Die Animation ist der Kern dieser Aufgabe, deshalb hier die Entscheidungen,
die dahinterstecken.

**1. Kein Nachziehen.** Die Größe wird pro Bild *direkt* aus der
Mausposition berechnet, nicht über Frames interpoliert. Das Icon sitzt exakt
unter dem Pfeil und fühlt sich an wie eine Feder. Ein weicher
Nachzieheffekt würde sich sofort hackelig anfühlen – das ist der häufigste
Fehler in nachgebauten Docks.

**2. Kein Anker-Icon.** Viele Nachbauten richten das Layout auf ein
bestimmtes Icon aus und schalten den Anker um, sobald der Zeiger die Mitte
passiert. Das erzeugt einen harten Sprung von über 100 Pixeln. Hier ist
jede Position eine stetige Funktion der Mausposition:

1. Jedes Icon wächst nach einer angehobenen Cosinus-Kurve (`dockwave/magnify.py`).
2. Der Abstand wird **zweidimensional** gerechnet. Mit rein waagerechtem
   Abstand wäre ein Icon sofort auf Anschlag, sobald der Zeiger die Leiste
   von oben oder unten erreicht – der Aufbau fiele dann ersatzlos aus.
   Jetzt reagieren links, rechts, oben und unten identisch.
3. Jedes Wachstum weitet den Abstand zu beiden Nachbarn – sie werden
   weggeschoben statt sich zu überlappen.
4. Der Zeiger misst immer gegen die Ruhelage des Docks, nie gegen die gerade
   vergrößerte Lage. Sonst entsteht eine Rückkopplung zwischen Leistenbreite
   und Mausposition, die ebenfalls springen lässt.

Gemessen über 400 Mauspositionen liegt der größte Positionssprung bei
**0,3 Pixeln**; die vier Anfahrtrichtungen unterscheiden sich um
**0,0000** (`tools/smoke_test.py`).

**3. Icons gleich groß.** Windows liefert Icons mit sehr unterschiedlichem
transparenten Rand – eine 256-Pixel-Grafik füllt oft nur 52 % ihrer Kachel,
eine 128er dagegen 68 %. Skaliert man beide auf dieselbe Fläche, wirkt die
256er deutlich kleiner. Deshalb wird jedes Icon beim Laden auf seinen
sichtbaren Inhalt zuschchnitten und neu zentriert.

**4. Ein einziges Widget.** Die gesamte Leiste ist ein rahmenloses,
transluzentes Fenster, das selbst gezeichnet wird. Kein Layout-Manager,
keine hundert Kind-Widgets, ein Paint-Ereignis pro Bild.

**5. Vorgerenderte Bilder.** Icons werden einmal in hoher Auflösung geladen,
das Panel inklusive Schlagschatten wird in ein Pixmap gerendert und bei
Größenänderung wiederverwendet. Pro Bild wird also geblittet, nicht neu
gerastert.

**6. Fenster wächst nie.** Die Leiste wird breiter, wenn sie sich vergrößert.
Das Fenster bekommt deshalb von Anfang an die größtmögliche Breite und
ändert seine Größe nie. Nachträgliches Wachsen und Schrumpfen ist eine der
häufigsten Ursachen für Ruckler.

Messergebnis (`tools/bench.py`, 24 Icons, Windows):

| | Mittel | 99 %-Quantil | Budget bei 60 fps |
|---|---|---|---|
| Layout | 0,06 ms | 0,09 ms | |
| Zeichnen | 0,58 ms | 1,76 ms | |
| **Summe** | **0,64 ms** | **1,85 ms** | 16,67 ms |

Das sind rund 11 % des Bildbudgets. Im Ruhezustand wird gar nicht gezeichnet –
der Prozess braucht dann unter 70 MB und praktisch keine CPU.

---

## Technik

```
Dockwave/
├── main.py                    Einstiegspunkt
├── LICENSE                    MIT
├── Start-Dockwave.bat          Starter für den Explorer
├── Stop-Dockwave.bat           Beenden
├── Start-Dockwave.command      Starter für macOS
├── Stop-Dockwave.command       Beenden auf macOS
├── com.dockwave.plist          Vorlage für den Autostart auf macOS
├── requirements.txt            nur PyQt6
├── dockwave/
│   ├── app.py                 Argumente, Start, Ereignisschleife
│   ├── config.py              Einstellungen und Speichern
│   ├── dock_window.py         Fenster, Layout, Zeichnen, Maus
│   ├── settings.py            Das Einstellungsfenster
│   ├── magnify.py             Kurve der Vergrößerung
│   ├── icons.py               Icon-Beschaffung und -Cache
│   ├── platform.py            Plattform-Auswahl (macOS / Windows / sonst)
│   ├── platform_win.py        Shell, .exe/.lnk, Z-Reihenfolge, Laufzeit-Erkennung
│   ├── platform_mac.py        AppKit, echte App-Icons, .app-Bundles
│   ├── platform_null.py       Rückfall für andere Systeme
│   ├── stack.py               Der Ordner mit allen Programmen
│   └── qt.py                  PyQt6/PySide6-Kompatibilität
└── tools/
    ├── platform_test.py       Windows-Anbindung (Icons, .lnk, laufende Prozesse)
    ├── smoke_test.py          Layout, Stetigkeit, Rendern
    ├── interaction_test.py    Klicks, Ziehen, Drop, Speichern
    ├── settings_test.py       Das Einstellungsfenster
    └── bench.py               Bildlaufzeit
```

**Frame-Schleife.** Ein einziger `QTimer` mit ~16 ms treibt alles an. Gezeichnet
wird nur, wenn sich wirklich etwas geändert hat.

**Kein Fokus-Diebstahl.** Das Fenster nimmt keinen Tastendruck an und
aktiviert sich nicht, wenn du ein Icon anklickst – du kannst im Programm
darunter weiterarbeiten. Gattermaske auf das Panel: Klicks neben der Leiste
fallen an die Fenster darunter durch.

**Nur eine Instanz.** Ein zweiter Start beendet sich sofort mit einem Hinweis.

**Plattform-Trennung.** Alles außer `platform_*.py` ist betriebssystemneutral.
Die Windows-Anbindung nutzt nur `ctypes`, braucht also keine zusätzlichen
Pakete:

* Icons über die Windows-Shell, Verknüpfungen (`.lnk`) werden über
  `IShellLink` aufgelöst – sonst zeigte eine Verknüpfung nur den
  generischen Pfeil statt des echten Programmsymbols
* Starten über `os.startfile`, also wie ein Doppelklick im Explorer
* „Im Explorer anzeigen" mit markierter Datei
* Laufende Programme über `EnumWindows` + `QueryFullProcessImageName`;
  wird zusätzlich der Dateiname verglichen, weil unter Windows 11 etwa
  `C:\Windows\notepad.exe` nur ein Starter ist, der sich in den echten
  Notepad unter `WindowsApps` weiterleitet
* Z-Reihenfolge über `SetWindowPos`; „Auf dem Desktop" sortiert das Fenster
  direkt über den Desktop ein, „Immer sichtbar" ist topmost
* Als Erstbelegung: deine Startmenü-Einträge, gefiltert am PE-Header auf
  echte Fensterprogramme – keine Deinstallationsreste und keine Dienste

**Abhängigkeiten.** PyQt6 *oder* PySide6, sonst nichts.

---

## Konfiguration

Gespeichert wird in `%APPDATA%\Dockwave\dock.json`
(auf macOS: `~/Library/Application Support/Dockwave/dock.json`):

```json
{
  "entries": [
    {"type": "app", "path": "C:\\Program Files\\Firefox\\firefox.exe"},
    {"type": "separator"},
    {"type": "stack"}
  ],
  "size": 46,
  "magnification": 1.85,
  "radius": 190,
  "spacing": 8,
  "padding": 10,
  "position": "bottom",
  "layer": "floating",
  "fps": 60,
  "minimal": false,
  "show_running": true
}
```

| Schlüssel | Bedeutung |
|---|---|
| `size` | Icon-Größe in px |
| `magnification` | 1.0 = aus, 1.85 = Standard, bis 3.5 |
| `radius` | Einflussradius in px |
| `spacing` | Abstand zwischen den Icons |
| `padding` | Innenabstand der Leiste |
| `layer` | `floating` (Standard unter Windows), `desktop`, `top` |

### Kommandozeile

```bat
main.py --size 56 --magnification 2.3     :: Größe und Vergrößerung
main.py --position left --topmost         :: links, immer sichtbar
main.py --fps 120                         :: 120 Hz
main.py --minimal                         :: kompakt starten
main.py --dump-config                     :: Konfiguration anzeigen
main.py --reset                           :: alles zurücksetzen
```

---

## Tests

```bat
python tools\platform_test.py     :: Windows-Anbindung
python tools\smoke_test.py        :: Layout, Stetigkeit, Rendern
python tools\interaction_test.py  :: Klicks, Ziehen, Drop, Speichern
python tools\bench.py             :: Bildlaufzeit
```

---

## Bekannte Grenzen

* Fensterposition ist nicht frei verschiebbar – Position nur unten, oben,
  links oder rechts.
* Kein Umschalten per Tastenkürzel.
* Programme werden gestartet, aber es gibt kein Icon-Fenster für noch
  laufende Programme wie im echten macOS-Dock.
* Die Leiste sitzt auf dem primären Bildschirm.
* „Im Explorer anzeigen" öffnet ein neues Explorer-Fenster.