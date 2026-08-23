#!/usr/bin/env python3
"""Fetch Strava running data and calculate metrics for the half-marathon dashboard.

Ausgabe: data.json

Aufruf:
    python3 tracker.py            # real Strava data (requires creds.json)
    python3 tracker.py --mock     # example data for design/testing
"""

import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import strava_creds

RACE_DATE = date(2026, 10, 4)
# Kept fixed so the dashboard title remains stable regardless of the name
# spelling in Strava.
ATHLETE_NAME = "Réka"
RACE_KM = 21.0975
HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "creds.json")
OUT = os.path.join(HERE, "data.json")

# How far back to fetch activities (training block)
LOOKBACK_WEEKS = 16


# --------------------------------------------------------------------------
# Strava API
# --------------------------------------------------------------------------

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


def access_token():
    """Get a fresh access token and persist Strava's rotated refresh token."""
    if not os.path.exists(CREDS):
        sys.exit(f"No {CREDS} found. Set it up first:\n"
                 f"  python3 auth.py url <client_id>\n"
                 f"Or try it without Strava first:  python3 tracker.py --mock")
    c = strava_creds.load(CREDS)
    tok = _post("https://www.strava.com/api/v3/oauth/token", {
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": c["refresh_token"],
    })
    if tok.get("refresh_token") and tok["refresh_token"] != c["refresh_token"]:
        c["refresh_token"] = tok["refresh_token"]
        strava_creds.save(CREDS, c)
    return tok["access_token"]


def fetch_runs(token, after_dt):
    """Fetch every run after ``after_dt``, with pagination."""
    runs, page = [], 1
    after = int(after_dt.replace(tzinfo=timezone.utc).timestamp())
    while True:
        batch = _get("https://www.strava.com/api/v3/athlete/activities", token,
                     {"after": after, "per_page": 200, "page": page})
        if not batch:
            break
        runs.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        if page > 10:
            break
    out = []
    for a in runs:
        if a.get("type") not in ("Run", "TrailRun") and a.get("sport_type") not in ("Run", "TrailRun"):
            continue
        dist = (a.get("distance") or 0) / 1000.0
        mt = a.get("moving_time") or 0
        if dist < 0.8 or mt < 240:
            continue
        out.append({
            "id": a.get("id"),
            "name": a.get("name") or "Run",
            "date": a["start_date_local"][:10],
            "km": round(dist, 2),
            "seconds": mt,
            "elev": round(a.get("total_elevation_gain") or 0),
            "hr": round(a["average_heartrate"]) if a.get("average_heartrate") else None,
        })
    out.sort(key=lambda r: r["date"])
    return out


# --------------------------------------------------------------------------
# Example data
# --------------------------------------------------------------------------

def mock_runs(today):
    import random
    random.seed(7)
    runs = []
    start = today - timedelta(weeks=LOOKBACK_WEEKS)
    # Gradually rising volume and a gradually improving pace.
    for w in range(LOOKBACK_WEEKS + 1):
        wk_start = start + timedelta(weeks=w)
        if wk_start > today:
            break
        base_pace = 372 - w * 3.1          # sec/km, from 6:12 to ~5:22
        n = 3 if w < 4 else (4 if w < 11 else 4)
        longrun = min(6 + w * 0.95, 19.5)
        dists = [longrun] + [random.uniform(5.5, 8.5) for _ in range(n - 1)]
        for i, d in enumerate(dists):
            day = wk_start + timedelta(days=[6, 1, 3, 4][i % 4])
            if day > today:
                continue
            is_long = i == 0
            is_tempo = i == 2 and w >= 5
            pace = base_pace + (26 if is_long else 0) - (34 if is_tempo else 0)
            pace += random.uniform(-9, 9)
            d = round(d * random.uniform(0.94, 1.06), 2)
            runs.append({
                "id": 1000 + w * 10 + i,
                "name": "Long run" if is_long else ("Tempo run" if is_tempo else "Easy run"),
                "date": day.isoformat(),
                "km": d,
                "seconds": int(d * pace),
                "elev": int(d * random.uniform(4, 14)),
                "hr": int(148 + (8 if is_tempo else 0) - (4 if is_long else 0) + random.uniform(-5, 5)),
            })
    runs.sort(key=lambda r: r["date"])
    return runs


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

