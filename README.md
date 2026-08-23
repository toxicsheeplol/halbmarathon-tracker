# Half-Marathon Dashboard

Fetch Réka’s Strava runs and render them as a static `index.html` website for GitHub Pages.

## Files

| File | Purpose |
|---|---|
| `auth.py` | One-time Strava authorisation; creates `creds.json`. |
| `strava_creds.py` | Safely reads and writes `creds.json`. |
| `tracker.py` | Fetches runs and calculates metrics → `data.json`. |
| `render.py` | Builds the published `index.html` from `data.json`. |
| `update.sh` | Runs the tracker and renderer in sequence. |
| `.gitignore` | Keeps secrets and local logs out of Git. |

Runtime files: `creds.json`, `data.json`, `index.html`, and `update.log`.

## Set up on macOS

Keep all files together in one folder. No additional libraries are needed — only the Python 3 included with macOS.

```bash
cd "/Users/tim/Documents/Halbmarathon Prep"
chmod +x update.sh
python3 tracker.py --mock && python3 render.py
```

When `index.html` is created, the local pipeline is working.

## Connect Strava

Create an application at <https://www.strava.com/settings/api>. Set **Authorization Callback Domain** to `localhost` (the word only, without `http://`).

```bash
python3 auth.py url 12345
```

Replace `12345` with your Client ID. The command prints links for the browser, Android and iPhone. Réka opens the appropriate link while signed in to Strava and grants access to **all activities**, including private activities.

After authorising, the localhost address does not load — that is expected. Copy the complete address from the browser’s address bar, then run:

```bash
python3 auth.py token 12345 YOUR_CLIENT_SECRET "http://localhost/?state=&code=abc123..."
python3 auth.py check
python3 tracker.py && python3 render.py
```

The URL code expires after a few minutes. If it does, run `auth.py url` again and authorise again.

## Publish updates

After a real Strava refresh, publish the updated data and page with:

```bash
git add data.json index.html
git commit -m "Update running data"
git push
```

`creds.json` contains the Client Secret and refresh token. Never share or commit it. Strava rotates the refresh token when the tracker refreshes access; `tracker.py` writes the replacement safely and keeps the previous version as `creds.json.bak`.

## Automatic refresh every 12 hours (macOS)

`refresh-and-publish.sh` fetches the latest Strava runs, builds the page and publishes only `data.json` and `index.html`. It is designed for a macOS `launchd` job every 12 hours. The job will stop safely if the repository has uncommitted changes or the Git histories diverge; see `refresh.log` for the result.

Because this automatically publishes new training data to the public website, keep the repository clean and only connect a Strava account whose activity details may be displayed there.

You can adjust `RACE_DATE`, `ATHLETE_NAME`, and `LOOKBACK_WEEKS` at the top of `tracker.py`.
