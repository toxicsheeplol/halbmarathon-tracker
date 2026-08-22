#!/usr/bin/env python3
"""Render data.json to index.html for the published website."""

import html
import json
import math
import os
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "index.html")

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------- Formatierung ----------

def mmss(sec):
    if sec is None:
        return "–"
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def hhmmss(sec):
    if sec is None:
        return "–"
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def de(d):
    d = date.fromisoformat(d)
    return f"{MONTHS[d.month - 1]} {d.day}"


def num(x, dec=1):
    return f"{x:.{dec}f}"


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- Bausteine ----------

def delta_chip(now, prev, words, lower_is_better=False, fmt=lambda v: num(v), unit=""):
    """Change chip with icon and wording; colour never carries meaning alone."""
    if now is None or prev is None or prev == 0:
        return '<span class="chip chip-flat"><span class="chip-ico">–</span>first value</span>'
    d = now - prev
    better = (d < 0) if lower_is_better else (d > 0)
    if abs(d) < (0.05 if not lower_is_better else 0.5):
        return '<span class="chip chip-flat"><span class="chip-ico">→</span>unchanged</span>'
    cls = "chip-up" if better else "chip-down"
    ico = "▲" if d > 0 else "▼"
    return (f'<span class="chip {cls}"><span class="chip-ico">{ico}</span>'
            f'{fmt(abs(d))}{unit} {words[0] if d > 0 else words[1]}</span>')


def tile(label, value, unit, sub, chip=""):
    return f"""      <div class="tile">
        <div class="tile-label">{label}</div>
        <div class="tile-value">{value}<span class="tile-unit">{unit}</span></div>
        <div class="tile-sub">{sub}</div>
        {chip}
      </div>"""


def axis_y(ticks, fmt):
    return "".join(
        f'<div class="ygrid" style="bottom:{p:.4f}%"><span class="ytick">{fmt(v)}</span></div>'
        for v, p in ticks)


def nice_ticks(vmax, count=5):
    """Readable integer axis steps that end just above the maximum."""
    if vmax <= 0:
        return [0], 1
    best = None
    for c in (4, 5, 6):
        raw = vmax / c
        mag = 10 ** math.floor(math.log10(raw))
        step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-9)
        n = math.ceil(vmax / step - 1e-9)
        top = step * n
        if best is None or top < best[1] - 1e-9:
            best = ([step * i for i in range(n + 1)], top)
    return best


def time_ticks(lo, hi, y):
    """Axis steps for time values (seconds), with about four grid lines."""
    span = hi - lo
    step = next((s for s in (60, 120, 300, 600, 900, 1800, 3600) if span / s <= 5), 3600)
    out, v = [], int(lo / step + 1) * step
    while v < hi:
        out.append((v, y(v)))
        v += step
    return out


