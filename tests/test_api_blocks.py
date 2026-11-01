"""API-Tests für Blöcke, Wochen- und Monatsansicht (M2)."""
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-04")  # Mittwoch
    with TestClient(create_app(tmp_path / "test.db")) as c:
        yield c


def quick(client, text, **kw):
    r = client.post("/api/quick", json={"text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def schedule(client, entry_id, day, start, end=None):
    return client.post(f"/api/entries/{entry_id}/schedule",
                       json={"day": day, "start_minute": start, "end_minute": end})


def test_schedule_creates_block_with_default_duration(client):
    e = quick(client, "Bericht", date="2026-11-04", estimated_minutes=90)["entry"]
    r = schedule(client, e["id"], "2026-11-04", 9 * 60)
    assert r.status_code == 200, r.text
    block = r.json()["block"]
    assert (block["day"], block["start_minute"], block["end_minute"]) == ("2026-11-04", 540, 630)
    assert block["start"] == "2026-11-04T09:00:00+01:00"
    # Der Block erscheint im Tag
    [entry] = client.get("/api/day").json()["entries"]
    assert entry["block"]["id"] == block["id"]


def test_schedule_week_entry_on_time_assigns_day(client):
    # V-2: Wochen-Eintrag auf eine Uhrzeit ziehen -> Tag zuweisen (R-6) und Block
    e = quick(client, "W", scope="week", date="2026-11-04")["entry"]
    r = schedule(client, e["id"], "2026-11-06", 600)
    assert r.json()["scope"] == "day"
    assert r.json()["period_start"] == "2026-11-06"
    assert r.json()["block"]["end_minute"] == 630


def test_schedule_existing_block_moves_it(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    b1 = schedule(client, e["id"], "2026-11-04", 540).json()["block"]
    b2 = schedule(client, e["id"], "2026-11-04", 600).json()["block"]
    assert b1["id"] == b2["id"]
    assert (b2["start_minute"], b2["end_minute"]) == (600, 630)


def test_move_block_to_other_day_moves_entry(client):
    # R-23
    e = quick(client, "X", date="2026-11-04")["entry"]
    b = schedule(client, e["id"], "2026-11-04", 540).json()["block"]
    r = client.patch(f"/api/blocks/{b['id']}",
                     json={"day": "2026-11-05", "start_minute": 600, "end_minute": 660})
    assert r.status_code == 200, r.text
    assert r.json()["period_start"] == "2026-11-05"
    assert r.json()["block"]["start_minute"] == 600
    assert client.get("/api/day").json()["entries"] == []


def test_block_on_past_day_for_open_entry_rejected(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    assert schedule(client, e["id"], "2026-11-03", 540).status_code == 400


def test_invalid_block_times_rejected(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    assert schedule(client, e["id"], "2026-11-04", 600, 590).status_code == 400
    assert schedule(client, e["id"], "2026-11-04", 1430, 1500).status_code == 400


def test_delete_block_keeps_entry(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    b = schedule(client, e["id"], "2026-11-04", 540).json()["block"]
    assert client.delete(f"/api/blocks/{b['id']}").status_code == 200
    [entry] = client.get("/api/day").json()["entries"]
    assert entry["block"] is None


def test_move_entry_with_block_to_other_day_keeps_time(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    schedule(client, e["id"], "2026-11-04", 540)
    r = client.patch(f"/api/entries/{e['id']}", json={"day": "2026-11-06"})
    assert r.json()["block"]["day"] == "2026-11-06"
    assert r.json()["block"]["start_minute"] == 540


def test_carry_over_deletes_block(client, monkeypatch):
    # R-12
    e = quick(client, "X", date="2026-11-04")["entry"]
    schedule(client, e["id"], "2026-11-04", 540)
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-05")
    [entry] = client.get("/api/day").json()["entries"]
    assert entry["overdue"] is True
    assert entry["block"] is None


def test_done_entry_keeps_block_on_its_day(client, monkeypatch):
    e = quick(client, "X", date="2026-11-04")["entry"]
    schedule(client, e["id"], "2026-11-04", 540)
    client.patch(f"/api/entries/{e['id']}", json={"done": True})
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-05")
    [entry] = client.get("/api/day", params={"date": "2026-11-04"}).json()["entries"]
    assert entry["block"]["start_minute"] == 540


def test_remove_entry_deletes_block(client):
    e = quick(client, "X", date="2026-11-04")["entry"]
    b = schedule(client, e["id"], "2026-11-04", 540).json()["block"]
    client.delete(f"/api/entries/{e['id']}")
    assert client.delete(f"/api/blocks/{b['id']}").status_code == 404


def test_week_view(client):
    quick(client, "W", scope="week", date="2026-11-04", tier="bonus")
    quick(client, "Mo", date="2026-11-02")  # gestern+ -> wird auf heute übertragen
    quick(client, "Fr", date="2026-11-06")
    quick(client, "Nächste Woche", date="2026-11-09")
    w = client.get("/api/week", params={"date": "2026-11-05"}).json()
    assert w["week_start"] == "2026-11-02"
    assert w["days"][0] == "2026-11-02" and w["days"][6] == "2026-11-08"
    assert [e["title"] for e in w["week_entries"]] == ["W"]
    assert {e["title"]: e["period_start"] for e in w["entries"]} == {
        "Mo": "2026-11-04", "Fr": "2026-11-06"}
    assert w["progress"]["all_total"] == 3


def test_month_view(client):
    quick(client, "A", date="2026-11-04")
    quick(client, "B", date="2026-11-04", tier="bonus")
    done = quick(client, "C", date="2026-11-04")["entry"]
    client.patch(f"/api/entries/{done['id']}", json={"done": True})
    e = quick(client, "D", date="2026-11-20")["entry"]
    schedule(client, e["id"], "2026-11-20", 600)
    m = client.get("/api/month", params={"date": "2026-11-15"}).json()
    assert m["month"] == "2026-11"
    days = {d["date"]: d for week in m["weeks"] for d in week}
    assert m["weeks"][0][0]["date"] == "2026-10-26"  # Montag vor dem 1.11.
    assert all(len(w) == 7 for w in m["weeks"])
    assert days["2026-11-04"]["open_must"] == 1
    assert days["2026-11-20"]["blocks"] == 1
    assert days["2026-10-26"]["in_month"] is False


# --- M4: Fremdtermine in den Ansichten (S-4, R-20) ---------------------------

def add_event(client, title, day, start_h, end_h, all_day=False, cal="privat"):
    """Termin direkt in den Zwischenspeicher legen (wie nach einem Abgleich)."""
    from datetime import date as d, datetime, time
    from backend.config import TIMEZONE
    from backend.db import repository as repo
    from backend.db.connection import connect
    from backend.domain.external import ExternalEvent
    conn = connect(client.app.state.db_path)
    repo.save_calendars(conn, [{"id": cal, "summary": cal}])
    repo.set_calendar_selected(conn, cal, True)
    day = d.fromisoformat(day)
    ev = ExternalEvent(cal, title, title,
                       datetime.combine(day, time(start_h), TIMEZONE),
                       datetime.combine(day, time(end_h % 24), TIMEZONE) if end_h < 24 else
                       datetime.combine(d.fromordinal(day.toordinal() + 1), time(0), TIMEZONE),
                       all_day)
    repo.save_external_events(conn, [ev], set())
    conn.commit()
    conn.close()


def test_events_in_day_and_week_view(client):
    add_event(client, "Zahnarzt", "2026-11-04", 9, 10)
    add_event(client, "Geburtstag", "2026-11-04", 0, 24, all_day=True)
    d = client.get("/api/day").json()
    assert [(e["title"], e["start_minute"], e["end_minute"], e["all_day"]) for e in d["events"]] == [
        ("Geburtstag", 0, 1440, True), ("Zahnarzt", 540, 600, False)]
    w = client.get("/api/week").json()
    assert [e["day"] for e in w["events"] if e["title"] == "Zahnarzt"] == ["2026-11-04"]


def test_block_overlap_is_marked(client):
    # R-20: erlaubt, aber markiert
    add_event(client, "Zahnarzt", "2026-11-04", 9, 10)
    e1 = quick(client, "Überschneidet", date="2026-11-04")["entry"]
    e2 = quick(client, "Frei", date="2026-11-04")["entry"]
    schedule(client, e1["id"], "2026-11-04", 9 * 60 + 30)
    schedule(client, e2["id"], "2026-11-04", 11 * 60)
    flags = {e["title"]: e["conflict"] for e in client.get("/api/day").json()["entries"]}
    assert flags == {"Überschneidet": True, "Frei": False}


def test_month_counts_events(client):
    add_event(client, "Zahnarzt", "2026-11-20", 9, 10)
    m = client.get("/api/month", params={"date": "2026-11-15"}).json()
    days = {d["date"]: d for w in m["weeks"] for d in w}
    assert days["2026-11-20"]["events"] == 1


def test_unselected_calendar_not_shown(client):
    add_event(client, "Arbeit", "2026-11-04", 9, 10, cal="arbeit")
    from backend.db import repository as repo
    from backend.db.connection import connect
    conn = connect(client.app.state.db_path)
    repo.set_calendar_selected(conn, "arbeit", False)
    conn.commit()
    conn.close()
    assert client.get("/api/day").json()["events"] == []
