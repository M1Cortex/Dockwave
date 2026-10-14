"""Windows-Anbindung: Icons, Starten, Fenster-Ebene, laufende Programme.

Nutzt nur ctypes, damit keine zusaetzliche Abhaengigkeit noetig ist.
Alles ist defensiv gekapselt: Fehlt etwas, faellt der Aufrufer auf einen
einfacheren Weg zurueck.
"""

import ctypes
import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"

# Endungen, die als "Programm" gelten und per Doppelklick starten.
LAUNCHABLE = (".exe", ".lnk", ".bat", ".cmd", ".com", ".pif")

_user32 = _kernel32 = _shell32 = _ole32 = None
try:  # pragma: no cover - nur auf Windows
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _ole32 = ctypes.WinDLL("ole32", use_last_error=True)
except Exception:  # pragma: no cover
    pass


def available():
    """True, wenn die Windows-Schnittstellen geladen sind."""
    return _user32 is not None


# ----------------------------------------------------------------------
# Pfade
# ----------------------------------------------------------------------

def is_launchable(path):
    return bool(path) and path.lower().endswith(LAUNCHABLE)


def display_name(path):
    """Anzeigename ohne Endung - wie es im Dock steht."""
    name = os.path.basename(str(path).rstrip("/\\"))
    for ext in LAUNCHABLE + (".app",):
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return name


def resolve_shortcut(path):
    """Loest eine .lnk-Verknuepfung zu ihrem Ziel auf.

    Wird fuer das Icon gebraucht: eine Verknuepfung zeigt sonst nur das
    generische Pfeil-Symbol. Scheitert die Aufloesung, bleibt der Pfad
    unveraendert - der Start funktioniert dann trotzdem.
    """
    if not str(path).lower().endswith(".lnk") or _ole32 is None:
        return path
    try:
        return _ishell_path(path) or path
    except Exception:
        return path


class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_ulong),
                ("d2", ctypes.c_ushort),
                ("d3", ctypes.c_ushort),
                ("d4", ctypes.c_byte * 8)]


def _guid(d1, d2, d3, d4):
    """Baut eine GUID - zuverlaessiger als der Konstruktor mit Array."""
    g = _GUID()
    g.d1 = d1
    g.d2 = d2
    g.d3 = d3
    for i in range(8):
        g.d4[i] = d4[i] if i < len(d4) else 0
    return g


_TAIL = (0xC0, 0, 0, 0, 0, 0, 0, 0x46)
_CLSID_SHELL_LINK = _guid(0x00021401, 0, 0, _TAIL)
_IID_SHELL_LINK_W = _guid(0x000214F9, 0, 0, _TAIL)
_IID_PERSIST_FILE = _guid(0x0000010B, 0, 0, _TAIL)

_S_OK = 0x00000000
_S_FALSE = 0x00000001
_RPC_E_CHANGED_MODE = 0x80010106


def _co_init():
    """COM einmalig fuer diesen Thread anmelden.

    Ohne das liefert CoCreateInstance CLASS_E_CLASSNOTAVAIL. Ein bereits
   initialisierter Thread ist kein Fehler - dann einfach durchreichen.
    """
    if _ole32 is None:
        return False
    global _co_ready
    if _co_ready:
        return True
    try:
        # COINIT_APARTMENTTHREADED = 0x2
        hr = _ole32.CoInitializeEx(None, 0x2)
        _co_ready = hr in (_S_OK, _S_FALSE, _RPC_E_CHANGED_MODE)
    except Exception:
        _co_ready = False
    return _co_ready


_co_ready = False


def _vmethod(ptr, index, restype, *argtypes):
    """Holt die index-te Methode aus der vtable eines COM-Objekts."""
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtable[index])