def tick_every(n, want=5):
    """Choose an x-axis label frequency that prevents collisions."""
    return max(1, -(-n // want))


def keep_tick(i, n, want=5):
    step = tick_every(n, want)
    return i % step == (n - 1) % step


# ---------- Charts ----------

def chart_weekly(weeks):
    """Weekly distance: bars = completed, line = target."""
    ws = weeks[-13:]
    vmax = max([w["km"] for w in ws] + [w["plan_km"] or 0 for w in ws] + [1])
    ticks, top = nice_ticks(vmax)
    n = len(ws)

    bars, hits, pts = [], [], []
    for i, w in enumerate(ws):
        left = (i + 0.5) / n * 100
        h = w["km"] / top * 100
        cls = "bar"
        if w["current"]:
            cls += " bar-now"
        if w["future"]:
            cls += " bar-future"
        if w["km"] > 0:
            bars.append(f'<div class="{cls}" style="left:{left:.4f}%;height:{h:.4f}%"></div>')
        if w["plan_km"]:
            pts.append((i, w["plan_km"]))
        # Full-height tooltip target for each column.
        soll = f" · Target {num(w['plan_km'])} km" if w["plan_km"] else ""
        note = " · in progress" if w["current"] else ""
        hits.append(
            f'<div class="hit" style="left:{i / n * 100:.4f}%;width:{100 / n:.4f}%" '
            f'data-tip="Week of {esc(w["label"])}&#10;{num(w["km"])} km · {w["runs"]} runs{soll}{note}"></div>')

    line = ""
    if len(pts) > 1:
        d = " ".join(f"{(i + 0.5) / n * 100:.4f},{100 - v / top * 100:.4f}" for i, v in pts)
        line = (f'<svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
                f'<polyline class="planline" points="{d}" vector-effect="non-scaling-stroke"/></svg>')
    dots = "".join(
        f'<div class="pdot" style="left:{(i + 0.5) / n * 100:.4f}%;bottom:{v / top * 100:.4f}%"></div>'
        for i, v in pts)

    xlab = "".join(
        f'<div class="xtick{" xtick-now" if w["current"] else ""}" '
        f'style="left:{(i + 0.5) / n * 100:.4f}%">{esc(w["label"])}</div>'
        for i, w in enumerate(ws) if keep_tick(i, n, 6))

    return f"""    <figure class="card chart">
      <figcaption>
        <h2>Weekly distance</h2>
        <p>What she ran compared with the target curve through race day.</p>
      </figcaption>
      <div class="legend">
        <span class="lg"><i class="sw sw-ist"></i>completed</span>
        <span class="lg"><i class="sw sw-soll"></i>target</span>
      </div>
      <div class="plot" style="--plot-h:210px">
        <div class="grid">{axis_y(ticks_pct(ticks, top), lambda v: num(v, 0))}</div>
        <div class="marks">{''.join(bars)}{line}{dots}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{xlab}</div>
      <div class="unit-note">Kilometres per week</div>
    </figure>"""


def ticks_pct(ticks, top):
    return [(v, v / top * 100) for v in ticks]


def chart_longrun(weeks, race_km=21.0975):
    ws = [w for w in weeks[-13:]]
    vmax = max([w["long"] for w in ws] + [w["plan_long"] or 0 for w in ws] + [race_km])
    ticks, top = nice_ticks(vmax)
    n = len(ws)
    bars, hits = [], []
    for i, w in enumerate(ws):
        left = (i + 0.5) / n * 100
        if w["long"] > 0:
            cls = "bar" + (" bar-now" if w["current"] else "")
            bars.append(f'<div class="{cls}" style="left:{left:.4f}%;height:{w["long"] / top * 100:.4f}%"></div>')
        elif w["plan_long"]:
            bars.append(f'<div class="bar bar-plan" style="left:{left:.4f}%;'
                        f'height:{w["plan_long"] / top * 100:.4f}%"></div>')
        v = w["long"] if w["long"] > 0 else (w["plan_long"] or 0)
        kind = "completed" if w["long"] > 0 else "planned"
        hits.append(f'<div class="hit" style="left:{i / n * 100:.4f}%;width:{100 / n:.4f}%" '
                    f'data-tip="Week of {esc(w["label"])}&#10;longest run: {num(v)} km ({kind})"></div>')
    ref = (f'<div class="refline" style="bottom:{race_km / top * 100:.4f}%">'
           f'<span>Race distance 21.1</span></div>')
    xlab = "".join(
        f'<div class="xtick{" xtick-now" if w["current"] else ""}" style="left:{(i + 0.5) / n * 100:.4f}%">{esc(w["label"])}</div>'
        for i, w in enumerate(ws) if keep_tick(i, n, 4))
    return f"""    <figure class="card chart">
      <figcaption>
        <h2>Longest run per week</h2>
        <p>The key half-marathon indicator. Outlined bars are still planned.</p>
      </figcaption>
      <div class="legend">
        <span class="lg"><i class="sw sw-ist"></i>completed</span>
        <span class="lg"><i class="sw sw-plan"></i>planned</span>
      </div>
      <div class="plot" style="--plot-h:180px">
        <div class="grid">{axis_y(ticks_pct(ticks, top), lambda v: num(v, 0))}</div>
        <div class="marks">{''.join(bars)}{ref}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{xlab}</div>
      <div class="unit-note">Kilometres</div>
    </figure>"""


def chart_pace(points):
    """Pace per run plus a four-week trend. Faster times sit higher."""
    pts = [p for p in points]
    if len(pts) < 3:
        return ""
    d0 = date.fromisoformat(pts[0]["date"])
    d1 = date.fromisoformat(pts[-1]["date"])
    span = max((d1 - d0).days, 1)
    paces = [p["pace"] for p in pts]
    lo, hi = min(paces), max(paces)
    pad = max((hi - lo) * 0.15, 8)
    lo, hi = lo - pad, hi + pad

    def y(pace):                       # inverted: faster = higher
        return (hi - pace) / (hi - lo) * 100

    def x(ds):
        return (date.fromisoformat(ds) - d0).days / span * 100

    dots, hits = [], []
    for p in pts:
        sz = 7 + min(p["km"], 22) * 0.42
        dots.append(f'<div class="rdot" style="left:{x(p["date"]):.4f}%;bottom:{y(p["pace"]):.4f}%;'
                    f'--d:{sz:.1f}px"></div>')
        dt = date.fromisoformat(p["date"])
        hr = f' · {p["hr"]} bpm' if p.get("hr") else ""
        hits.append(f'<div class="hit hit-dot" style="left:{x(p["date"]):.4f}%;bottom:{y(p["pace"]):.4f}%" '
                    f'data-tip="{DAYS[dt.weekday()][:2]}, {dt.day}.{dt.month}. · {esc(p["name"])}&#10;'
                    f'{num(p["km"])} km in {hhmmss(p["seconds"])} · {mmss(p["pace"])}/km{hr}"></div>')

    # Moving 21-day average as the trend line.
    trend = []
    for p in pts:
        c = date.fromisoformat(p["date"])
        win = [q["pace"] for q in pts if 0 <= (c - date.fromisoformat(q["date"])).days <= 21]
        if len(win) >= 2:
            trend.append((x(p["date"]), y(sum(win) / len(win))))
    tl = ""
    if len(trend) > 1:
        tl = ('<svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
              '<polyline class="trendline" points="'
              + " ".join(f"{a:.4f},{100 - b:.4f}" for a, b in trend)
              + '" vector-effect="non-scaling-stroke"/></svg>')

    tick_vals = time_ticks(lo, hi, y)

    # Month labels.
    xlab, seen = [], set()
    for p in pts:
        dt = date.fromisoformat(p["date"])
        k = (dt.year, dt.month)
        if k in seen:
            continue
        seen.add(k)
        xlab.append(f'<div class="xtick" style="left:{x(p["date"]):.4f}%">{MONTHS[dt.month - 1][:3]}</div>')

    return f"""    <figure class="card chart">
      <figcaption>
        <h2>Pace per run</h2>
        <p>One point per run; point size represents distance. Higher is faster; the line is the three-week average.</p>
      </figcaption>
      <div class="plot" style="--plot-h:180px">
        <div class="grid">{axis_y(tick_vals, mmss)}</div>
        <div class="marks">{''.join(dots)}{tl}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{''.join(xlab)}</div>
      <div class="unit-note">Minutes per kilometre</div>
    </figure>"""


def chart_forecast(fc):
    if len(fc) < 3:
        return ""
    vals = [f["seconds"] for f in fc]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.2, 60)
    lo, hi = lo - pad, hi + pad
    n = len(fc)

    def y(v):
        return (hi - v) / (hi - lo) * 100

    tick_vals = time_ticks(lo, hi, y)

    pl = " ".join(f"{i / (n - 1) * 100:.4f},{100 - y(f['seconds']):.4f}" for i, f in enumerate(fc))
    hits = "".join(
        f'<div class="hit" style="left:{i / n * 100:.4f}%;width:{100 / n:.4f}%" '
        f'data-tip="As of {esc(f["label"])}&#10;Prediction {hhmmss(f["seconds"])}"></div>'
        for i, f in enumerate(fc))
    end = (f'<div class="enddot" style="left:100%;bottom:{y(fc[-1]["seconds"]):.4f}%"></div>'
           f'<div class="endlabel" style="bottom:{y(fc[-1]["seconds"]):.4f}%">{hhmmss(fc[-1]["seconds"])}</div>')
    return f"""      <div class="plot" style="--plot-h:130px">
        <div class="grid">{axis_y(tick_vals, lambda v: hhmmss(v)[:4])}</div>
        <div class="marks">
          <svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <polyline class="fcline" points="{pl}" vector-effect="non-scaling-stroke"/>
          </svg>{end}{hits}
        </div>
      </div>
      <div class="xaxis xaxis-spark"><span>{esc(fc[0]["label"])}</span><span>today</span></div>
      <div class="unit-note">Predicted finish time, hours:minutes</div>"""


def table_view(weeks):
    rows = []
    for w in weeks:
        if w["runs"] == 0 and not w["plan_km"]:
            continue
        state = "in progress" if w["current"] else ("planned" if w["future"] else "")
        rows.append(f"<tr><th scope=\"row\">{esc(w['label'])}</th>"
                    f"<td>{num(w['km']) if w['runs'] else '–'}</td>"
                    f"<td>{num(w['plan_km']) if w['plan_km'] else '–'}</td>"
                    f"<td>{num(w['long']) if w['long'] else '–'}</td>"
                    f"<td>{w['runs'] or '–'}</td>"
                    f"<td>{mmss(w['avg_pace'])}</td><td>{state}</td></tr>")
    return f"""    <details class="card tablewrap">
      <summary>All weeks as a table</summary>
      <div class="scroll">
        <table>
          <thead><tr><th scope="col">Week of</th><th scope="col">km</th><th scope="col">Target km</th>
          <th scope="col">longest</th><th scope="col">runs</th><th scope="col">avg. pace</th><th scope="col"></th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </details>"""


def weekly_plan(d):
    """Suggested day-by-day plan for the current week.

    The rendered page stores edits locally in the visitor's browser.  Keeping
    the defaults in the generated HTML means a newly published target curve
    provides a fresh suggestion without exposing any credentials or needing a
    server.
    """
    cur = next((w for w in d["weeks"] if w["current"]), None)
    week_start = date.fromisoformat((cur or {}).get("week") or d["today"])
    target_km = float((cur or {}).get("plan_km") or d["plan_basis"]["baseline_km"] or 0)
    target_long = float((cur or {}).get("plan_long") or min(target_km, d["kpi"]["longest_recent"] or 0))
    target_long = min(target_long, target_km)
    remaining = max(target_km - target_long, 0)
    easy_one = round(remaining * 0.35, 1)
    tempo = round(remaining * 0.35, 1)
    easy_two = round(max(remaining - easy_one - tempo, 0), 1)

    suggested = [
        ("Rest", 0, "Recovery, mobility or an easy walk."),
        ("Easy run", easy_one, "Comfortable, conversational effort."),
        ("Rest", 0, "Recovery, mobility or an easy walk."),
        ("Tempo run", tempo, "Controlled, comfortably hard effort."),
        ("Rest", 0, "Recovery, mobility or an easy walk."),
        ("Easy run", easy_two, "Keep the pace comfortable."),
        ("Long run", target_long, "Easy effort; focus on time on feet."),
    ]
    plan_days = []
    for i, (kind, km, note) in enumerate(suggested):
        day = week_start + timedelta(days=i)
        plan_days.append({
            "date": day.isoformat(),
            "day": DAYS[i],
            "short": DAYS[i][:3],
            "type": kind,
            "km": km,
            "notes": note,
        })

    defaults = {
        "weekStart": week_start.isoformat(),
        "weekEnd": (week_start + timedelta(days=6)).isoformat(),
        "targetKm": round(target_km, 1),
        "targetLong": round(target_long, 1),
        "days": plan_days,
    }
    # Prevent a (future) user-entered string from closing this script element.
    defaults_json = json.dumps(defaults, ensure_ascii=False).replace("</", "<\\/")

    return f'''  <section class="card planner" aria-labelledby="weekly-plan-title">
    <div class="section-head">
      <div>
        <p class="section-kicker">This week</p>
        <h2 id="weekly-plan-title">Your weekly plan</h2>
        <p class="section-copy">A suggested schedule based on this week's target. Change it to fit real life.</p>
      </div>
      <div class="plan-total" id="plan-total"></div>
    </div>
    <div class="plan-grid" id="plan-cards" aria-live="polite"></div>
    <details class="plan-editor">
      <summary>Edit this week's plan</summary>
      <p>Adjust the session, distance or note for any day. Your changes are saved on this device.</p>
      <form id="plan-form">
        <div id="plan-editor-fields"></div>
        <div class="form-actions">
          <button class="button button-primary" type="submit">Save plan on this device</button>
          <button class="button button-quiet" id="reset-plan" type="button">Restore suggested plan</button>
        </div>
      </form>
    </details>
    <p class="local-note" id="plan-status">This plan is private to this browser. It does not change Strava.</p>
  </section>

  <section class="card manual-panel" aria-labelledby="manual-run-title">
    <div class="section-head">
      <div>
        <p class="section-kicker">Not on Strava?</p>
        <h2 id="manual-run-title">Add a manual run</h2>
        <p class="section-copy">Log a treadmill run, watch-free run or any activity that was not tracked in Strava.</p>
      </div>
    </div>
    <form class="manual-form" id="manual-run-form">
      <label>Date<input id="manual-date" name="date" type="date" value="{esc(d['today'])}" required></label>
      <label>Run name<input id="manual-name" name="name" type="text" maxlength="60" placeholder="e.g. Treadmill easy run"></label>
      <label>Distance (km)<input id="manual-distance" name="distance" type="number" min="0.1" max="200" step="0.1" inputmode="decimal" required></label>
      <label>Duration<input id="manual-duration" name="duration" type="text" inputmode="numeric" placeholder="00:45:00" required></label>
      <button class="button button-primary" type="submit">Add manual run</button>
    </form>
    <p class="form-help">Use <b>hh:mm:ss</b> (or <b>mm:ss</b>) for duration. Manual runs are kept on this device and are shown below; they are not sent to Strava.</p>
    <p class="manual-summary" id="manual-summary" aria-live="polite"></p>
    <ul class="runs manual-runs" id="manual-runs"></ul>
    <p class="local-note" id="manual-status"></p>
  </section>

  <script id="planner-defaults" type="application/json">{defaults_json}</script>'''


# ---------- Seite ----------

def build(d):
    k = d["kpi"]
    name = (d.get("athlete") or {}).get("name") or ""
    title = f"{name}'s Half Marathon" if name else "Half Marathon Countdown"
    days = d["days_left"]
    race = date.fromisoformat(d["race_date"])
    today = date.fromisoformat(d["today"])

    # Current week: actual distance against the pro-rata target.
    cur = next((w for w in d["weeks"] if w["current"]), None)
    pill = ""
    if cur and cur["plan_km"]:
        frac = (today.weekday() + 1) / 7
        due = cur["plan_km"] * frac
        r = cur["km"] / due if due > 0 else 1
        if r >= 0.95:
            pill = ('<span class="pill pill-good"><span class="pill-ico">●</span>On track this week</span>')
        elif r >= 0.75:
            pill = ('<span class="pill pill-warn"><span class="pill-ico">◐</span>A little behind this week</span>')
        else:
            pill = ('<span class="pill pill-crit"><span class="pill-ico">○</span>Well behind this week</span>')

    to_race = max(21.0975 - (k["longest_recent"] or 0), 0)
    long_sub = (f"{num(to_race)} km left to race distance" if to_race > 0.2
                else "race distance already in her legs")

    tiles = "\n".join([
        tile("Weekly distance", num(k["weekly_km"]), " km", "average of the last 4 weeks",
             delta_chip(k["weekly_km"], k["weekly_km_prev"], ("more", "less"), unit=" km")),
        tile("Longest run", num(k["longest_recent"]), " km", long_sub,
             delta_chip(k["longest_recent"], k.get("longest_prev") or None,
                        ("longer", "shorter"), unit=" km")),
        tile("Easy pace", mmss(k["easy_pace"]), " /km", "easy runs, last 4 weeks",
             delta_chip(k["easy_pace"], k["easy_pace_prev"], ("slower", "faster"),
                        lower_is_better=True, fmt=mmss, unit=" min/km")),
        tile("Finish-time prediction", hhmmss(k["prediction"]), "", "estimated from her best runs",
             delta_chip(k["prediction"], k["prediction_prev"], ("slower", "faster"),
                        lower_is_better=True, fmt=mmss, unit=" min")),
    ])

    runs = "".join(
        f'<li><span class="r-date">{date.fromisoformat(r["date"]).strftime("%d.%m.")}</span>'
        f'<span class="r-name">{esc(r["name"])}</span>'
        f'<span class="r-km">{num(r["km"])} km</span>'
        f'<span class="r-pace">{mmss(r["seconds"] / r["km"])}/km</span></li>'
        for r in d["recent_runs"])

    gen = datetime.fromisoformat(d["generated"]).strftime("%d.%m.%Y, %H:%M UTC")
    mock_banner = ('<div class="card banner">Example data — not connected to Strava yet.</div>'
                   if d.get("mock") else "")

    fc = chart_forecast(d["forecast"])
    fc_block = f"""    <figure class="card chart">
      <figcaption>
        <h2>How the prediction is progressing</h2>
        <p>Recalculated each week from the preceding six weeks (Riegel formula). Higher is faster.</p>
      </figcaption>
{fc}
    </figure>""" if fc else ""
    planner = weekly_plan(d)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(title)} — training progress.">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..125,400..800&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