def monday(d):
    return d - timedelta(days=d.weekday())


def riegel(dist_km, seconds, target_km=RACE_KM):
    """Riegel formula: T2 = T1 * (D2/D1)^1.06."""
    return seconds * (target_km / dist_km) ** 1.06


def predict(runs, upto, window_weeks=6):
    """Best half-marathon prediction from runs in the last ``window_weeks``."""
    lo = upto - timedelta(weeks=window_weeks)
    pool = [r for r in runs if lo <= date.fromisoformat(r["date"]) <= upto]
    # Runs of at least 8 km are more meaningful; otherwise use 5 km.
    cands = [r for r in pool if r["km"] >= 8] or [r for r in pool if r["km"] >= 5]
    if not cands:
        return None
    best = min(riegel(r["km"], r["seconds"]) for r in cands)
    return int(round(best))


def build_plan(weeks_done, race_week_start, baseline_km, baseline_long):
    """Target curve for the remaining weeks.

    Build up until two weeks before race day (+6% per week), then taper.
    It is derived from the actual current volume rather than a generic plan.
    """
    plan = {}
    # Weeks from the current Monday through race week.
    weeks = []
    w = weeks_done
    while w <= race_week_start:
        weeks.append(w)
        w += timedelta(weeks=1)
    n = len(weeks)
    if n == 0:
        return plan
    # Final blocks: peak, first taper week, race week.
    build_n = max(n - 2, 0)
    peak_km = baseline_km * (1.06 ** max(build_n - 1, 0))
    peak_km = min(peak_km, baseline_km * 1.30)     # avoid overreaching
    peak_long = min(baseline_long + 1.2 * max(build_n - 1, 0), 20.0)

    for i, wk in enumerate(weeks):
        if i < build_n:
            f = 1.06 ** i
            km = min(baseline_km * f, peak_km)
            lng = min(baseline_long + 1.2 * i, peak_long)
        elif i == n - 2:                            # taper week
            km, lng = peak_km * 0.78, min(peak_long * 0.65, 13.0)
        else:                                       # race week including race day
            # The weekly total can never be shorter than its longest run.
            km, lng = max(peak_km * 0.55, RACE_KM), RACE_KM
        plan[wk.isoformat()] = {"km": round(km, 1), "long": round(lng, 1)}
    return plan


