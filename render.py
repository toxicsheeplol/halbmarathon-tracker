#!/usr/bin/env python3
"""Rendert data.json zu dashboard.html (Inhalt fuer das Artifact, ohne <html>/<head>/<body>)."""

import html
import json
import math
import os
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "dashboard.html")

MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


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
    return f"{d.day}. {MONTHS[d.month - 1]}"


def num(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",")


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- Bausteine ----------

def delta_chip(now, prev, words, lower_is_better=False, fmt=lambda v: num(v), unit=""):
    """Veraenderungs-Chip mit Icon + Wort - Farbe traegt die Aussage nie allein.

    `words` ist das Paar (mehr, weniger) in der Sprache der Kennzahl.
    """
    if now is None or prev is None or prev == 0:
        return '<span class="chip chip-flat"><span class="chip-ico">–</span>erster Wert</span>'
    d = now - prev
    better = (d < 0) if lower_is_better else (d > 0)
    if abs(d) < (0.05 if not lower_is_better else 0.5):
        return '<span class="chip chip-flat"><span class="chip-ico">→</span>unverändert</span>'
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
    """Ganzzahlige, lesbare Achsenschritte, die knapp ueber vmax enden."""
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
    """Achsenschritte fuer Zeitwerte (Sekunden) - ca. 4 Linien."""
    span = hi - lo
    step = next((s for s in (60, 120, 300, 600, 900, 1800, 3600) if span / s <= 5), 3600)
    out, v = [], int(lo / step + 1) * step
    while v < hi:
        out.append((v, y(v)))
        v += step
    return out


