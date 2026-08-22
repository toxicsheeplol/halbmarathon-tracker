# Halbmarathon-Dashboard

Holt Rékas Läufe aus Strava und rendert daraus `dashboard.html`.

## Dateien

| Datei | Zweck |
|---|---|
| `auth.py` | Einmalige Strava-Autorisierung, erzeugt `creds.json` |
| `strava_creds.py` | Sicheres Lesen/Schreiben von `creds.json` |
| `tracker.py` | Holt die Läufe, berechnet Kennzahlen → `data.json` |
| `render.py` | Baut aus `data.json` das `dashboard.html` |
| `update.sh` | Ruft tracker + render nacheinander auf (für den Zeitplan) |
| `gitignore.txt` | Inhalt für `.gitignore`, falls der Ordner in Git liegt |

Erzeugt werden zur Laufzeit: `creds.json`, `data.json`, `dashboard.html`, `update.log`.

## Einrichtung auf macOS

Alle Dateien in **einen** Ordner legen, z. B. `~/halbmarathon`. Es werden keine
zusätzlichen Bibliotheken gebraucht — nur das python3, das bei macOS dabei ist.

```bash
cd ~/halbmarathon
chmod +x update.sh
python3 tracker.py --mock && python3 render.py    # Testlauf ohne Strava
```

Wenn `dashboard.html` entsteht, funktioniert die Pipeline.

### Strava verbinden

Auf https://www.strava.com/settings/api eine Anwendung anlegen.
**Authorization Callback Domain: `localhost`** (nur das Wort, ohne `http://`).

```bash
python3 auth.py url 12345                      # 12345 = deine Client ID
```

Gibt drei Links aus. Réka öffnet einen davon (iPhone-Link nur in Safari) und
muss dabei den Zugriff auf **alle** Aktivitäten erlauben, auch die privaten.
Nach „Autorisieren" lädt die Seite nicht — das ist richtig. Sie kopiert die
komplette Adresse aus der Adressleiste und schickt sie zurück.

```bash
python3 auth.py token 12345 DEIN_SECRET "http://localhost/?state=&code=abc123..."
python3 auth.py check                          # zeigt die letzten 5 Aktivitäten
python3 tracker.py && python3 render.py        # echter Durchlauf
```

Der Code in der URL verfällt nach wenigen Minuten. Falls es zu lange gedauert
hat: einfach `auth.py url` erneut aufrufen und neu autorisieren.

## Automatisch aktualisieren

`update.sh` erledigt beide Schritte und schreibt nach `update.log`.
Zwei Wege, den Mac das regelmäßig tun zu lassen:

### cron (schneller eingerichtet)

```bash
crontab -e
```

Eine Zeile eintragen — täglich um 6:30 Uhr:

```
30 6 * * * /Users/DEINNAME/halbmarathon/update.sh
```

Absolute Pfade sind Pflicht, `~` funktioniert in cron nicht.

### launchd (der von Apple vorgesehene Weg)

Läuft im Gegensatz zu cron **nach**, wenn der Mac zur geplanten Zeit geschlafen
hat. Datei `~/Library/LaunchAgents/de.halbmarathon.update.plist` anlegen:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>de.halbmarathon.update</string>
  <key>ProgramArguments</key>
  <array><string>/Users/DEINNAME/halbmarathon/update.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
</dict>
</plist>
```

Aktivieren:

```bash
launchctl load ~/Library/LaunchAgents/de.halbmarathon.update.plist
```

Beim ersten Lauf fragt macOS eventuell nach Berechtigungen für den Ordner —
einmal bestätigen, danach ist Ruhe.

**Wichtig:** Der Mac muss zur geplanten Zeit eingeschaltet sein. Wenn er das
nicht zuverlässig ist, ist ein GitHub-Actions-Workflow die bessere Wahl.

## Wartung

`creds.json` enthält Client Secret und Refresh-Token — nicht weitergeben, nicht
committen. Strava tauscht den Refresh-Token bei jedem Abruf aus; `tracker.py`
schreibt ihn atomar zurück und legt die vorherige Fassung als `creds.json.bak`
daneben. Falls doch einmal etwas schiefgeht, lässt sich daraus zurückgehen —
andernfalls hilft nur eine neue Autorisierung über `auth.py url`.

Anpassen lassen sich oben in `tracker.py`: `RACE_DATE`, `ATHLETE_NAME` und
`LOOKBACK_WEEKS`.
