"""Benchmark: kostet ein Frame der Vergroesserung wirklich unter 16 ms?

Aufruf:  python3 tools/bench.py
"""

import os
import statistics
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dockwave.config import APP, SEPARATOR, STACK, Config   # noqa: E402
from dockwave.dock_window import DockWindow                 # noqa: E402
from dockwave.qt import QtGui, QtWidgets                    # noqa: E402


def build(count):
    entries = []
    for i in range(count):
        if i and i % 6 == 0:
            entries.append({"type": SEPARATOR})
        entries.append({"type": APP, "path": "/Applications/App%02d.app" % i})
    entries.append({"type": STACK})
    return Config({"entries": entries, "size": 46})


def run(count, frames=1500):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    cfg = build(count)
    dock = DockWindow(cfg)
    dock.resize(dock.width(), dock.height())
    dock.show()

    dock._layout(-1.0e9)
    start_x = dock._bounds[0].center().x()
    end_x = dock._bounds[-1].center().x()

    target = QtGui.QPixmap(dock.size())
    target.fill(0)

    # Aufwaermen, damit Icon-Caches und Panel-Pixmap warm sind.
    for i in range(100):
        dock._cursor_x = start_x + (end_x - start_x) * i / 100.0
        dock._layout(dock._cursor_x)
        dock._update_mask()
        dock.render(target)

    layout_ms = []
    paint_ms = []
    mask_calls = 0
    for i in range(frames):
        x = start_x + (end_x - start_x) * (i % 200) / 199.0
        dock._cursor_x = x

        t0 = time.perf_counter()
        dock._layout(x)
        dock._update_mask()
        t1 = time.perf_counter()
        dock.render(target)
        t2 = time.perf_counter()

        layout_ms.append((t1 - t0) * 1000.0)
        paint_ms.append((t2 - t1) * 1000.0)

    total = [a + b for a, b in zip(layout_ms, paint_ms)]
    dock.close()

    def fmt(name, values):
        return ("  %-18s Mittel %6.3f ms   95%%-Wert %6.3f ms   max %6.3f ms"
                % (name, statistics.mean(values),
                   sorted(values)[int(len(values) * 0.95)], max(values)))

    print("\n%d Icons, %d Frames" % (count, frames))
    print(fmt("Layout", layout_ms))
    print(fmt("Zeichnen", paint_ms))
    print(fmt("Summe", total))
    budget = 1000.0 / 60.0
    worst = sorted(total)[int(len(total) * 0.99)]
    print("  Budget bei 60 fps: %.2f ms/Frame" % budget)
    print("  99%%-Quantil %.3f ms -> %.0f%% des Budgets" % (worst, worst / budget * 100))
    _ = app, mask_calls
    return worst < budget


def main():
    ok = True
    for count in (5, 12, 24):
        ok &= run(count)
    print("\n%s" % ("Ergebnis: Budget eingehalten." if ok else "Ergebnis: zu langsam!"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())