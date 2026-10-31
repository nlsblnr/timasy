"""Tests für die Schnellerfassung (V-7) und Tags (R-22)."""
from backend.domain.quick_capture import parse_quick_input
from backend.domain.tags import normalize_tag, suggest_tags


def test_plain_title():
    assert parse_quick_input("Bericht schreiben") == ("Bericht schreiben", [])


def test_hashtags_become_tags_and_are_removed_from_title():
    title, tags = parse_quick_input("Bericht #arbeit schreiben #Wichtig")
    assert title == "Bericht schreiben"
    assert tags == ["arbeit", "wichtig"]


def test_duplicate_tags_once():
    assert parse_quick_input("A #x #X")[1] == ["x"]


def test_umlauts_and_dashes_in_tags():
    assert parse_quick_input("Einkauf #gärten #haus-bau")[1] == ["gärten", "haus-bau"]


def test_lone_hash_stays_in_title():
    assert parse_quick_input("Ticket # 12") == ("Ticket # 12", [])


def test_normalize_tag():
    assert normalize_tag("  #Arbeit ") == "arbeit"
    assert normalize_tag("#") == ""


def test_suggest_tags_by_prefix():
    existing = ["arbeit", "haushalt", "Arzt", "garten"]
    assert suggest_tags("ar", existing) == ["arbeit", "Arzt"]
    assert suggest_tags("", existing) == []
