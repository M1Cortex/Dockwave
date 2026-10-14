"""Magnification-Kurve des Docks.

Wichtig fuer das "fluessige" Gefuehl: Die Skalierung wird *direkt* aus der
Cursorposition berechnet und nicht ueber Frames interpoliert. Genau so
arbeitet auch der echte macOS-Dock - das Icon sitzt exakt unter dem Zeiger und
fuehlt sich dadurch an wie eine Physicalche Feder, nicht wie eine Animation mit
Verzoegerung. Die Weichheit entsteht allein durch die stetige Kurve und eine
stabile Bildrate.
"""

import math

# Anzahl Samples fuer die Lookup-Tabelle. Die Kurve wird pro Frame fuer alle
# Icons ausgewertet; eine Tabelle macht daraus eine Array-Indexierung statt
# mehrerer trigonometrischer Aufrufe.
_TABLE_SIZE = 512


def _build_table(max_scale: float) -> list:
    """Vorberechnete Kurve, indiziert nach der normierten Distanz d/radius."""
    table = []
    for i in range(_TABLE_SIZE + 1):
        d = i / _TABLE_SIZE            # 0 = direkt unter dem Cursor, 1 = ausser Reichweite
        # Angehobene Cosinus-Kurve: bei d=0 der Maximalwert, bei d=1 der Wert 1.
        # Das ist eine gute Naeherung an die Dock-Kurve von macOS.
        f = 0.5 * (1.0 + math.cos(math.pi * d))
        table.append(1.0 + (max_scale - 1.0) * f)
    return table


_TABLES: dict = {}


def _table_for(max_scale: float) -> list:
    key = round(max_scale, 3)
    table = _TABLES.get(key)
    if table is None:
        table = _build_table(max_scale)
        _TABLES[key] = table
    return table


def scale_at(distance: float, radius: float, max_scale: float) -> float:
    """Skalierungsfaktor fuer einen Abstand zum Cursor.

    Args:
        distance:  Pixel Abstand zwischen Icon-Mitte und Cursor.
        radius:    Pixel, bis in denen Verzoegerung wirkt.
        max_scale: Groesster Faktor direkt unter dem Cursor.

    Returns:
        Faktor >= 1.0 (1.0 = keine Verzoegerung).
    """
    if radius <= 0.0 or max_scale <= 1.0:
        return 1.0
    if distance >= radius:
        return 1.0
    if distance <= 0.0:
        return max_scale

    table = _table_for(max_scale)
    pos = distance / radius * _TABLE_SIZE
    idx = int(pos)
    frac = pos - idx
    a = table[idx]
    b = table[idx + 1] if idx + 1 <= _TABLE_SIZE else table[_TABLE_SIZE]
    return a + (b - a) * frac


def scales_for(centers, cursor_x, radius, max_scale,
               cursor_y=None, icon_y=0.0):
    """Skalierung fuer eine ganze Icon-Reihe auf einmal.

    Args:
        centers:   x-Positionen der Icon-Mittelpunkte.
        cursor_x:  Cursorposition in denselben Koordinaten.
        radius:    Einflussradius in Pixeln.
        max_scale: maximaler Verzoegerungsfaktor.
        cursor_y:  vertikale Cursorposition. Ohne Angabe wird nur der
                   waagerechte Abstand betrachtet.
        icon_y:    vertikale Mitte der Icon-Reihe.

    Returns:
        Liste mit einem Faktor je Icon.

    Der Abstand wird zweidimensional gerechnet, damit ein Icon von jeder
    Seite gleich reagiert. Mit rein waagerechtem Abstand waere ein Icon
    sofort voll vergroessert, sobald der Zeiger die Leiste nur von oben
    oder unten erreicht - der Aufbau faellt dann ersatzlos aus.
    """
    if radius <= 0.0 or max_scale <= 1.0:
        return [1.0] * len(centers)

    table = _table_for(max_scale)
    out = []
    inv_radius = 1.0 / radius
    last = _TABLE_SIZE
    dy2 = 0.0
    if cursor_y is not None:
        dy = cursor_y - icon_y
        dy2 = dy * dy

    for cx in centers:
        dx = cx - cursor_x
        if dy2:
            d = math.sqrt(dx * dx + dy2)
        else:
            d = abs(dx)
        if d >= radius:
            out.append(1.0)
            continue
        pos = d * inv_radius * _TABLE_SIZE
        idx = int(pos)
        frac = pos - idx
        nxt = table[idx + 1] if idx < last else table[last]
        out.append(table[idx] + (nxt - table[idx]) * frac)
    return out