def tick_every(n, want=5):
    """Jeden wievielten X-Wert beschriften, damit die Labels nicht kollidieren."""
    return max(1, -(-n // want))


def keep_tick(i, n, want=5):
    step = tick_every(n, want)
    return i % step == (n - 1) % step


# ---------- Charts ----------

def chart_weekly(weeks):
    """Wochenkilometer: Balken = gelaufen, Linie = Soll."""
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
        # Tooltip-Trefferflaeche ueber die volle Spaltenhoehe
        soll = f" · Soll {num(w['plan_km'])} km" if w["plan_km"] else ""
        note = " · läuft noch" if w["current"] else ""
        hits.append(
            f'<div class="hit" style="left:{i / n * 100:.4f}%;width:{100 / n:.4f}%" '
            f'data-tip="Woche ab {esc(w["label"])}&#10;{num(w["km"])} km · {w["runs"]} Läufe{soll}{note}"></div>')

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
        <h2>Wochenkilometer</h2>
        <p>Was sie gelaufen ist, gegen die Sollkurve bis zum Rennen.</p>
      </figcaption>
      <div class="legend">
        <span class="lg"><i class="sw sw-ist"></i>gelaufen</span>
        <span class="lg"><i class="sw sw-soll"></i>Soll</span>
      </div>
      <div class="plot" style="--plot-h:210px">
        <div class="grid">{axis_y(ticks_pct(ticks, top), lambda v: num(v, 0))}</div>
        <div class="marks">{''.join(bars)}{line}{dots}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{xlab}</div>
      <div class="unit-note">Kilometer pro Woche</div>
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
        kind = "gelaufen" if w["long"] > 0 else "geplant"
        hits.append(f'<div class="hit" style="left:{i / n * 100:.4f}%;width:{100 / n:.4f}%" '
                    f'data-tip="Woche ab {esc(w["label"])}&#10;längster Lauf: {num(v)} km ({kind})"></div>')
    ref = (f'<div class="refline" style="bottom:{race_km / top * 100:.4f}%">'
           f'<span>Renndistanz 21,1</span></div>')
    xlab = "".join(
        f'<div class="xtick{" xtick-now" if w["current"] else ""}" style="left:{(i + 0.5) / n * 100:.4f}%">{esc(w["label"])}</div>'
        for i, w in enumerate(ws) if keep_tick(i, n, 4))
    return f"""    <figure class="card chart">
      <figcaption>
        <h2>Längster Lauf pro Woche</h2>
        <p>Der wichtigste Indikator vor einem Halbmarathon. Umrandet = noch geplant.</p>
      </figcaption>
      <div class="legend">
        <span class="lg"><i class="sw sw-ist"></i>gelaufen</span>
        <span class="lg"><i class="sw sw-plan"></i>geplant</span>
      </div>
      <div class="plot" style="--plot-h:180px">
        <div class="grid">{axis_y(ticks_pct(ticks, top), lambda v: num(v, 0))}</div>
        <div class="marks">{''.join(bars)}{ref}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{xlab}</div>
      <div class="unit-note">Kilometer</div>
    </figure>"""


def chart_pace(points):
    """Tempo pro Lauf + 4-Wochen-Trend. Schnellere Zeiten liegen oben."""
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

    def y(pace):                       # invertiert: schneller = weiter oben
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

    # gleitender 21-Tage-Mittelwert als Trend
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

    # Monatsbeschriftung
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
        <h2>Tempo pro Lauf</h2>
        <p>Ein Punkt je Lauf, Punktgröße = Distanz. Weiter oben heißt schneller; die Linie ist der 3-Wochen-Schnitt.</p>
      </figcaption>
      <div class="plot" style="--plot-h:180px">
        <div class="grid">{axis_y(tick_vals, mmss)}</div>
        <div class="marks">{''.join(dots)}{tl}{''.join(hits)}</div>
      </div>
      <div class="xaxis">{''.join(xlab)}</div>
      <div class="unit-note">Minuten pro Kilometer</div>
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
        f'data-tip="Stand {esc(f["label"])}&#10;Prognose {hhmmss(f["seconds"])}"></div>'
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
      <div class="xaxis xaxis-spark"><span>{esc(fc[0]["label"])}</span><span>heute</span></div>
      <div class="unit-note">Hochgerechnete Zielzeit, Stunden:Minuten</div>"""


def table_view(weeks):
    rows = []
    for w in weeks:
        if w["runs"] == 0 and not w["plan_km"]:
            continue
        state = "läuft" if w["current"] else ("geplant" if w["future"] else "")
        rows.append(f"<tr><th scope=\"row\">{esc(w['label'])}</th>"
                    f"<td>{num(w['km']) if w['runs'] else '–'}</td>"
                    f"<td>{num(w['plan_km']) if w['plan_km'] else '–'}</td>"
                    f"<td>{num(w['long']) if w['long'] else '–'}</td>"
                    f"<td>{w['runs'] or '–'}</td>"
                    f"<td>{mmss(w['avg_pace'])}</td><td>{state}</td></tr>")
    return f"""    <details class="card tablewrap">
      <summary>Alle Wochen als Tabelle</summary>
      <div class="scroll">
        <table>
          <thead><tr><th scope="col">Woche ab</th><th scope="col">km</th><th scope="col">Soll km</th>
          <th scope="col">längster</th><th scope="col">Läufe</th><th scope="col">ø Pace</th><th scope="col"></th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </details>"""


# ---------- Seite ----------

def build(d):
    k = d["kpi"]
    name = (d.get("athlete") or {}).get("name") or ""
    title = f"{name}s Halbmarathon" if name else "Halbmarathon-Countdown"
    days = d["days_left"]
    race = date.fromisoformat(d["race_date"])
    today = date.fromisoformat(d["today"])

    # Status der laufenden Woche: Ist gegen anteiliges Soll
    cur = next((w for w in d["weeks"] if w["current"]), None)
    pill = ""
    if cur and cur["plan_km"]:
        frac = (today.weekday() + 1) / 7
        due = cur["plan_km"] * frac
        r = cur["km"] / due if due > 0 else 1
        if r >= 0.95:
            pill = ('<span class="pill pill-good"><span class="pill-ico">●</span>Diese Woche im Plan</span>')
        elif r >= 0.75:
            pill = ('<span class="pill pill-warn"><span class="pill-ico">◐</span>Diese Woche etwas hinten</span>')
        else:
            pill = ('<span class="pill pill-crit"><span class="pill-ico">○</span>Diese Woche deutlich hinten</span>')

    to_race = max(21.0975 - (k["longest_recent"] or 0), 0)
    long_sub = (f"noch {num(to_race)} km bis zur Renndistanz" if to_race > 0.2
                else "sie hat die Distanz schon in den Beinen")

    tiles = "\n".join([
        tile("Wochenumfang", num(k["weekly_km"]), " km", "Schnitt der letzten 4 Wochen",
             delta_chip(k["weekly_km"], k["weekly_km_prev"], ("mehr", "weniger"), unit=" km")),
        tile("Längster Lauf", num(k["longest_recent"]), " km", long_sub,
             delta_chip(k["longest_recent"], k.get("longest_prev") or None,
                        ("länger", "kürzer"), unit=" km")),
        tile("Lockeres Tempo", mmss(k["easy_pace"]), " /km", "ruhige Läufe, letzte 4 Wochen",
             delta_chip(k["easy_pace"], k["easy_pace_prev"], ("langsamer", "schneller"),
                        lower_is_better=True, fmt=mmss, unit=" min/km")),
        tile("Zielzeit-Prognose", hhmmss(k["prediction"]), "", "hochgerechnet aus ihren besten Läufen",
             delta_chip(k["prediction"], k["prediction_prev"], ("langsamer", "schneller"),
                        lower_is_better=True, fmt=mmss, unit=" min")),
    ])

    runs = "".join(
        f'<li><span class="r-date">{date.fromisoformat(r["date"]).strftime("%d.%m.")}</span>'
        f'<span class="r-name">{esc(r["name"])}</span>'
        f'<span class="r-km">{num(r["km"])} km</span>'
        f'<span class="r-pace">{mmss(r["seconds"] / r["km"])}/km</span></li>'
        for r in d["recent_runs"])

    gen = datetime.fromisoformat(d["generated"]).strftime("%d.%m.%Y, %H:%M UTC")
    mock_banner = ('<div class="card banner">Beispieldaten – noch nicht mit Strava verbunden.</div>'
                   if d.get("mock") else "")

    fc = chart_forecast(d["forecast"])
    fc_block = f"""    <figure class="card chart">
      <figcaption>
        <h2>Wie sich die Prognose entwickelt</h2>
        <p>Woche für Woche neu aus den jeweils letzten sechs Wochen hochgerechnet (Riegel-Formel). Weiter oben heißt schneller.</p>
      </figcaption>
{fc}
    </figure>""" if fc else ""

    return f"""<title>{esc(title)}</title>
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
    <p class="eyebrow">Halbmarathon · {DAYS[race.weekday()]}, {de(d["race_date"])} {race.year}</p>
    <h1>{esc(title)}</h1>
    <p class="when">21,1 Kilometer. Hier steht, wie das Training läuft.</p>
    <div class="count"><b>{days}</b><span>Tage bis zum Start<br>({num(d["weeks_left"])} Wochen)</span></div>
    <div class="rail"><i style="width:{d['block_progress'] * 100:.1f}%"></i></div>
    <div class="railcap"><span>Trainingsblock</span><span>{d['block_progress'] * 100:.0f} % geschafft</span></div>
    {pill}
  </header>

{mock_banner}

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
    <h2>Letzte Läufe</h2>
    <ul class="runs">{runs}</ul>
  </section>

{table_view(d["weeks"])}

  <footer>
    <p>Daten aus Strava, zuletzt aktualisiert am <b>{gen}</b>. Im Trainingsblock bisher
    <b>{num(d['totals']['km'])} km</b> in <b>{d['totals']['runs']} Läufen</b>.</p>
    <p>Die Sollkurve ist kein Plan von der Stange: Sie geht von ihrem tatsächlichen Umfang der letzten vier Wochen
    aus ({num(d['plan_basis']['baseline_km'])} km/Woche), steigert um 6 % pro Woche bis zwei Wochen vor dem Rennen
    und tapert dann. Die Zielzeit ist eine Hochrechnung nach Riegel und keine Garantie.</p>
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
  // Tastatur: Trefferflaechen fokussierbar machen
  document.querySelectorAll('[data-tip]').forEach(function (el) {{
    el.tabIndex = 0;
    el.addEventListener('focus', function () {{
      var r = el.getBoundingClientRect();
      show(el, r.left + r.width / 2, r.top + r.height / 2);
    }});
    el.addEventListener('blur', hide);
  }});
}})();
</script>
"""


if __name__ == "__main__":
    with open(DATA) as f:
        data = json.load(f)
    with open(OUT, "w") as f:
        f.write(build(data))
    print("->", OUT)