def analyse(runs, today):
    race_week = monday(RACE_DATE)
    this_week = monday(today)
    first_week = monday(today - timedelta(weeks=LOOKBACK_WEEKS))

    # --- Weekly aggregation (actual) ---
    by_week = {}
    w = first_week
    while w <= race_week:
        by_week[w.isoformat()] = {"km": 0.0, "long": 0.0, "runs": 0, "seconds": 0}
        w += timedelta(weeks=1)
    for r in runs:
        k = monday(date.fromisoformat(r["date"])).isoformat()
        if k not in by_week:
            continue
        b = by_week[k]
        b["km"] += r["km"]
        b["seconds"] += r["seconds"]
        b["runs"] += 1
        b["long"] = max(b["long"], r["km"])

    # --- Baseline from the last four completed weeks ---
    done = [k for k in sorted(by_week) if date.fromisoformat(k) < this_week and by_week[k]["runs"] > 0]
    recent = done[-4:]
    base_km = sum(by_week[k]["km"] for k in recent) / len(recent) if recent else 25.0
    base_long = max((by_week[k]["long"] for k in recent), default=10.0)

    plan = build_plan(this_week, race_week, base_km, base_long)

    weeks = []
    for k in sorted(by_week):
        d = date.fromisoformat(k)
        b = by_week[k]
        p = plan.get(k)
        weeks.append({
            "week": k,
            "label": d.strftime("%d.%m."),
            "km": round(b["km"], 1),
            "long": round(b["long"], 1),
            "runs": b["runs"],
            "avg_pace": int(b["seconds"] / b["km"]) if b["km"] > 0.5 else None,
            "plan_km": p["km"] if p else None,
            "plan_long": p["long"] if p else None,
            "future": d > this_week,
            "current": d == this_week,
        })

    # --- Prediction trend (shows improvement) ---
    forecast = []
    k = first_week + timedelta(weeks=3)
    while k <= this_week:
        p = predict(runs, min(k + timedelta(days=6), today))
        if p:
            forecast.append({"week": k.isoformat(), "label": k.strftime("%d.%m."), "seconds": p})
        k += timedelta(weeks=1)

    now_pred = predict(runs, today)
    then_pred = predict(runs, today - timedelta(weeks=4))

    # --- Categorised pace per run ---
    pace_points = []
    for r in runs:
        d = date.fromisoformat(r["date"])
        if d < first_week:
            continue
        cat = "long" if r["km"] >= max(base_long * 0.75, 12) else ("tempo" if r["seconds"] / r["km"] < 320 else "easy")
        pace_points.append({
            "date": r["date"], "km": r["km"], "pace": round(r["seconds"] / r["km"]),
            "cat": cat, "name": r["name"], "seconds": r["seconds"], "hr": r["hr"],
        })

    # --- Metrics ---
    last4 = [w for w in weeks if not w["future"] and not w["current"]][-4:]
    prev4 = [w for w in weeks if not w["future"] and not w["current"]][-8:-4]
    km4 = sum(w["km"] for w in last4) / max(len(last4), 1)
    km4p = sum(w["km"] for w in prev4) / max(len(prev4), 1)

    easy = [p for p in pace_points if p["cat"] == "easy"]
    def avg_pace(pts):
        return int(sum(p["pace"] for p in pts) / len(pts)) if pts else None
    cut = (today - timedelta(weeks=4)).isoformat()
    cut8 = (today - timedelta(weeks=8)).isoformat()
    pace_now = avg_pace([p for p in easy if p["date"] >= cut])
    pace_then = avg_pace([p for p in easy if cut8 <= p["date"] < cut])

    longest = max((r["km"] for r in runs), default=0)
    longest_recent = max((p["km"] for p in pace_points if p["date"] >= cut), default=0)
    longest_prev = max((p["km"] for p in pace_points if cut8 <= p["date"] < cut), default=0)

    days_left = (RACE_DATE - today).days
    block_start = first_week
    progress = 1 - days_left / max((RACE_DATE - block_start).days, 1)

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "race_date": RACE_DATE.isoformat(),
        "days_left": days_left,
        "weeks_left": round(days_left / 7, 1),
        "block_progress": round(min(max(progress, 0), 1), 3),
        "weeks": weeks,
        "forecast": forecast,
        "pace_points": pace_points,
        "recent_runs": list(reversed(runs[-8:])),
        "totals": {
            "runs": len([r for r in runs if date.fromisoformat(r["date"]) >= first_week]),
            "km": round(sum(r["km"] for r in runs if date.fromisoformat(r["date"]) >= first_week), 1),
        },
        "kpi": {
            "weekly_km": round(km4, 1),
            "weekly_km_prev": round(km4p, 1),
            "longest": round(longest, 1),
            "longest_recent": round(longest_recent, 1),
            "longest_prev": round(longest_prev, 1),
            "easy_pace": pace_now,
            "easy_pace_prev": pace_then,
            "prediction": now_pred,
            "prediction_prev": then_pred,
        },
        "plan_basis": {"baseline_km": round(base_km, 1), "baseline_long": round(base_long, 1)},
    }


def main():
    today = date.today()
    if "--mock" in sys.argv:
        runs = mock_runs(today)
        athlete = {"name": ATHLETE_NAME, "photo": None}
    else:
        tok = access_token()
        prof = _get("https://www.strava.com/api/v3/athlete", tok)
        athlete = {"name": ATHLETE_NAME, "photo": prof.get("profile_medium")}
        runs = fetch_runs(tok, datetime.combine(today - timedelta(weeks=LOOKBACK_WEEKS + 1), datetime.min.time()))

    if not runs:
        print("WARNING: no runs found.")
        print("  The most common cause is missing activity:read_all permission,")
        print("  which leaves private activities unavailable. Check with:")
        print("    python3 auth.py check")

    data = analyse(runs, today)
    data["athlete"] = athlete
    data["mock"] = "--mock" in sys.argv
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    print(f"{len(runs)} runs -> {OUT}")
    k = data["kpi"]
    print(f"  Weekly km (4-week average): {k['weekly_km']}  longest run: {k['longest']}")
    if k["prediction"]:
        p = k["prediction"]
        print(f"  Prediction: {p//3600}:{p%3600//60:02d}:{p%60:02d}")


if __name__ == "__main__":
    main()