:root {{
  color-scheme: light;
  --plane:#F1F3F5; --surface:#FBFCFD; --ink:#0F1418; --ink2:#4A5157; --muted:#7C858C;
  --hair:#E0E4E8; --axis:#CBD2D8;
  --ist:#2a78d6; --soll:#eb6834;
  --good:#0ca30c; --warn:#B4780A; --crit:#d03b3b;
  --ring:rgba(15,20,24,.09); --wash:rgba(42,120,214,.08); --wash-soll:rgba(235,104,52,.07);
  --sans:'Archivo','Archivo Fallback',system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --plane:#0A0C0E; --surface:#14181B; --ink:#F4F7F9; --ink2:#AFB8BE; --muted:#79828A;
    --hair:#242A2E; --axis:#333B41;
    --ist:#3987e5; --soll:#d95926;
    --good:#0ca30c; --warn:#fab219; --crit:#e66767;
    --ring:rgba(255,255,255,.10); --wash:rgba(57,135,229,.13); --wash-soll:rgba(217,89,38,.12);
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --plane:#0A0C0E; --surface:#14181B; --ink:#F4F7F9; --ink2:#AFB8BE; --muted:#79828A;
  --hair:#242A2E; --axis:#333B41;
  --ist:#3987e5; --soll:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#e66767;
  --ring:rgba(255,255,255,.10); --wash:rgba(57,135,229,.13); --wash-soll:rgba(217,89,38,.12);
}}

