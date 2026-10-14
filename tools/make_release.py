r"""Release auf GitHub anlegen oder ergaenzen.

Aufruf:
    python tools\make_release.py v1.0.0 --notes RELEASE_NOTES.md --exe dist\Dockwave.exe

Nutzt die Zugangsdaten, die Git Credential Manager nach dem Push gespeichert
hat. Es werden keine Geheimnisse auf der Platte abgelegt und keine
ausgegeben. Ein wiederholter Lauf ergaenzt ein bestehendes Release, statt
ein zweites anzulegen.
"""

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("DOCKWAVE_REPO", "M1Cortex/Dockwave")
API = "https://api.github.com"


def token():
    """Liest das gespeicherte GitHub-Token aus dem Credential Store."""
    anfrage = "protocol=https\nhost=github.com\n\n"
    res = subprocess.run(["git", "credential", "fill"], input=anfrage,
                         capture_output=True, text=True, timeout=60)
    for zeile in res.stdout.splitlines():
        if zeile.startswith("password="):
            return zeile[9:]
    raise SystemExit("Kein gespeichertes GitHub-Token gefunden. "
                     "Bitte einmal `git push` ausfuehren.")


def api(pfad, daten=None, datei=None, methode="GET", auth=True):
    """Ein API-Aufruf mit sauberer UTF-8-Kodierung."""
    kopf = {"Accept": "application/vnd.github+json",
            "User-Agent": "Dockwave"}
    if auth:
        kopf["Authorization"] = "Bearer " + token()

    koerper = None
    if datei is not None:
        name, inhalt = datei
        typ = mimetypes.guess_type(name)[0] or "application/octet-stream"
        kopf["Content-Type"] = typ
        koerper = inhalt
    elif daten is not None:
        kopf["Content-Type"] = "application/json; charset=utf-8"
        koerper = json.dumps(daten, ensure_ascii=False).encode("utf-8")

    anfrage = urllib.request.Request(API + pfad, data=koerper,
                                     headers=kopf, method=methode)
    try:
        with urllib.request.urlopen(anfrage, timeout=120) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode("utf-8", "replace")
        raise SystemExit("GitHub antwortete mit %d:\n%s"
                         % (fehler.code, text[:800]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tag")
    p.add_argument("--notes", required=True)
    p.add_argument("--name")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--prerelease", action="store_true")
    p.add_argument("--exe", action="append", default=[])
    args = p.parse_args()

    with open(args.notes, "r", encoding="utf-8") as fh:
        notizen = fh.read()

    # Existiert das Release schon? Dann nur ergaenzen, nicht duplizieren.
    vorhanden = None
    for r in api("/repos/%s/releases" % REPO):
        if r["tag_name"] == args.tag:
            vorhanden = r
            break

    daten = {
        "tag_name": args.tag,
        "target_commitish": "main",
        "name": args.name or ("Dockwave %s" % args.tag.lstrip("v")),
        "body": notizen,
        "draft": args.draft,
        "prerelease": args.prerelease,
    }

    if vorhanden:
        release = api("/repos/%s/releases/%d" % (REPO, vorhanden["id"]),
                      daten=daten, methode="PATCH")
        print("Release aktualisiert: %s" % release["html_url"])
    else:
        release = api("/repos/%s/releases" % REPO, daten=daten, methode="POST")
        print("Release angelegt: %s" % release["html_url"])

    # Dateien anhaengen
    for pfad in args.exe:
        if not os.path.exists(pfad):
            print("  fehlt: %s" % pfad)
            continue
        name = os.path.basename(pfad)
        bereits = {a["name"] for a in release.get("assets", [])}
        if name in bereits:
            print("  %s liegt bereits vor - uebersprungen" % name)
            continue
        with open(pfad, "rb") as fh:
            inhalt = fh.read()
        url = "https://uploads.github.com/repos/%s/releases/%d/assets?name=%s" % (
            REPO, release["id"], name)
        ergebnis = api_url(url, name, inhalt)
        print("  hochgeladen: %s (%.1f MB) -> %s"
              % (name, len(inhalt) / 1048576.0,
                 ergebnis.get("browser_download_url")))

    final = api("/repos/%s/releases/tags/%s" % (REPO, args.tag))
    print("\nZusammenfassung:")
    print("  URL:    %s" % final["html_url"])
    print("  Tag:    %s" % final["tag_name"])
    print("  Entwurf: %s   Vorab: %s" % (final["draft"], final["prerelease"]))
    for a in final["assets"]:
        print("  Datei:  %s (%.1f MB, %d Downloads)"
              % (a["name"], a["size"] / 1048576.0, a["download_count"]))
    return 0


def api_url(url, name, inhalt):
    anfrage = urllib.request.Request(
        url, data=inhalt,
        headers={"Authorization": "Bearer " + token(),
                 "User-Agent": "Dockwave",
                 "Content-Type": "application/octet-stream"},
        method="POST")
    try:
        with urllib.request.urlopen(anfrage, timeout=600) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode("utf-8", "replace")
        raise SystemExit("Upload fehlgeschlagen (%d):\n%s"
                         % (fehler.code, text[:800]))


if __name__ == "__main__":
    sys.exit(main())