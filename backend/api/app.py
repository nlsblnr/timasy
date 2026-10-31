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
from pydantic import BaseModel, Field

from .. import clock, services
from ..config import FRONTEND_DIST
from ..db import repository as repo
from ..db.connection import connect, init_db
from ..domain.models import Scope, Tier


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
    day: dt.date | None = None       # Wochen-Eintrag einem Tag zuweisen (R-6)


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
        services.roll_over(conn, today)
        return services.day_view(conn, date or today, today)

    @app.get("/api/backlog")
    def get_backlog(conn: sqlite3.Connection = Depends(get_conn)):
        services.roll_over(conn, clock.today())
        return {"tasks": services.backlog(conn)}

    @app.get("/api/tags")
    def get_tags(conn: sqlite3.Connection = Depends(get_conn)):
        return repo.all_tags(conn)

    @app.post("/api/quick")
    def post_quick(body: QuickIn, conn: sqlite3.Connection = Depends(get_conn)):
        def do():
            task_id, entry = services.quick_capture(
                conn, body.text, clock.now(), body.tier, body.scope, body.date,
                body.notes, body.estimated_minutes, body.tags)
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
            e = services.change_entry(conn, entry_id, clock.now(), body.done, body.tier, body.day)
            return services.entry_payloads(conn, [e], clock.today())[0]
        return run(do)

    @app.delete("/api/entries/{entry_id}")
    def delete_entry(entry_id: int, conn: sqlite3.Connection = Depends(get_conn)):
        run(lambda: services.remove_entry(conn, entry_id))
        return {"ok": True}

    # Das gebaute Frontend (npm run build) unter "/" ausliefern.
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app
