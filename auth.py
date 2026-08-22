#!/usr/bin/env python3
"""Einmalige Strava-Autorisierung fuer das Halbmarathon-Dashboard.

    python3 auth.py url    <client_id>
        -> Autorisierungs-Links zum Weiterschicken (Web / Android / iPhone)

    python3 auth.py token  <client_id> <client_secret> <code>
        -> tauscht den Code gegen einen Refresh-Token und schreibt creds.json

    python3 auth.py check
        -> prueft, ob der gespeicherte Zugang funktioniert und Laeufe liefert
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import strava_creds

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "creds.json")

# activity:read_all ist noetig, sonst liefert die API fuer alle nicht-oeffentlichen
# Laeufe stillschweigend eine leere Liste - der klassische "geht nicht"-Fehler.
SCOPE = "activity:read_all"
REDIRECT = "http://localhost"


def _post(url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _get(url, token, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def cmd_url(client_id):
    q = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": SCOPE,
    })
    print("\nBrowser (normal eingeloggt):")
    print(f"  https://www.strava.com/oauth/authorize?{q}")
    print("\nAndroid (oeffnet die Strava-App):")
    print(f"  https://www.strava.com/oauth/mobile/authorize?{q}")
    print("\niPhone (nur in Safari oeffnen, nicht aus WhatsApp o.ae.):")
    print(f"  strava://oauth/mobile/authorize?{q}")
    print("\nNach 'Autorisieren' schlaegt die Weiterleitung auf localhost fehl.")
    print("Das ist richtig so - die komplette URL aus der Adressleiste kopieren,")
    print("darin steht code=... . Der Code verfaellt schnell, also zuegig eintauschen.\n")


def cmd_token(client_id, client_secret, code):
    # Falls jemand die ganze URL statt nur des Codes einwirft: Code herausziehen.
    if "code=" in code:
        parsed = urllib.parse.urlparse(code)
        code = urllib.parse.parse_qs(parsed.query).get("code", [code])[0]

    try:
        tok = _post("https://www.strava.com/api/v3/oauth/token", {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"Fehlgeschlagen ({e.code}): {body}\n"
                 f"Meist ist der Code abgelaufen oder schon benutzt - neuen Link oeffnen.")

    granted = tok.get("scope") or ""
    strava_creds.save(CREDS, {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tok["refresh_token"],
    })
    print(f"creds.json geschrieben -> {CREDS}")
    athlete = tok.get("athlete") or {}
    if athlete:
        print(f"Konto: {athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip())
    if "activity:read_all" not in granted:
        print(f"\nACHTUNG: erteilte Rechte = '{granted}'.")
        print("Ohne activity:read_all bleiben private Laeufe unsichtbar.")
        print("Beim Autorisieren muss das Haekchen fuer alle Aktivitaeten gesetzt sein.")
    else:
        print("Rechte in Ordnung (activity:read_all).")
    print("\nJetzt pruefen mit:  python3 auth.py check")


def cmd_check():
    if not os.path.exists(CREDS):
        sys.exit("Keine creds.json - zuerst 'auth.py url' und 'auth.py token' ausfuehren.")
    c = strava_creds.load(CREDS)
    try:
        tok = _post("https://www.strava.com/api/v3/oauth/token", {
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": c["refresh_token"],
        })
    except urllib.error.HTTPError as e:
        sys.exit(f"Token-Refresh fehlgeschlagen ({e.code}): {e.read().decode(errors='replace')}\n"
                 f"Refresh-Token vermutlich ungueltig - neu autorisieren.")

    if tok.get("refresh_token") and tok["refresh_token"] != c["refresh_token"]:
        c["refresh_token"] = tok["refresh_token"]
        strava_creds.save(CREDS, c)
        print("Refresh-Token wurde rotiert und gespeichert.")

    acts = _get("https://www.strava.com/api/v3/athlete/activities",
                tok["access_token"], {"per_page": 5})
    print(f"Zugang funktioniert. {len(acts)} Aktivitaeten in der Stichprobe.")
    for a in acts[:5]:
        print(f"  {a['start_date_local'][:10]}  {a.get('distance', 0) / 1000:5.1f} km  "
              f"{a.get('sport_type') or a.get('type')}  {a.get('name', '')[:40]}")
    if not acts:
        print("Leere Liste. Entweder gibt es keine Aktivitaeten, oder activity:read_all fehlt.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "url":
        cmd_url(a[1])
    elif len(a) == 4 and a[0] == "token":
        cmd_token(a[1], a[2], a[3])
    elif len(a) == 1 and a[0] == "check":
        cmd_check()
    else:
        sys.exit(__doc__)