* {{ box-sizing: border-box; }}
body {{
  margin:0; background:var(--plane); color:var(--ink);
  font-family:var(--sans); font-size:16px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:920px; margin:0 auto; padding:clamp(16px,4vw,40px) clamp(14px,4vw,28px) 64px;
  display:flex; flex-direction:column; gap:clamp(14px,2.4vw,20px); }}

/* ---------- Kopf ---------- */
.hero {{ background:var(--surface); border:1px solid var(--hair); border-radius:14px;
  padding:clamp(20px,4vw,32px); }}
.eyebrow {{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); margin:0 0 14px; }}
.hero h1 {{ margin:0; font-size:clamp(24px,5vw,34px); font-weight:700; font-stretch:112%;
  letter-spacing:-.018em; line-height:1.1; text-wrap:balance; }}
.hero .when {{ margin:6px 0 0; color:var(--ink2); font-size:15px; }}
.count {{ display:flex; align-items:baseline; gap:12px; margin:22px 0 0; }}
.count b {{ font-size:clamp(58px,15vw,92px); font-weight:800; font-stretch:118%;
  letter-spacing:-.035em; line-height:.86; }}
.count span {{ font-size:15px; color:var(--ink2); }}
.rail {{ margin-top:20px; height:5px; border-radius:3px; background:var(--hair); overflow:hidden; }}
.rail i {{ display:block; height:100%; background:var(--ist); border-radius:3px; }}
.railcap {{ display:flex; justify-content:space-between; font-family:var(--mono); font-size:10.5px;
  letter-spacing:.09em; text-transform:uppercase; color:var(--muted); margin-top:7px; }}
.pill {{ display:inline-flex; align-items:center; gap:7px; margin-top:18px; padding:5px 12px 5px 10px;
  border-radius:999px; font-size:13px; font-weight:600; border:1px solid var(--ring); }}
