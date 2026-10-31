"""Verbindung zur SQLite-Datei."""
import sqlite3
from pathlib import Path

from .migrations import migrate


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI öffnet die Verbindung in einem anderen
    # Thread, als es die Anfrage bearbeitet. Das ist hier unproblematisch, weil
    # jede Anfrage ihre eigene Verbindung bekommt und sie nie geteilt wird.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row             # Zeilen wie ein dict lesen: row["title"]
    conn.execute("PRAGMA foreign_keys = ON")   # ON DELETE CASCADE aktivieren
    return conn


def init_db(path: Path | str) -> None:
    """Datei anlegen (falls nötig) und fehlende Migrationen ausführen."""
    conn = connect(path)
    try:
        migrate(conn)
    finally:
        conn.close()
