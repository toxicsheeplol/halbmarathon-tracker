#!/usr/bin/env python3
"""One-time Strava authorisation for the half-marathon dashboard.

    python3 auth.py url    <client_id>
        -> print authorisation links (web / Android / iPhone)

    python3 auth.py token  <client_id> <client_secret> <code>
        -> exchange the code for a refresh token and write creds.json

    python3 auth.py check
        -> check the saved connection and list sample activities
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

# activity:read_all is required; otherwise the API silently omits non-public
# runs and returns an empty list.
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
    print("\nBrowser (signed in normally):")
    print(f"  https://www.strava.com/oauth/authorize?{q}")
    print("\nAndroid (opens the Strava app):")
    print(f"  https://www.strava.com/oauth/mobile/authorize?{q}")
    print("\niPhone (open in Safari only, not from WhatsApp or a similar app):")
    print(f"  strava://oauth/mobile/authorize?{q}")
    print("\nAfter authorising, the redirect to localhost will fail.")
    print("That is expected — copy the complete URL from the address bar;")
    print("it contains code=... . The code expires quickly, so exchange it promptly.\n")


def cmd_token(client_id, client_secret, code):
    # Extract the code if a complete redirect URL was supplied.
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
        sys.exit(f"Failed ({e.code}): {body}\n"
                 f"The code is usually expired or already used — open a new link.")

    granted = tok.get("scope") or ""
    strava_creds.save(CREDS, {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tok["refresh_token"],
    })
    print(f"Wrote creds.json -> {CREDS}")
    athlete = tok.get("athlete") or {}
    if athlete:
        print(f"Account: {athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip())
    if "activity:read_all" not in granted:
        print(f"\nWARNING: granted permissions = '{granted}'.")
        print("Private runs remain unavailable without activity:read_all.")
        print("Select access to all activities while authorising.")
    else:
        print("Permissions look good (activity:read_all).")
    print("\nNow check with:  python3 auth.py check")


def cmd_check():
    if not os.path.exists(CREDS):
        sys.exit("No creds.json — run 'auth.py url' and 'auth.py token' first.")
    c = strava_creds.load(CREDS)
    try:
        tok = _post("https://www.strava.com/api/v3/oauth/token", {
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": c["refresh_token"],
        })
    except urllib.error.HTTPError as e:
        sys.exit(f"Token refresh failed ({e.code}): {e.read().decode(errors='replace')}\n"
                 f"The refresh token is likely invalid — authorise again.")

    if tok.get("refresh_token") and tok["refresh_token"] != c["refresh_token"]:
        c["refresh_token"] = tok["refresh_token"]
        strava_creds.save(CREDS, c)
        print("Refresh token rotated and saved.")

    acts = _get("https://www.strava.com/api/v3/athlete/activities",
                tok["access_token"], {"per_page": 5})
    print(f"Connection works. {len(acts)} sample activities returned.")
    for a in acts[:5]:
        print(f"  {a['start_date_local'][:10]}  {a.get('distance', 0) / 1000:5.1f} km  "
              f"{a.get('sport_type') or a.get('type')}  {a.get('name', '')[:40]}")
    if not acts:
        print("Empty list. There are no activities, or activity:read_all is missing.")


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