.pill-ico {{ font-size:10px; line-height:1; }}
.pill-good {{ color:var(--good); }} .pill-warn {{ color:var(--warn); }} .pill-crit {{ color:var(--crit); }}

/* ---------- Kacheln ---------- */
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:clamp(10px,1.6vw,14px); }}
.tile {{ background:var(--surface); border:1px solid var(--hair); border-radius:12px; padding:16px 16px 14px;
  display:flex; flex-direction:column; gap:2px; }}
.tile-label {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--muted); }}
.tile-value {{ font-size:clamp(27px,4.4vw,33px); font-weight:700; font-stretch:106%; letter-spacing:-.024em;
  line-height:1.15; margin-top:5px; }}
.tile-unit {{ font-size:.46em; font-weight:600; color:var(--ink2); margin-left:2px; letter-spacing:0; }}
.tile-sub {{ font-size:12.5px; color:var(--ink2); line-height:1.35; margin-top:1px; }}
.chip {{ display:inline-flex; align-items:center; gap:5px; align-self:flex-start; margin-top:10px;
  white-space:nowrap;
  font-size:11.5px; font-weight:600; padding:3px 9px 3px 7px; border-radius:999px;
  border:1px solid var(--ring); color:var(--ink2); }}
.chip-ico {{ font-size:8.5px; line-height:1; }}
.chip-up {{ color:var(--good); }} .chip-down {{ color:var(--crit); }} .chip-flat {{ color:var(--muted); }}

/* ---------- Karten ---------- */
.card {{ background:var(--surface); border:1px solid var(--hair); border-radius:12px;
  padding:clamp(16px,2.6vw,22px); }}
.banner {{ font-size:13.5px; color:var(--ink2); border-style:dashed; }}
figcaption {{ margin:0 0 16px; }}
h2 {{ margin:0; font-size:16.5px; font-weight:700; font-stretch:104%; letter-spacing:-.008em; }}
figcaption p {{ margin:5px 0 0; font-size:13px; color:var(--ink2); max-width:62ch; line-height:1.45; }}
.two {{ display:grid; grid-template-columns:1fr; gap:clamp(14px,2.4vw,20px); }}
@media (min-width:760px) {{ .two {{ grid-template-columns:1fr 1fr; }} }}

/* ---------- Weekly plan & manual entries ---------- */
.section-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:16px; }}
.section-kicker {{ margin:0 0 4px; font-family:var(--mono); font-size:10.5px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--soll); }}
.section-copy {{ margin:5px 0 0; max-width:58ch; color:var(--ink2); font-size:13px; line-height:1.45; }}
.plan-total {{ flex:0 0 auto; padding:5px 9px; border:1px solid var(--ring); border-radius:999px;
  color:var(--ink2); font-family:var(--mono); font-size:11px; text-align:right; white-space:nowrap; }}
.plan-grid {{ display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:8px; }}
.plan-day {{ min-height:126px; padding:10px; border:1px solid var(--hair); border-radius:9px; background:var(--plane);
  display:flex; flex-direction:column; gap:6px; }}
.plan-day-name {{ font-family:var(--mono); font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
.plan-type {{ font-weight:700; font-size:13px; line-height:1.15; }}
.plan-km {{ margin-top:auto; font-variant-numeric:tabular-nums; font-size:13px; font-weight:600; color:var(--ist); }}
.plan-note {{ font-size:11px; color:var(--ink2); line-height:1.25; }}
.plan-editor {{ margin-top:14px; padding-top:14px; border-top:1px solid var(--hair); }}
.plan-editor > p {{ margin:8px 0 14px; color:var(--ink2); font-size:13px; }}
.plan-row {{ display:grid; grid-template-columns:90px minmax(120px, 1fr) 100px minmax(150px, 1.4fr); gap:10px;
  align-items:end; margin:0 0 10px; padding:0; border:0; }}
.plan-row legend {{ padding:0; font-family:var(--mono); font-size:11px; color:var(--muted); }}
.plan-row label, .manual-form label {{ display:flex; flex-direction:column; gap:5px; font-size:11px; font-weight:600; color:var(--ink2); }}
input {{ width:100%; min-width:0; padding:8px 9px; border:1px solid var(--hair); border-radius:7px; background:var(--surface);
  color:var(--ink); font:inherit; font-size:13px; }}
input:focus {{ outline:2px solid color-mix(in srgb, var(--ist) 40%, transparent); outline-offset:1px; border-color:var(--ist); }}
.form-actions {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }}
.button {{ appearance:none; border:1px solid var(--hair); border-radius:8px; padding:9px 12px; cursor:pointer;
  font:inherit; font-size:13px; font-weight:650; line-height:1.2; }}
.button-primary {{ background:var(--ist); border-color:var(--ist); color:white; }}
.button-primary:hover {{ filter:brightness(.94); }}
.button-quiet {{ background:transparent; color:var(--ink2); }}
.button-quiet:hover {{ background:var(--plane); }}
.local-note, .form-help, .manual-summary {{ margin:11px 0 0; color:var(--muted); font-size:12px; line-height:1.45; }}
.manual-form {{ display:grid; grid-template-columns:130px minmax(150px, 1.5fr) minmax(110px, .75fr) minmax(110px, .75fr) auto;
  align-items:end; gap:10px; }}
.manual-form .button {{ min-height:35px; }}
.manual-summary {{ color:var(--ink2); }}
.manual-runs {{ margin-top:8px; }}
.manual-runs li {{ grid-template-columns:52px 1fr auto auto auto; }}
.manual-delete {{ justify-self:end; padding:2px 0; border:0; background:transparent; color:var(--crit); cursor:pointer; font:inherit; font-size:12px; }}
.manual-delete:hover {{ text-decoration:underline; }}
@media (max-width:760px) {{
  .plan-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }}
  .plan-day {{ min-height:108px; }}
  .plan-row {{ grid-template-columns:76px 1fr 84px; }}
  .plan-row label:last-child {{ grid-column:2 / -1; }}
  .manual-form {{ grid-template-columns:1fr 1fr; }}
  .manual-form label:nth-child(2) {{ grid-column:1 / -1; }}
  .manual-form .button {{ grid-column:1 / -1; justify-self:start; }}
}}
@media (max-width:440px) {{
  .section-head {{ flex-direction:column; }}
  .plan-row {{ grid-template-columns:1fr 1fr; }}
  .plan-row legend {{ grid-column:1 / -1; }}
  .plan-row label:last-child {{ grid-column:1 / -1; }}
  .manual-runs li {{ grid-template-columns:44px 1fr auto; gap:8px; }}
  .manual-runs .r-pace {{ display:none; }}
}}

