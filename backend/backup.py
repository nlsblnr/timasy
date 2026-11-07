"""Backups der Datenbankdatei (V-6, v0.9).

Alle Daten liegen in einer einzigen SQLite-Datei (Abschnitt 10). Ein Backup ist
eine vollständige Kopie davon im Ordner data/backups/:
- timasy-JJJJ-MM-TT-HHMMSS.db   per Knopf, bleibt immer erhalten
- timasy-auto-JJJJ-MM-TT.db     automatisch, einmal pro Tag, die letzten 14

Wiederherstellen: Timasy beenden, die gewünschte Backup-Datei nach
data/timasy.db kopieren (die alte vorher umbenennen), Timasy starten.

Kopiert wird mit der Backup-Funktion von SQLite. Sie ist sicher, auch wenn
Timasy gerade läuft und in die Datei schreibt.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

AUTO_KEEP = 14
AUTO_PREFIX = "timasy-auto-"


def _copy(db_path: Path | str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def create_backup(db_path: Path | str, folder: Path, now: datetime) -> Path:
    """Backup per Knopf."""
    return _copy(db_path, folder / f"timasy-{now:%Y-%m-%d-%H%M%S}.db")


def daily_backup(db_path: Path | str, folder: Path, now: datetime) -> Path | None:
    """Automatisches Backup, höchstens eines pro Tag; ältere über 14 werden gelöscht.

    Gibt den Pfad zurück oder None, wenn es heute schon eines gibt.
    """
    target = folder / f"{AUTO_PREFIX}{now:%Y-%m-%d}.db"
    if target.exists():
        return None
    _copy(db_path, target)
    autos = sorted(folder.glob(f"{AUTO_PREFIX}*.db"))   # Datum im Namen: sortiert = zeitlich
    for old in autos[:-AUTO_KEEP]:
        old.unlink()
    return target


def list_backups(folder: Path) -> list[dict]:
    """Alle Backups, neuste zuerst."""
    if not folder.exists():
        return []
    files = sorted(folder.glob("timasy-*.db"), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return [{
        "name": p.name,
        "size": p.stat().st_size,
        "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        "automatic": p.name.startswith(AUTO_PREFIX),
    } for p in files]
