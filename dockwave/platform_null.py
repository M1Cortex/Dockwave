"""Rueckfall fuer Plattformen, die weder macOS noch Windows sind.

Damit das Projekt ueberall importierbar bleibt und der Benutzer zumindest
eine verstaendliche Meldung bekommt.
"""

import os

LAUNCHABLE = (".desktop",)
EXTRA_STARTERS = []


def available():
    return False


def is_launchable(path):
    return str(path).lower().endswith(LAUNCHABLE)


def display_name(path):
    return os.path.basename(str(path))


def launch(path):
    import subprocess

    try:
        subprocess.Popen(["xdg-open", str(path)],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def reveal(path):
    return False


def running_keys():
    return frozenset()


def is_running(path, keys=None):
    return False


def app_key(path):
    return os.path.normcase(os.path.abspath(str(path)))


def category(path):
    return "Sonstiges"


def apply_window_level(widget, layer):
    return None


def open_app_panel(parent=None):
    return None


def default_config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "Dockwave")


def acquire_single_instance():
    return True


def sample_apps():
    return []