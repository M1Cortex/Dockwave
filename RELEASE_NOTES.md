## Was ist neu

### Einstellungsfenster

Rechtsklick auf eine freie Stelle der Leiste → **Einstellungen…**

Darin liegen jetzt **alle** Einstellungen an einem Ort. Jeder Regler wirkt
sofort — beim Verschieben siehst du, was passiert. Das Fenster legt sich neben
die Leiste und verdeckt sie nicht.

| Gruppe | Einstellungen |
|---|---|
| **Leiste** | Icon-Größe, Vergrößerung, Einflussbereich, Abstand, Innenabstand, Bildrate |
| **Verhalten** | Position, Ebene, laufende Programme zeigen, Minimal-Modus |
| **Programme** | Hinzufügen, entfernen, sortieren, Trenner setzen |

**Standard** setzt die Zahlenwerte zurück und lässt die Programme unberührt.

Das Rechtsklick-Menü ist entsprechend kurz geworden: **Einstellungen…**,
**Programm hinzufügen…**, **Dock schließen** — dazu am Icon **Öffnen**,
**Im Explorer anzeigen**, **Aus Dock entfernen**. Jede Einstellung steht jetzt
genau einmal da, nicht doppelt.

### Trenner einfügen

Im Fenster unter **Programme** gibt es einen fünften Knopf `│`. Er setzt einen
Trenner **vor** den markierten Eintrag, oder ans Ende, wenn nichts markiert
ist. Mehrere Trenner sind möglich; jeder ist schmal gezeichnet statt als Icon
und über `–` wieder entfernbar.

### Neue Standardwerte

| | vorher | jetzt |
|---|---|---|
| Position | unten | **oben** |
| Ebene | Immer sichtbar | **Auf dem Desktop** |
| Abstand | 8 px | **28 px (sehr weit)** |
| Einflussbereich | 190 px | **260 px (weit)** |

Gilt für neue Installationen. Wer schon eine `dock.json` hat, behält seine
Werte.

## Fehlerbehebungen

**Die Leiste saß schief.** Das Panel wurde um genau den Innenabstand zu weit
links platziert — der Innenabstand war zweimal in die Rechnung eingeflossen.
Bei breiter Leiste ragte sie dadurch links aus dem Fenster und wurde dort
eckig abgeschnitten, während rechts die runden Ecken sichtbar blieben. Jetzt
ragt sie links und rechts gleich viel heraus.

**„Innenabstand" machte die Leiste höher.** Er wirkt jetzt ausschließlich in
der Breite: er schiebt die Icons auseinander und vergrößert den Rand nach links
und nach rechts. Die Höhe hängt nur noch an Icon-Größe und Vergrößerung.

**Pfeile blieben nach dem ersten Klick stecken.** Beim Verschieben eines
Eintrags blieb die alte Markierung stehen, sodass zwei Zeilen markiert waren.
Der nächste Klick tat nichts, und `–` löschte dann beide Einträge. Jetzt bleibt
immer genau eine Markierung.

**Die Leiste sprang beim Verschieben eines Reglers.** Nach einer Größenänderung
verwarf die Leiste Cursorposition und Layout für ein Bild — ein anderes Icon
lag kurz unter dem Zeiger. Jetzt wird die Position in Dock-Koordinaten
festgehalten und direkt weitergezeichnet.

**Das Einstellungsfenster blieb klein.** Die Programmliste war auf 150 px
Deckelung begrenzt; alles andere dehnte sich, nur sie nicht.

**Deine Programmliste konnte verloren gehen.** Vor jedem Schreiben der
Konfiguration wird jetzt eine Sicherung `dock.json.bak` angelegt. Ein
versehentliches Überschreiben ist damit rückgängig zu machen.

## Technisch

* **218 Prüfungen, 0 Fehler.** Neu: 124 im Einstellungsfenster — Vollständigkeit
  der Regler, sofortige Wirkung, Grenzwerte, Programme verwalten, Trenner,
  Fenstergroße, Position neben der Leiste, Symmetrie des Panels.
* Jeder Testlauf benutzt ein temporäres Konfigurationsverzeichnis
  (`tools/_testconfig.py`) und kann die echte `dock.json` nicht erreichen.
  Beim Schließen des Leistenfensters wird grundsätzlich nicht gespeichert.
* Die Animation bleibt unverändert weich: **0,36 px** größter Positionssprung
  über 400 Mauspositionen, **0,0000** Unterschied zwischen den vier
  Anfahrtrichtungen.

## Bekannte Grenze

Bei sehr großem Innenabstand und vielen Programmen wird die Leiste breiter als
der Bildschirm und in der Mitte zusammengedrückt. Abhilfe: Innenabstand
verringern oder Programme ausblenden. Automatisch herunterregeln tut die
Leiste das noch nicht.

## Installieren

Quelle:

```
git clone https://github.com/M1Cortex/Dockwave.git
cd Dockwave
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Oder die portable `Dockwave.exe` herunterladen und doppelklicken — die bringt
alles mit und braucht keine Installation.