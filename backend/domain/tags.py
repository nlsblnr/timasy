"""Tags (R-22): optional, frei wählbar, mehrere pro Aufgabe."""
from typing import Iterable


def normalize_tag(name: str) -> str:
    """Einheitliche Schreibweise: ohne '#', ohne Leerzeichen am Rand, klein.

    So entstehen aus "Arbeit" und "arbeit" nicht zwei verschiedene Tags.
    """
    return name.strip().lstrip("#").strip().lower()


def suggest_tags(prefix: str, existing: Iterable[str]) -> list[str]:
    """Bestehende Tags, die mit dem Getippten beginnen (beim Tippen vorschlagen)."""
    p = normalize_tag(prefix)
    if not p:
        return []
    return [t for t in existing if t.lower().startswith(p)]
