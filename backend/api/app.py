"""JSON-Schnittstelle (FastAPI) für das Frontend.

Neues Konzept: FastAPI ruft für jede Anfrage die passende Funktion auf
(z.B. GET /api/day -> get_day). Die Klassen mit BaseModel beschreiben, wie
der JSON-Inhalt einer Anfrage aussehen muss; FastAPI prüft das automatisch
und antwortet bei Fehlern mit Status 422.
"""
import sqlite3
from contextlib import asynccontextmanager
import datetime as dt
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from .. import clock, services
from ..config import FRONTEND_DIST
from ..db import repository as repo
from ..db.connection import connect, init_db
from ..domain.models import Scope, Tier
from ..domain.series import EndType, Freq, MonthlyBy


# --- Formate der Anfragen ----------------------------------------------------

class QuickIn(BaseModel):
    text: str
    tier: Tier = Tier.MUST           # Standardstufe Pflicht (V-7)
    scope: Scope = Scope.DAY
    date: dt.date | None = None      # ohne Datum: Aufgabe im Backlog
    # aus dem erweiterten Dialog (V-7)
    notes: str = ""
    estimated_minutes: int | None = Field(default=None, ge=1)
    tags: list[str] = []
    start_minute: int | None = None  # Uhrzeit -> Block


class TaskIn(BaseModel):
    title: str
    notes: str = ""
    estimated_minutes: int | None = Field(default=None, ge=1)
    tags: list[str] = []


class EntryIn(BaseModel):
    task_id: int
    scope: Scope
    period_start: dt.date
    tier: Tier


class EntryPatch(BaseModel):
    done: bool | None = None
    tier: Tier | None = None
    day: dt.date | None = None       # auf einen Tag legen (bei Wochen-Einträgen R-6)


class ScheduleIn(BaseModel):
    """Zeit als Tag + Minuten seit Mitternacht in Ortszeit, z.B. 9:15 = 555."""
    day: dt.date
    start_minute: int
    end_minute: int | None = None    # ohne Ende: Standarddauer (R-21)


class SeriesIn(BaseModel):
    """Neue Serie (V-8). Wochentage: 0 = Montag bis 6 = Sonntag."""
    text: str = ""
    notes: str = ""
    estimated_minutes: int | None = Field(default=None, ge=1)
    tags: list[str] = []
    tier: Tier = Tier.MUST
    scope: Scope = Scope.DAY
    starts_on: dt.date
    freq: Freq
    interval: int = 1
    weekdays: list[int] = []
    monthly_by: MonthlyBy = MonthlyBy.DAY
    end_type: EndType = EndType.NEVER
    until_date: dt.date | None = None
    count: int | None = None
    start_minute: int | None = None
    duration_minutes: int | None = Field(default=None, ge=1)
    carry_over: bool = False


class OccurrenceEdit(BaseModel):
    """R-17: Vorkommen bearbeiten. Nur mitgeschickte Felder werden geändert."""
    mode: Literal["this", "following", "all"] = "all"
    title: str | None = None
    notes: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    tags: list[str] | None = None
    tier: Tier | None = None
    day: dt.date | None = None             # nur "this"
    start_minute: int | None = None        # None mitschicken = Uhrzeit entfernen
    duration_minutes: int | None = Field(default=None, ge=1)
    starts_on: dt.date | None = None       # nur "all"
    freq: Freq | None = None
    interval: int | None = None
    weekdays: list[int] | None = None
    monthly_by: MonthlyBy | None = None
    end_type: EndType | None = None
    until_date: dt.date | None = None
    count: int | None = None
    carry_over: bool | None = None


class SeriesPatch(BaseModel):
    carry_over: bool


class BlockPatch(BaseModel):
    day: dt.date
    start_minute: int
    end_minute: int


# --- App ---------------------------------------------------------------------