/* ---------- Plot ---------- */
.legend {{ display:flex; gap:16px; margin:-6px 0 14px; }}
.lg {{ display:inline-flex; align-items:center; gap:7px; font-size:12px; color:var(--ink2); }}
.sw {{ width:14px; height:12px; border-radius:3px; display:inline-block; }}
.sw-ist {{ background:var(--ist); }}
.sw-soll {{ background:transparent; border-top:2px dashed var(--soll); height:0; width:18px; border-radius:0; }}
.sw-plan {{ background:var(--wash-soll); border:1.5px dashed var(--soll); }}
.plot {{ position:relative; height:var(--plot-h); padding-left:38px; }}
.grid {{ position:absolute; inset:0 0 0 0; }}
.ygrid {{ position:absolute; left:38px; right:0; height:1px; background:var(--hair); }}
.ygrid:first-child {{ background:var(--axis); }}
.ytick {{ position:absolute; right:calc(100% + 8px); top:-.62em; font-family:var(--sans);
  font-variant-numeric:tabular-nums; font-size:10.5px; color:var(--muted); white-space:nowrap; }}
.marks {{ position:absolute; inset:0 0 0 38px; }}
.bar {{ position:absolute; bottom:0; width:min(52%,26px); transform:translateX(-50%);
  background:var(--ist); border-radius:4px 4px 0 0; }}
.bar-now {{ background:linear-gradient(var(--ist),var(--ist)) padding-box; opacity:.55; }}
.bar-plan {{ background:var(--wash-soll); border:1.5px dashed var(--soll); border-bottom:0;
  border-radius:5px 5px 0 0; }}
.bar-future {{ display:none; }}
.overlay {{ position:absolute; inset:0; width:100%; height:100%; overflow:visible; }}
.planline {{ fill:none; stroke:var(--soll); stroke-width:2; stroke-dasharray:5 4; stroke-linecap:round; }}
.trendline, .fcline {{ fill:none; stroke:var(--ist); stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; }}
.pdot {{ position:absolute; width:7px; height:7px; border-radius:50%; background:var(--soll);
  transform:translate(-50%,50%); box-shadow:0 0 0 2px var(--surface); }}
.rdot {{ position:absolute; width:var(--d); height:var(--d); border-radius:50%; background:var(--ist);
  opacity:.62; transform:translate(-50%,50%); box-shadow:0 0 0 2px var(--surface); }}
.enddot {{ position:absolute; width:9px; height:9px; border-radius:50%; background:var(--ist);
  transform:translate(-50%,50%); box-shadow:0 0 0 2px var(--surface); }}
.endlabel {{ position:absolute; right:0; transform:translateY(50%) translateY(-18px);
  font-size:12px; font-weight:700; font-variant-numeric:tabular-nums; color:var(--ist); }}
.refline {{ position:absolute; left:0; right:0; height:0; border-top:1.5px solid var(--soll); opacity:.85; }}
.refline span {{ position:absolute; left:0; bottom:4px; font-family:var(--mono); font-size:9.5px;
  letter-spacing:.07em; text-transform:uppercase; color:var(--soll); background:var(--surface); padding:0 3px; }}
.hit {{ position:absolute; top:0; bottom:0; cursor:default; }}
.hit-dot {{ top:auto; width:26px; height:26px; transform:translate(-50%,50%); border-radius:50%; }}
.hit:hover, .hit:focus-visible {{ background:var(--wash); border-radius:4px; outline:none; }}
.hit-dot:hover, .hit-dot:focus-visible {{ background:var(--wash); }}
.xaxis {{ position:relative; height:16px; margin-left:38px; margin-top:7px; }}
.xtick {{ position:absolute; transform:translateX(-50%); font-family:var(--mono); font-size:10px;
  letter-spacing:.04em; color:var(--muted); white-space:nowrap; }}
.xtick-now {{ color:var(--ink2); font-weight:600; }}
.xaxis-spark {{ display:flex; justify-content:space-between; margin-left:0; }}
.xaxis-spark span {{ font-family:var(--mono); font-size:10px; letter-spacing:.04em; color:var(--muted); }}
.plot-spark {{ padding-left:0; }}
.plot-spark .marks {{ inset:0; }}
.unit-note {{ font-family:var(--mono); font-size:10px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); margin-top:10px; margin-left:38px; }}
.plot-spark ~ .unit-note {{ margin-left:0; }}

/* ---------- Liste & Tabelle ---------- */
.runs {{ list-style:none; margin:0; padding:0; }}
.runs li {{ display:grid; grid-template-columns:52px 1fr auto auto; gap:12px; align-items:baseline;
  padding:9px 0; border-top:1px solid var(--hair); font-size:14px; }}
.runs li:first-child {{ border-top:0; }}
.r-date {{ font-family:var(--mono); font-size:11.5px; color:var(--muted); }}
.r-name {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.r-km, .r-pace {{ font-variant-numeric:tabular-nums; font-weight:600; }}
.r-pace {{ color:var(--ink2); font-weight:500; min-width:64px; text-align:right; }}
summary {{ cursor:pointer; font-size:14px; font-weight:600; }}
summary::marker {{ color:var(--muted); }}
.scroll {{ overflow-x:auto; margin-top:14px; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:right; padding:7px 10px; border-bottom:1px solid var(--hair); white-space:nowrap; }}
thead th {{ font-family:var(--mono); font-size:10px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); font-weight:500; }}
tbody th {{ text-align:left; font-weight:600; }}
td:last-child {{ color:var(--muted); }}

/* ---------- Tooltip & Footer ---------- */
#tip {{ position:fixed; z-index:50; pointer-events:none; opacity:0; transition:opacity .1s;
  background:var(--ink); color:var(--surface); font-size:12px; line-height:1.4; padding:7px 10px;
  border-radius:7px; white-space:pre-line; max-width:250px; box-shadow:0 6px 20px rgba(0,0,0,.22); }}
