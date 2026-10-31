"""Schnellerfassung (V-7): Titel eingeben, '#name' fügt einen Tag hinzu."""
import re

from .tags import normalize_tag

# '#' gefolgt von Buchstaben, Ziffern, '_' oder '-' (\w erfasst auch Umlaute)
_TAG_PATTERN = re.compile(r"(?<!\S)#([\w-]+)")


def parse_quick_input(text: str) -> tuple[str, list[str]]:
    """Zerlegt die Eingabe in Titel und Tags.

    "Bericht #arbeit schreiben" -> ("Bericht schreiben", ["arbeit"])
    """
    tags: list[str] = []
    for raw in _TAG_PATTERN.findall(text):
        tag = normalize_tag(raw)
        if tag and tag not in tags:
            tags.append(tag)
    title = _TAG_PATTERN.sub("", text)
    title = " ".join(title.split())  # doppelte Leerzeichen entfernen
    return title, tags
