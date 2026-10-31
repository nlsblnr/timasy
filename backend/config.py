"""Einstellungen, die beim Start feststehen."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Zeitzone (Settings, Abschnitt 4). Einstellbar wird sie in M6.
TIMEZONE = ZoneInfo("Europe/Zurich")

# Die ganze App lebt in einer einzigen SQLite-Datei (Abschnitt 10).
DB_PATH = Path(os.environ.get("TIMASY_DB", PROJECT_ROOT / "data" / "timasy.db"))

# Nur lokal erreichbar (T-3).
HOST = "127.0.0.1"
PORT = int(os.environ.get("TIMASY_PORT", "8765"))

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