#tip.on {{ opacity:1; }}
footer {{ font-size:12px; color:var(--muted); line-height:1.6; }}
footer b {{ color:var(--ink2); font-weight:600; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; animation:none !important; }} }}
</style>

<div class="wrap">
  <header class="hero">
    <p class="eyebrow">Half marathon · {DAYS[race.weekday()]}, {de(d["race_date"])} {race.year}</p>
    <h1>{esc(title)}</h1>
    <p class="when">21.1 kilometres. This is how training is progressing.</p>
    <div class="count"><b>{days}</b><span>days to race day<br>({num(d["weeks_left"])} weeks)</span></div>
    <div class="rail"><i style="width:{d['block_progress'] * 100:.1f}%"></i></div>
    <div class="railcap"><span>Training block</span><span>{d['block_progress'] * 100:.0f} % complete</span></div>
    {pill}
  </header>

{mock_banner}

{planner}

  <section class="tiles">
{tiles}
  </section>

{chart_weekly(d["weeks"])}

  <div class="two">
{chart_longrun(d["weeks"])}
{chart_pace(d["pace_points"])}
  </div>

{fc_block}

  <section class="card">
    <h2>Recent runs</h2>
    <ul class="runs">{runs}</ul>
  </section>

{table_view(d["weeks"])}

  <footer>
    <p>Data from Strava, last updated <b>{gen}</b>. So far in this training block:
    <b>{num(d['totals']['km'])} km</b> in <b>{d['totals']['runs']} runs</b>.</p>
    <p>The target curve is not a generic plan: it starts from the actual volume of the last four weeks
    ({num(d['plan_basis']['baseline_km'])} km/week), increases by 6% per week until two weeks before race day,
    then tapers. The finish-time prediction is based on Riegel and is not a guarantee.</p>
  </footer>
</div>

<div id="tip" role="status" aria-live="polite"></div>
<script>
(function () {{
  var tip = document.getElementById('tip'), cur = null;
  function show(el, x, y) {{
    tip.textContent = el.getAttribute('data-tip');
    tip.classList.add('on');
    var r = tip.getBoundingClientRect();
    var left = Math.min(Math.max(x - r.width / 2, 8), innerWidth - r.width - 8);
    var top = y - r.height - 14;
    if (top < 8) top = y + 20;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }}
  function hide() {{ tip.classList.remove('on'); cur = null; }}
  document.addEventListener('pointermove', function (e) {{
    var el = e.target.closest ? e.target.closest('[data-tip]') : null;
    if (el) {{ cur = el; show(el, e.clientX, e.clientY); }}
    else if (cur) hide();
  }});
  document.addEventListener('pointerdown', function (e) {{
    var el = e.target.closest ? e.target.closest('[data-tip]') : null;
    if (el) show(el, e.clientX, e.clientY); else hide();
  }});
  document.addEventListener('scroll', hide, true);
  // Keyboard: make tooltip targets focusable.
  document.querySelectorAll('[data-tip]').forEach(function (el) {{
    el.tabIndex = 0;
    el.addEventListener('focus', function () {{
      var r = el.getBoundingClientRect();
      show(el, r.left + r.width / 2, r.top + r.height / 2);
    }});
    el.addEventListener('blur', hide);
  }});
}})();