# Rueckruf-Prototyp fuer EnumWindows. Muss beim Aufruf identisch sein.
_ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def _ishell_path(lnk_path):
    """Liest das Ziel einer .lnk ueber IShellLinkW."""
    if not _co_init():
        return None
    ptr = ctypes.c_void_p()
    hr = _ole32.CoCreateInstance(ctypes.byref(_CLSID_SHELL_LINK), None,
                                 1,                      # CLSCTX_INPROC_SERVER
                                 ctypes.byref(_IID_SHELL_LINK_W),
                                 ctypes.byref(ptr))
    if hr != 0 or not ptr:
        return None
    try:
        # GetPath steht in dieser vtable direkt hinter IUnknown (Index 3).
        # Erfahrungswert: GetClassID von IPersist taucht hier nicht auf.
        get_path = _vmethod(ptr, 3, ctypes.c_int,
                            ctypes.c_wchar_p, ctypes.c_int,
                            ctypes.c_void_p, ctypes.c_uint)
        buf = ctypes.create_unicode_buffer(1024)

        # Wichtig: erst laden, dann fragen. Vor dem Load liefert GetPath
        # nichts Brauchbares.
        persist = ctypes.c_void_p()
        # QueryInterface(this, riid, ppv) - _vmethod stellt "this" selbst.
        qi = _vmethod(ptr, 0, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        if qi(ptr, ctypes.byref(_IID_PERSIST_FILE), ctypes.byref(persist)) != 0:
            return None
        try:
            load = _vmethod(persist, 5, ctypes.c_int,
                            ctypes.c_wchar_p, ctypes.c_uint)
            if load(persist, str(lnk_path), 0) != 0:   # STGM_READ
                return None
            # SLGP_RAWPATH = 0x4
            if get_path(ptr, buf, 1024, None, 0x4) != 0:
                return None
            return buf.value or None
        finally:
            # Release(this) - auch hier stellt _vmethod "this" selbst.
            _vmethod(persist, 2, ctypes.c_ulong)(persist)
    finally:
        _vmethod(ptr, 2, ctypes.c_ulong)(ptr)


# ----------------------------------------------------------------------
# Signaturen der Win32-Aufrufe
#
# Ohne die explizit zu setzen nimmt ctypes an, ein Rueckgabewert sei
# 32-Bit. Ein 64-Bit-Handle wird dann abgeschnitten und alle folgenden
# Aufrufe scheitern - daher ist dieser Block nicht optional.
# ----------------------------------------------------------------------

def _declare_signatures():
    if _kernel32 is None or _user32 is None:
        return
    _kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong)]
    _kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int
    _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                       ctypes.c_wchar_p]
    _kernel32.CreateMutexW.restype = ctypes.c_void_p

    _user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    _user32.IsWindowVisible.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    _user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    _user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    _user32.SetWindowPos.restype = ctypes.c_int
    _user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    _user32.FindWindowW.restype = ctypes.c_void_p
    # Der Prototyp muss woertlich derselbe sein wie beim Aufruf, sonst
    # lehnt ctypes den Rueckruf ab.
    _user32.EnumWindows.argtypes = [_ENUMPROC, ctypes.c_long]
    _user32.EnumWindows.restype = ctypes.c_int

    if _ole32 is not None:
        _ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        _ole32.CoInitializeEx.restype = ctypes.c_long
        _ole32.CoCreateInstance.argtypes = [
            ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
        _ole32.CoCreateInstance.restype = ctypes.c_long


_declare_signatures()


# ----------------------------------------------------------------------
# Programm starten
# ----------------------------------------------------------------------

def launch(path):
    """Startet ein Programm per Explorer-Semantik (wie ein Doppelklick)."""
    try:
        os.startfile(str(path))          # noqa: S606 - gewollt
        return True
    except (OSError, AttributeError):
        pass
    try:
        subprocess.Popen([str(path)], cwd=os.path.dirname(str(path)))
        return True
    except OSError:
        return False


def reveal(path):
    """Im Explorer markiert anzeigen."""
    try:
        subprocess.Popen(["explorer", "/select,", str(path)])
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------
# Laufende Programme
# ----------------------------------------------------------------------

_MAX_PATH = 260
_running_cache = (0.0, frozenset())


def app_key(path):
    """Vergleichsschluessel fuer eine Programmdatei.

    Bei einer Verknuepfung zaehlt das Ziel, damit ein Icon auch dann als
    laufend markiert wird, wenn das Programm nicht ueber die .lnk gestartet
    wurde.
    """
    target = resolve_shortcut(path) or path
    return os.path.normcase(os.path.abspath(target))


def running_keys():
    """Pfade aller Programme, die gerade ein sichtbares Fenster haben."""
    global _running_cache
    import time

    now = time.monotonic()
    ts, cached = _running_cache
    if now - ts < 2.0:
        return cached

    found = set()
    if _user32 is not None:
        pids = set()

        @_ENUMPROC
        def callback(hwnd, _lparam):
            if not _user32.IsWindowVisible(hwnd):
                return True
            # Nur echte Fenster mit Titel, keine Tooltips/Menue-Fenster.
            length = _user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            pid = ctypes.c_ulong()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                pids.add(pid.value)
            return True

        try:
            _user32.EnumWindows(callback, 0)
        except Exception:
            pids = set()

        for pid in pids:
            path = _process_path(pid)
            if path:
                found.add(os.path.normcase(os.path.abspath(path)))

    _running_cache = (now, frozenset(found))
    return _running_cache[1]


def is_running(path, keys=None):
    """Laeuft dieses Programm?

    Zuerst wird der volle Pfad verglichen. Stimmt er nicht, hilft der
    Dateiname: Unter Windows 11 ist `C:\\Windows\\notepad.exe` nur ein
    kleiner Starter, der sich in den echten Notepad unter
    `...\\WindowsApps\\...` weiterleitet. Ohne diesen zweiten Blick bliebe
    der Punkt dort leer.
    """
    keys = running_keys() if keys is None else keys
    if not keys:
        return False

    key = app_key(path)
    if key in keys:
        return True

    name = os.path.basename(key).lower()
    if not name:
        return False
    return any(os.path.basename(k).lower() == name for k in keys)


def _process_path(pid):
    """Vollstaendiger Pfad einer Prozess-ID."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        return buf.value
    except Exception:
        return None
    finally:
        _kernel32.CloseHandle(handle)


# ----------------------------------------------------------------------
# Fenster-Ebene
# ----------------------------------------------------------------------

_SW_NOMOVE = 0x0002
_SW_NOSIZE = 0x0001
_SW_NOACTIVATE = 0x0010
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2


def apply_window_level(widget, layer):
    """Setzt die Z-Reihenfolge des Fensters.

    "floating"/"top" -> immer im Vordergrund (wie eine Taskleiste)
    "desktop"        -> knapp ueber dem Desktop, hinter allen Fenstern
    """
    if _user32 is None or widget is None:
        return
    try:
        win = widget.windowHandle()
        if win is None:
            return
        hwnd = ctypes.c_void_p(int(win.winId()))

        if layer in ("floating", "top"):
            _user32.SetWindowPos(hwnd, ctypes.c_void_p(_HWND_TOPMOST),
                                 0, 0, 0, 0,
                                 _SW_NOMOVE | _SW_NOSIZE | _SW_NOACTIVATE)
            return

        # Auf dem Desktop: direkt ueber den Desktop-Fenster einsortieren.
        progman = _user32.FindWindowW("Progman", None)
        if not progman:
            progman = _user32.FindWindowW("WorkerW", None)
        after = progman if progman else ctypes.c_void_p(_HWND_NOTOPMOST)
        _user32.SetWindowPos(hwnd, ctypes.c_void_p(after),
                             0, 0, 0, 0,
                             _SW_NOMOVE | _SW_NOSIZE | _SW_NOACTIVATE)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Dateiauswahl
# ----------------------------------------------------------------------

def open_app_panel(parent=None):
    """Dateiauswahl fuer Programme. Liefert eine Liste von Pfaden."""
    from .qt import QtWidgets

    patterns = "Programme (*.exe *.lnk *.bat *.cmd);;Alle Dateien (*)"
    paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
        parent, "Programme zum Dock hinzufuegen",
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                     "Microsoft", "Windows", "Start Menu", "Programs"),
        patterns)
    return list(paths) if paths else None


# ----------------------------------------------------------------------
# Kategorie fuer den Ordner
# ----------------------------------------------------------------------

CATEGORY_FOLDERS = [
    ("Spiele", ["Steam", "Epic Games", "GOG", "Ubisoft", "Battle.net"]),
    ("Kommunikation", ["Discord", "Slack", "Teams", "Zoom", "Telegram",
                       "WhatsApp", "Signal", "Skype"]),
    ("Medien", ["Spotify", "VLC", "OBS", "iTunes", "Audacity", "Kodi"]),
    ("Entwicklung", ["Visual Studio", "Git", "Docker", "IntelliJ", "PyCharm",
                     "VS Code", "Android Studio", "Node", "Sublime"]),
    ("Büro", ["Word", "Excel", "PowerPoint", "Outlook", "OneNote", "Notion",
              "Obsidian", "LibreOffice"]),
]


def category(path):
    """Grobe Kategorie aus dem Installationsordner erraten."""
    lowered = str(path).lower()
    for name, hints in CATEGORY_FOLDERS:
        if any(h.lower() in lowered for h in hints):
            return name
    for folder in ("program files", "program files (x86)"):
        if folder in lowered:
            return "Programme"
    return "Sonstiges"


def acquire_single_instance():
    """Sorgt dafuer, dass nur eine Kopie laeuft.

    Ein benanntes Mutex reicht: Beim zweiten Start meldet Windows
    bereits, dass es existiert. Die Sperre bleibt bis zum Prozessende
    automatisch bestehen.
    """
    global _instance_mutex
    if _kernel32 is None:
        return True
    if _instance_mutex:
        return True
    try:
        _kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = _kernel32.CreateMutexW(None, False, "Local\\Dockwave")
        if not handle:
            return True
        # ERROR_ALREADY_EXISTS = 183
        already = ctypes.get_last_error() == 183
        _instance_mutex = ctypes.c_void_p(handle)
        return not already
    except Exception:
        return True


_instance_mutex = None


# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------

def default_config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Dockwave")


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ----------------------------------------------------------------------
# Startvorschlaege fuer den allerersten Start
# ----------------------------------------------------------------------

# Dateien, die zwar eine .exe sind, aber kein sinnvolles Dock-Ziel.
_SKIP_WORDS = (
    "unins", "uninstall", "setup", "install", "update", "updater",
    "vcredist", "dotnetfx", "cr_", "dllhost", "conhost", "runtime",
    "rundll32", "regsvr32", "services", "service", "svc", "taskhost",
    "wusa", "onedrive", "backgroundtask", "installer", "repair",
    # Mitgelieferte Windows-Hilfen, die kaum jemand an ein Dock haengt.
    "administrative tools", "magnify", "narrator", "livecaptions",
    "on-screen keyboard", "voiceaccess", "steps recorder", "character map",
    "windows administrative", "windows powershell", "windows terminal",
    # Verknuepfungen auf besondere Ordner statt auf Programme.
    "control panel", "run.lnk",
)

_START_MENU = os.path.join(
    "%APPDATA%", "Microsoft", "Windows", "Start Menu", "Programs")


def is_gui_program(path):
    """Prueft am PE-Header, ob es eine Fensteranwendung ist.

    Sonst landen im Dock Dinge wie Konsolentools oder Dienste, die nie
    ein sichtbares Fenster zeigen.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(0x200)
        if len(head) < 0x60 or head[:2] != b"MZ":
            return False
        offset = int.from_bytes(head[0x3C:0x40], "little")
        if head[offset:offset + 4] != b"PE\x00\x00":
            return False
        optional = offset + 24
        subsystem = int.from_bytes(head[optional + 68:optional + 70], "little")
        return subsystem == 2          # IMAGE_SUBSYSTEM_WINDOWS_GUI
    except (OSError, ValueError, IndexError):
        return False


def _skip(path):
    name = os.path.basename(path).lower()
    return any(word in name for word in _SKIP_WORDS)


def _start_menu_shortcuts(root):
    """Verknuepfungen aus dem Startmenue: erst oben, dann in Unterordnern."""
    def collect(folder, depth):
        out = []
        try:
            entries = sorted(os.listdir(folder))
        except OSError:
            return out
        for name in entries:
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                if depth < 2:
                    out.extend(collect(path, depth + 1))
            elif name.lower().endswith((".lnk", ".exe")) and not _skip(path):
                out.append(path)
        return out

    return collect(root, 0)


def _add(found, seen, path, limit):
    """Nimmt einen Pfad auf, wenn er noch nicht vorkommt."""
    if len(found) >= limit:
        return False
    try:
        key = app_key(path)
    except Exception:
        key = os.path.normcase(path)
    if key in seen:
        return True          # schon dabei, z.B. Startup-Verknuepfung
    seen.add(key)
    found.append(path)
    return True


def sample_apps(limit=10):
    """Staette Programme aus dem Startmenue, danach aus den Program Files."""
    found = []
    seen = set()

    # 1) Das Startmenue des Benutzers - dort stehen genau die Programme,
    #    die er auch wirklich benutzt.
    start_menu = os.path.expandvars(_START_MENU)
    for path in _start_menu_shortcuts(start_menu):
        if not _add(found, seen, path, limit):
            return found

    # 2) Fensteranwendungen aus den Program Files.
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if not base or not os.path.isdir(base):
            continue
        try:
            folders = sorted(os.listdir(base))
        except OSError:
            continue
        for folder in folders:
            full = os.path.join(base, folder)
            if not os.path.isdir(full):
                continue
            try:
                entries = sorted(os.listdir(full))
            except OSError:
                continue
            for name in entries:
                path = os.path.join(full, name)
                if not name.lower().endswith(".exe") or _skip(path):
                    continue
                if not is_gui_program(path):
                    continue
                if not _add(found, seen, path, limit):
                    return found
    return found[:limit]