"""Laden und atomares Speichern von creds.json.

Strava rotiert den Refresh-Token bei jedem Refresh. Geht das Zurueckschreiben
schief, ist der Zugang weg und muss ueber den Browser neu autorisiert werden.
Deshalb: erst Backup, dann atomar per os.replace ersetzen.
"""

import json
import os
import shutil
import tempfile


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, creds):
    """Schreibt creds atomar. Die vorherige Fassung bleibt als .bak liegen."""
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")

    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".creds-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(creds, f, indent=2)
            f.flush()
            os.fsync(f.fileno())          # wirklich auf der Platte, nicht nur im Cache
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)             # atomar - entweder alt oder neu, nie halb
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