def create_app(db_path: Path | str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        init_db(db_path)  # Migrationen beim Start
        yield

    app = FastAPI(title="Timasy", lifespan=lifespan)

    def get_conn():
        """Eine Verbindung pro Anfrage; am Ende wird gespeichert (commit)."""
        conn = connect(db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def run(fn):
        """Fehler aus der Service-Schicht in HTTP-Antworten übersetzen."""
        try:
            return fn()
        except services.NotFound:
            raise HTTPException(404, "Nicht gefunden.")
        except services.Conflict as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/day")
    def get_day(date: dt.date | None = None, conn: sqlite3.Connection = Depends(get_conn)):
        today = clock.today()
        services.refresh(conn, today, clock.now())
        return services.day_view(conn, date or today, today)

    @app.get("/api/backlog")
    def get_backlog(conn: sqlite3.Connection = Depends(get_conn)):
        services.refresh(conn, clock.today(), clock.now())
        return {"tasks": services.backlog(conn)}

    @app.get("/api/tags")
    def get_tags(conn: sqlite3.Connection = Depends(get_conn)):
        return repo.all_tags(conn)

    @app.post("/api/quick")
    def post_quick(body: QuickIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            task_id, entry = services.quick_capture(
                conn, body.text, clock.now(), body.tier, body.scope, body.date,
                body.notes, body.estimated_minutes, body.tags, body.start_minute, clock.today())
            return {
                "task": services.task_payload(conn, task_id),
                "entry": services.entry_payloads(conn, [entry], clock.today())[0] if entry else None,
            }
        return run(do)

    @app.post("/api/tasks")
    def post_task(body: TaskIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            task_id = services.create_task(conn, body.title, clock.now(), body.notes,
                                           body.estimated_minutes, body.tags)
            return services.task_payload(conn, task_id)
        return run(do)

    @app.put("/api/tasks/{task_id}")
    def put_task(task_id: int, body: TaskIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            services.update_task(conn, task_id, body.title, body.notes,
                                 body.estimated_minutes, body.tags)
            return services.task_payload(conn, task_id)
        return run(do)

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.delete_task(conn, task_id))
        return {"ok": True}

    @app.post("/api/entries")
    def post_entry(body: EntryIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            e = services.create_entry(conn, body.task_id, body.scope, body.period_start, body.tier)
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.patch("/api/entries/{entry_id}")
    def patch_entry(entry_id: int, body: EntryPatch, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            e = services.change_entry(conn, entry_id, clock.now(), clock.today(),
                                      body.done, body.tier, body.day)
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.delete("/api/entries/{entry_id}")
    def delete_entry(entry_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.remove_entry(conn, entry_id))
        return {"ok": True}

    @app.get("/api/week")
    def get_week(date: dt.date | None = None, conn: sqlite3.Connection = Depends(get_conn)):
        today = clock.today()
        services.refresh(conn, today, clock.now())
        return services.week_view(conn, date or today, today)

    @app.get("/api/month")
    def get_month(date: dt.date | None = None, conn: sqlite3.Connection = Depends(get_conn)):
        today = clock.today()
        services.refresh(conn, today, clock.now())
        return services.month_view(conn, date or today, today)

    @app.post("/api/entries/{entry_id}/schedule")
    def post_schedule(entry_id: int, body: ScheduleIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            e = services.schedule_entry(conn, entry_id, body.day, body.start_minute,
                                        body.end_minute, clock.today(), clock.now())
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.patch("/api/blocks/{block_id}")
    def patch_block(block_id: int, body: BlockPatch, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            e = services.change_block(conn, block_id, body.day, body.start_minute,
                                      body.end_minute, clock.today(), clock.now())
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.delete("/api/blocks/{block_id}")
    def delete_block(block_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.remove_block(conn, block_id))
        return {"ok": True}

    # --- Serien (M3) -----------------------------------------------------------

    @app.get("/api/series")
    def get_series_list(conn: sqlite3.Connection = Depends(get_conn)):
        services.refresh(conn, clock.today(), clock.now())
        return services.list_series(conn, clock.today())

    @app.get("/api/series/{series_id}")
    def get_series(series_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        return run(lambda: services.series_payload(
            conn, services.get_series(conn, series_id), clock.today()))

    @app.post("/api/series")
    def post_series(body: SeriesIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            s = services.create_series(conn, body.model_dump(), clock.today(), clock.now())
            return services.series_payload(conn, s, clock.today())
        return run(do)

    @app.post("/api/series/preview")
    def post_series_preview(body: SeriesIn):
        return run(lambda: [d.isoformat() for d in services.preview_series(body.model_dump())])

    @app.patch("/api/series/{series_id}")
    def patch_series(series_id: int, body: SeriesPatch, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            s = services.set_carry_over(conn, series_id, body.carry_over)
            return services.series_payload(conn, s, clock.today())
        return run(do)

    @app.put("/api/series/{series_id}")
    def put_series(series_id: int, body: OccurrenceEdit, conn: sqlite3.Connection = Depends(get_conn)):
        """Serie direkt bearbeiten (V-5); entspricht "alle" (R-17)."""
        def do():
            data = body.model_dump(include=body.model_fields_set - {"mode", "day"})
            s = services.edit_series(conn, services.get_series(conn, series_id), data,
                                     clock.today(), clock.now())
            return services.series_payload(conn, s, clock.today())
        return run(do)

    @app.post("/api/series/{series_id}/end")
    def post_series_end(series_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            s = services.end_series_now(conn, series_id, clock.today())
            return services.series_payload(conn, s, clock.today())
        return run(do)

    @app.delete("/api/series/{series_id}")
    def delete_series(series_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.delete_series(conn, series_id))
        return {"ok": True}

    @app.put("/api/entries/{entry_id}/occurrence")
    def put_occurrence(entry_id: int, body: OccurrenceEdit, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            # Nur Felder weitergeben, die wirklich mitgeschickt wurden
            data = body.model_dump(include=body.model_fields_set - {"mode"})
            e = services.edit_occurrence(conn, entry_id, body.mode, data, clock.today(), clock.now())
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.delete("/api/entries/{entry_id}/occurrence")
    def delete_occurrence(entry_id: int, mode: Literal["this", "following", "all"],
                          conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.delete_occurrence(conn, entry_id, mode, clock.today()))
        return {"ok": True}

    # Das gebaute Frontend (npm run build) unter "/" ausliefern.
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app
