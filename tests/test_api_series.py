"""API-Tests für Serien (M3): Erzeugen, R-13, R-16, R-17 (drei Bearbeitungsarten), V-5."""
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-02")  # Montag
    with TestClient(create_app(tmp_path / "test.db")) as c:
        yield c


def create(client, **kw):
    body = dict(text="Joggen #sport", tier="must", scope="day", starts_on="2026-11-02",
                freq="daily", end_type="count", count=14)
    body.update(kw)
    r = client.post("/api/series", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def day(client, iso):
    return client.get("/api/day", params={"date": iso}).json()["entries"]


def series_entries(client, first="2026-11-02", last="2027-03-31"):
    """Alle Tages-Einträge im Zeitraum, nach Datum."""
    out = {}
    from datetime import date, timedelta
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        w = client.get("/api/week", params={"date": d.isoformat()}).json()
        for e in w["entries"] + w["week_entries"]:
            out[e["id"]] = e
        d += timedelta(days=7)
    return sorted(out.values(), key=lambda e: (e["period_start"], e["id"]))


def test_daily_14_times_creates_14_entries(client):
    s = create(client)
    entries = series_entries(client)
    assert len(entries) == 14
    assert entries[0]["period_start"] == "2026-11-02"
    assert entries[-1]["period_start"] == "2026-11-15"
    assert all(e["series_id"] == s["id"] for e in entries)
    assert entries[0]["task"]["tags"] == ["sport"]
    assert entries[0]["title"] == "Joggen"


def test_weekly_until_29_december(client):
    create(client, freq="weekly", starts_on="2026-11-03", end_type="until",
           until_date="2026-12-29", count=None)
    dates = [e["period_start"] for e in series_entries(client)]
    assert dates[0] == "2026-11-03" and dates[-1] == "2026-12-29" and len(dates) == 9


def test_horizon_90_days_and_top_up(client, monkeypatch):
    # R-16
    create(client, end_type="never", count=None)
    assert len(series_entries(client)) == 91          # 2.11.2026 bis 31.1.2027
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-12")
    entries = series_entries(client, "2026-11-02", "2027-03-31")
    assert entries[-1]["period_start"] == "2027-02-10"  # nachgezogen bis heute + 90


def test_series_with_time_creates_blocks(client):
    create(client, start_minute=7 * 60, duration_minutes=45, count=3)
    [e] = day(client, "2026-11-03")
    assert (e["block"]["start_minute"], e["block"]["end_minute"]) == (420, 465)


def test_week_series(client):
    create(client, scope="week", freq="weekly", interval=2, count=3, starts_on="2026-11-04")
    w = client.get("/api/week", params={"date": "2026-11-16"}).json()
    assert [e["period_start"] for e in w["week_entries"]] == ["2026-11-16"]


def test_week_series_with_daily_rejected(client):
    r = client.post("/api/series", json=dict(text="X", tier="must", scope="week",
                    starts_on="2026-11-02", freq="daily", end_type="never"))
    assert r.status_code == 400


def test_missed_and_carry_over(client, monkeypatch):
    # R-13
    s = create(client, count=3)
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-03")
    assert [e["title"] for e in day(client, "2026-11-03")] == ["Joggen"]
    [old] = day(client, "2026-11-02")
    assert old["status"] == "missed"
    # mit carry_over wird übertragen
    client.patch(f"/api/series/{s['id']}", json={"carry_over": True})
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-04")
    today = day(client, "2026-11-04")
    assert len(today) == 2
    assert sorted(e["overdue"] for e in today) == [False, True]


def test_preview(client):
    r = client.post("/api/series/preview", json=dict(
        starts_on="2026-11-02", freq="weekly", weekdays=[1, 3], end_type="never", scope="day"))
    assert r.json() == ["2026-11-03", "2026-11-05", "2026-11-10", "2026-11-12", "2026-11-17"]


# --- R-17: drei Bearbeitungsarten ------------------------------------------

def edit(client, entry_id, mode, **changes):
    r = client.put(f"/api/entries/{entry_id}/occurrence", json={"mode": mode, **changes})
    assert r.status_code == 200, r.text
    return r.json()


def by_date(client):
    return {e["period_start"]: e for e in series_entries(client)}


def test_edit_only_this_occurrence(client):
    create(client, count=5)
    e = by_date(client)["2026-11-04"]
    edit(client, e["id"], "this", title="Intervalle", tier="bonus", start_minute=18 * 60)
    entries = by_date(client)
    assert entries["2026-11-04"]["title"] == "Intervalle"
    assert entries["2026-11-04"]["tier"] == "bonus"
    assert entries["2026-11-04"]["is_exception"] is True
    assert entries["2026-11-04"]["block"]["start_minute"] == 18 * 60
    assert entries["2026-11-05"]["title"] == "Joggen"       # übrige unverändert
    assert entries["2026-11-05"]["tier"] == "must"


def test_edit_this_and_following_splits_series(client):
    s = create(client, count=6)                 # 2.11. bis 7.11.
    e = by_date(client)["2026-11-05"]
    edit(client, e["id"], "following", title="Laufen", tier="bonus")
    entries = by_date(client)
    assert len(entries) == 6                    # Gesamtzahl bleibt
    assert [entries[d]["title"] for d in sorted(entries)] == ["Joggen"] * 3 + ["Laufen"] * 3
    assert entries["2026-11-07"]["tier"] == "bonus"
    assert entries["2026-11-05"]["series_id"] != s["id"]
    assert len(client.get("/api/series").json()) == 2


def test_edit_all_keeps_exceptions(client):
    create(client, count=5)
    exc = by_date(client)["2026-11-04"]
    edit(client, exc["id"], "this", title="Ausnahme")
    edit(client, by_date(client)["2026-11-03"]["id"], "all", title="Laufen", tier="bonus",
         start_minute=6 * 60, duration_minutes=30)
    entries = by_date(client)
    assert len(entries) == 5
    assert entries["2026-11-04"]["title"] == "Ausnahme"      # Ausnahme bleibt
    assert entries["2026-11-04"]["block"] is None
    assert entries["2026-11-06"]["title"] == "Laufen"
    assert entries["2026-11-06"]["tier"] == "bonus"
    assert entries["2026-11-06"]["block"]["start_minute"] == 360


def test_edit_all_keeps_done_and_changes_pattern(client):
    create(client, count=5)
    first = by_date(client)["2026-11-02"]
    client.patch(f"/api/entries/{first['id']}", json={"done": True})
    edit(client, first["id"], "all", title="Joggen", freq="weekly", weekdays=[0, 2],
         end_type="never")
    dates = sorted(by_date(client))
    assert dates[:4] == ["2026-11-02", "2026-11-04", "2026-11-09", "2026-11-11"]
    assert by_date(client)["2026-11-02"]["status"] == "done"


# --- Löschen (R-17, R-28) --------------------------------------------------

def test_delete_only_this(client, monkeypatch):
    create(client, count=5)
    e = by_date(client)["2026-11-04"]
    assert client.delete(f"/api/entries/{e['id']}/occurrence", params={"mode": "this"}).status_code == 200
    assert "2026-11-04" not in by_date(client)
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-03")       # wird nicht neu erzeugt
    assert "2026-11-04" not in by_date(client)


def test_remove_from_period_deletes_only_this(client):
    # R-27
    create(client, count=3)
    e = by_date(client)["2026-11-03"]
    client.delete(f"/api/entries/{e['id']}")
    assert sorted(by_date(client)) == ["2026-11-02", "2026-11-04"]
    assert client.get("/api/backlog").json()["tasks"] == []


def test_delete_this_and_following(client):
    create(client, count=5)
    e = by_date(client)["2026-11-04"]
    client.delete(f"/api/entries/{e['id']}/occurrence", params={"mode": "following"})
    assert sorted(by_date(client)) == ["2026-11-02", "2026-11-03"]


def test_delete_all_keeps_done(client):
    create(client, count=5)
    first = by_date(client)["2026-11-02"]
    client.patch(f"/api/entries/{first['id']}", json={"done": True})
    client.delete(f"/api/entries/{first['id']}/occurrence", params={"mode": "all"})
    assert list(by_date(client)) == ["2026-11-02"]
    assert client.get("/api/series").json() == []


def test_drag_makes_exception(client):
    # R-27: Block ziehen = nur dieses Vorkommen
    create(client, count=3, start_minute=420, duration_minutes=30)
    e = by_date(client)["2026-11-03"]
    client.patch(f"/api/blocks/{e['block']['id']}",
                 json={"day": "2026-11-03", "start_minute": 480, "end_minute": 510})
    assert by_date(client)["2026-11-03"]["is_exception"] is True
    assert by_date(client)["2026-11-04"]["is_exception"] is False


# --- V-5: Serien-Liste, beenden ---------------------------------------------

def test_series_list_and_end(client, monkeypatch):
    s = create(client, end_type="never", count=None)
    [listed] = client.get("/api/series").json()
    assert listed["title"] == "Joggen"
    assert listed["freq"] == "daily"
    assert listed["next_occurrence"] == "2026-11-02"
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-05")
    r = client.post(f"/api/series/{s['id']}/end")
    assert r.json()["until_date"] == "2026-11-05"
    dates = sorted(by_date(client))
    assert dates[-1] == "2026-11-05"                     # ab morgen entfernt (R-26)


def test_series_task_not_in_backlog(client, monkeypatch):
    create(client, count=1)
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-05")    # Vorkommen verpasst
    assert client.get("/api/backlog").json()["tasks"] == []


def test_quick_with_time_creates_block(client):
    # V-7: Uhrzeit im erweiterten Dialog
    r = client.post("/api/quick", json={"text": "Arzt", "date": "2026-11-03", "start_minute": 600})
    assert r.json()["entry"]["block"]["start_minute"] == 600


def test_edit_series_directly(client):
    # V-5: Serie in der Liste bearbeiten = "alle"
    s = create(client, count=3)
    r = client.put(f"/api/series/{s['id']}", json={"title": "Laufen", "tier": "bonus", "count": 4})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Laufen" and r.json()["count"] == 4
    entries = by_date(client)
    assert len(entries) == 4 and entries["2026-11-05"]["tier"] == "bonus"