// The dashboard is static, so personal plan edits and manual entries are kept
// in this browser only. They never leave the device or modify Strava data.
(function () {{
  var source = document.getElementById('planner-defaults');
  if (!source) return;

  var defaults;
  try {{ defaults = JSON.parse(source.textContent); }} catch (err) {{ return; }}

  var planCards = document.getElementById('plan-cards');
  var planFields = document.getElementById('plan-editor-fields');
  var planForm = document.getElementById('plan-form');
  var planTotal = document.getElementById('plan-total');
  var planStatus = document.getElementById('plan-status');
  var resetPlan = document.getElementById('reset-plan');
  var manualForm = document.getElementById('manual-run-form');
  var manualDate = document.getElementById('manual-date');
  var manualName = document.getElementById('manual-name');
  var manualDistance = document.getElementById('manual-distance');
  var manualDuration = document.getElementById('manual-duration');
  var manualRuns = document.getElementById('manual-runs');
  var manualSummary = document.getElementById('manual-summary');
  var manualStatus = document.getElementById('manual-status');
  var planKey = 'half-marathon-tracker:plan:' + defaults.weekStart;
  var runsKey = 'half-marathon-tracker:manual-runs';

  function escapeHtml(value) {{
    return String(value).replace(/[&<>"']/g, function (char) {{
      return {{ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }}[char];
    }});
  }}
  function load(key, fallback) {{
    try {{
      var saved = localStorage.getItem(key);
      return saved ? JSON.parse(saved) : fallback;
    }} catch (err) {{ return fallback; }}
  }}
  function save(key, value) {{
    try {{ localStorage.setItem(key, JSON.stringify(value)); return true; }}
    catch (err) {{ return false; }}
  }}
  function number(value, fallback) {{
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }}
  function km(value) {{
    var parsed = Math.max(0, number(value, 0));
    return Math.round(parsed * 10) / 10;
  }}
  function formatKm(value) {{
    return km(value).toLocaleString('en-GB', {{ minimumFractionDigits: 0, maximumFractionDigits: 1 }});
  }}
  function formatDate(value) {{
    var parts = value.split('-');
    if (parts.length !== 3) return value;
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])).toLocaleDateString('en-GB', {{ day:'numeric', month:'short' }});
  }}
  function normalisePlan(value) {{
    var savedDays = value && Array.isArray(value.days) ? value.days : [];
    return {{
      days: defaults.days.map(function (day, index) {{
        var saved = savedDays[index] || {{}};
        return {{
          date: day.date,
          day: day.day,
          short: day.short,
          type: String(saved.type || day.type).slice(0, 60),
          km: km(saved.km === undefined ? day.km : saved.km),
          notes: String(saved.notes === undefined ? day.notes : saved.notes).slice(0, 160)
        }};
      }})
    }};
  }}
  var plan = normalisePlan(load(planKey, null));
  var entries = load(runsKey, []);
  if (!Array.isArray(entries)) entries = [];
  entries = entries.filter(function (entry) {{
    return entry && /^\d{{4}}-\d{{2}}-\d{{2}}$/.test(String(entry.date || '')) && number(entry.km, 0) > 0 && number(entry.seconds, 0) > 0;
  }});

  function renderPlan() {{
    var total = plan.days.reduce(function (sum, day) {{ return sum + km(day.km); }}, 0);
    planTotal.textContent = formatKm(total) + ' km planned';
    planCards.innerHTML = plan.days.map(function (day) {{
      var rest = km(day.km) === 0;
      return '<article class="plan-day">' +
        '<span class="plan-day-name">' + escapeHtml(day.short) + ' · ' + escapeHtml(formatDate(day.date)) + '</span>' +
        '<span class="plan-type">' + escapeHtml(day.type) + '</span>' +
        '<span class="plan-note">' + escapeHtml(day.notes) + '</span>' +
        '<span class="plan-km">' + (rest ? 'Rest day' : formatKm(day.km) + ' km') + '</span>' +
      '</article>';
    }}).join('');
    planFields.innerHTML = plan.days.map(function (day, index) {{
      return '<fieldset class="plan-row">' +
        '<legend>' + escapeHtml(day.day) + '</legend>' +
        '<label>Session<input name="type-' + index + '" maxlength="60" value="' + escapeHtml(day.type) + '"></label>' +
        '<label>km<input name="km-' + index + '" type="number" min="0" max="200" step="0.1" inputmode="decimal" value="' + km(day.km) + '"></label>' +
        '<label>Note<input name="note-' + index + '" maxlength="160" value="' + escapeHtml(day.notes) + '"></label>' +
      '</fieldset>';
    }}).join('');
  }}

  function parseDuration(value) {{
    var pieces = String(value || '').trim().split(':');
    if (pieces.length !== 2 && pieces.length !== 3) return null;
    if (pieces.some(function (part) {{ return !/^\d{{1,2}}$/.test(part); }})) return null;
    var values = pieces.map(Number);
    var hours = pieces.length === 3 ? values[0] : 0;
    var minutes = pieces.length === 3 ? values[1] : values[0];
    var seconds = pieces.length === 3 ? values[2] : values[1];
    if (minutes > 59 || seconds > 59) return null;
    var result = hours * 3600 + minutes * 60 + seconds;
    return result > 0 ? result : null;
  }}
  function formatDuration(seconds) {{
    seconds = Math.round(seconds);
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var secs = seconds % 60;
    return (hours ? hours + ':' : '') + String(minutes).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
  }}
  function renderManualRuns() {{
    entries.sort(function (a, b) {{ return String(b.date).localeCompare(String(a.date)); }});
    var inThisWeek = entries.filter(function (entry) {{ return entry.date >= defaults.weekStart && entry.date <= defaults.weekEnd; }});
    var weeklyKm = inThisWeek.reduce(function (sum, entry) {{ return sum + km(entry.km); }}, 0);
    manualSummary.textContent = inThisWeek.length
      ? 'Manual additions this week: ' + inThisWeek.length + (inThisWeek.length === 1 ? ' run · ' : ' runs · ') + formatKm(weeklyKm) + ' km.'
      : 'No manual additions in this plan week yet.';
    manualRuns.innerHTML = entries.map(function (entry) {{
      var pace = number(entry.seconds, 0) / km(entry.km);
      return '<li>' +
        '<span class="r-date">' + escapeHtml(formatDate(entry.date)) + '</span>' +
        '<span class="r-name">' + escapeHtml(entry.name || 'Manual run') + '</span>' +
        '<span class="r-km">' + formatKm(entry.km) + ' km</span>' +
        '<span class="r-pace">' + formatDuration(pace) + '/km</span>' +
        '<button class="manual-delete" type="button" data-id="' + escapeHtml(entry.id) + '">Remove</button>' +
      '</li>';
    }}).join('');
  }}

  planForm.addEventListener('submit', function (event) {{
    event.preventDefault();
    plan.days = plan.days.map(function (day, index) {{
      var type = planForm.elements['type-' + index].value.trim() || 'Rest';
      var note = planForm.elements['note-' + index].value.trim();
      return {{ date:day.date, day:day.day, short:day.short, type:type.slice(0, 60), km:km(planForm.elements['km-' + index].value), notes:note.slice(0, 160) }};
    }});
    if (save(planKey, plan)) {{
      planStatus.textContent = 'Plan saved on this device.';
    }} else {{
      planStatus.textContent = 'Your browser could not save the plan. It will remain visible until this page is closed.';
    }}
    renderPlan();
  }});
  resetPlan.addEventListener('click', function () {{
    if (!window.confirm('Restore the suggested plan for this week? Your current plan changes will be replaced.')) return;
    plan = normalisePlan(null);
    save(planKey, plan);
    planStatus.textContent = 'Suggested plan restored.';
    renderPlan();
  }});
  manualForm.addEventListener('submit', function (event) {{
    event.preventDefault();
    var distance = km(manualDistance.value);
    var seconds = parseDuration(manualDuration.value);
    if (!/^\d{{4}}-\d{{2}}-\d{{2}}$/.test(manualDate.value) || distance <= 0 || !seconds) {{
      manualStatus.textContent = 'Please enter a date, a distance and a valid duration (hh:mm:ss or mm:ss).';
      return;
    }}
    var id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(16).slice(2);
    entries.unshift({{
      id: id,
      date: manualDate.value,
      name: manualName.value.trim().slice(0, 60) || 'Manual run',
      km: distance,
      seconds: seconds
    }});
    if (save(runsKey, entries)) {{
      manualStatus.textContent = 'Manual run saved on this device.';
    }} else {{
      manualStatus.textContent = 'Your browser could not save the run. It will remain visible until this page is closed.';
    }}
    manualName.value = '';
    manualDistance.value = '';
    manualDuration.value = '';
    renderManualRuns();
  }});
  manualRuns.addEventListener('click', function (event) {{
    var button = event.target.closest ? event.target.closest('.manual-delete') : null;
    if (!button) return;
    if (!window.confirm('Remove this manual run from this browser?')) return;
    entries = entries.filter(function (entry) {{ return entry.id !== button.getAttribute('data-id'); }});
    save(runsKey, entries);
    manualStatus.textContent = 'Manual run removed from this device.';
    renderManualRuns();
  }});

  renderPlan();
  renderManualRuns();
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    with open(DATA) as f:
        data = json.load(f)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(data))
    print("->", OUT)
