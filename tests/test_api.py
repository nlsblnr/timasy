"""Durchgehende Tests über die JSON-Schnittstelle mit echter (temporärer) Datenbank.

Sie prüfen vor allem das Abnahmekriterium von M1: erfassen, auf heute setzen,
abhaken, Fortschritt, simulierter Tageswechsel.
"""
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-04")  # Mittwoch
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def set_today(monkeypatch, iso):
    monkeypatch.setenv("TIMASY_TODAY", iso)


def quick(client, text, **kw):
    r = client.post("/api/quick", json={"text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def day(client, iso=None):
    r = client.get("/api/day", params={"date": iso} if iso else {})
    assert r.status_code == 200, r.text
    return r.json()


def test_server_reports_today(client):
    assert day(client)["today"] == "2026-11-04"
    assert day(client)["date"] == "2026-11-04"


def test_acceptance_capture_assign_check_progress(client):
    # Aufgabe erfassen und als Pflicht bzw. Bonus auf heute setzen
    a = quick(client, "Bericht schreiben #arbeit", date="2026-11-04")
    quick(client, "Joggen", date="2026-11-04", tier="bonus")
    assert a["entry"]["tier"] == "must"  # Standardstufe Pflicht (V-7)
    assert a["task"]["tags"] == ["arbeit"]

    d = day(client)
    assert [e["title"] for e in d["entries"]] == ["Bericht schreiben", "Joggen"]
    assert d["progress"]["must_total"] == 1
    assert d["progress"]["minimum_reached"] is False

    # abhaken
    r = client.patch(f"/api/entries/{a['entry']['id']}", json={"done": True})
    assert r.json()["status"] == "done"
    p = day(client)["progress"]
    assert (p["must_done"], p["must_total"], p["all_done"], p["all_total"]) == (1, 1, 1, 2)
    assert p["minimum_reached"] is True

    # rückgängig (R-7)
    client.patch(f"/api/entries/{a['entry']['id']}", json={"done": False})
    assert day(client)["progress"]["must_done"] == 0


def test_acceptance_simulated_day_change(client, monkeypatch):
    quick(client, "Offen", date="2026-11-04")
    done = quick(client, "Erledigt", date="2026-11-04")
    client.patch(f"/api/entries/{done['entry']['id']}", json={"done": True})
    quick(client, "Bonus offen", date="2026-11-04", tier="bonus")

    set_today(monkeypatch, "2026-11-06")  # zwei Tage später
    d = day(client)
    titles = {e["title"]: e for e in d["entries"]}
    assert set(titles) == {"Offen", "Bonus offen"}
    assert titles["Offen"]["overdue"] is True
    assert titles["Offen"]["overdue_since"] == "2026-11-04"
    assert titles["Offen"]["overdue_days"] == 2
    assert titles["Offen"]["tier"] == "must"
    assert titles["Bonus offen"]["tier"] == "bonus"
    # erledigter Eintrag bleibt am alten Tag
    assert [e["title"] for e in day(client, "2026-11-04")["entries"]] == ["Erledigt"]


def test_week_entries_carry_over(client, monkeypatch):
    r = quick(client, "Steuern", scope="week", date="2026-11-04")
    assert r["entry"]["period_start"] == "2026-11-02"
    set_today(monkeypatch, "2026-11-10")
    d = day(client)
    assert d["week_start"] == "2026-11-09"
    [w] = d["week_entries"]
    assert w["period_start"] == "2026-11-09"
    assert w["overdue"] is True


def test_quick_without_date_creates_backlog_task(client):
    quick(client, "Irgendwann #haus")
    tasks = client.get("/api/backlog").json()["tasks"]
    assert [t["title"] for t in tasks] == ["Irgendwann"]
    assert tasks[0]["tags"] == ["haus"]


def test_assign_from_backlog_and_remove_again(client):
    t = quick(client, "Später")["task"]
    r = client.post("/api/entries", json={"task_id": t["id"], "scope": "day",
                                          "period_start": "2026-11-05", "tier": "bonus"})
    assert r.status_code == 200
    assert client.get("/api/backlog").json()["tasks"] == []
    # Eine Aufgabe hat höchstens einen offenen Eintrag
    r2 = client.post("/api/entries", json={"task_id": t["id"], "scope": "day",
                                           "period_start": "2026-11-06", "tier": "must"})
    assert r2.status_code == 409
    # R-8: aus Zeitraum entfernen -> zurück in den Backlog
    client.delete(f"/api/entries/{r.json()['id']}")
    assert [x["title"] for x in client.get("/api/backlog").json()["tasks"]] == ["Später"]


def test_done_task_not_in_backlog(client):
    e = quick(client, "Fertig", date="2026-11-04")["entry"]
    client.patch(f"/api/entries/{e['id']}", json={"done": True})
    assert client.get("/api/backlog").json()["tasks"] == []


def test_week_entry_to_day(client):
    # R-6
    w = quick(client, "Wocheneintrag", scope="week", date="2026-11-04", tier="bonus")["entry"]
    r = client.patch(f"/api/entries/{w['id']}", json={"day": "2026-11-05"})
    assert r.status_code == 200
    assert r.json()["scope"] == "day" and r.json()["tier"] == "bonus"
    assert r.json()["id"] == w["id"]
    assert day(client)["week_entries"] == []
    assert [e["title"] for e in day(client, "2026-11-05")["entries"]] == ["Wocheneintrag"]


def test_week_entry_to_day_of_other_week_rejected(client):
    w = quick(client, "W", scope="week", date="2026-11-04")["entry"]
    r = client.patch(f"/api/entries/{w['id']}", json={"day": "2026-11-12"})
    assert r.status_code == 400


def test_change_tier(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    r = client.patch(f"/api/entries/{e['id']}", json={"tier": "bonus"})
    assert r.json()["tier"] == "bonus"


def test_week_progress_in_day_view(client):
    # R-4
    quick(client, "W", scope="week", date="2026-11-04")
    e = quick(client, "T", date="2026-11-03")["entry"]  # gestern -> wird übertragen
    client.patch(f"/api/entries/{e['id']}", json={"done": True})
    wp = day(client)["week_progress"]
    assert (wp["must_done"], wp["must_total"]) == (1, 2)


def test_edit_and_delete_task(client):
    t = quick(client, "Alt #a")["task"]
    r = client.put(f"/api/tasks/{t['id']}", json={"title": "Neu", "notes": "Notiz",
                                                   "estimated_minutes": 45, "tags": ["b", "#C"]})
    assert r.status_code == 200
    assert r.json()["tags"] == ["b", "c"]
    assert client.get("/api/tags").json() == ["b", "c"]  # "a" wird nicht mehr gebraucht
    client.delete(f"/api/tasks/{t['id']}")
    assert client.get("/api/backlog").json()["tasks"] == []
    assert client.get("/api/tags").json() == []


def test_validation(client):
    assert client.post("/api/quick", json={"text": "  #nurtag "}).status_code == 400
    assert client.patch("/api/entries/999", json={"done": True}).status_code == 404
    assert client.put("/api/tasks/999", json={"title": "x"}).status_code == 404
