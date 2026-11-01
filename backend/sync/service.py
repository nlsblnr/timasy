"""Abgleich im Hintergrund (S-9, S-10).

Neues Konzept "Thread": ein zweiter Ablauf, der neben dem Webserver läuft.
Er gleicht beim Start ab, danach alle 5 Minuten und sofort, wenn jemand
"Jetzt synchronisieren" drückt (trigger). Bei Fehlern wartet er zuerst 1
Minute, dann 2, 4 … bis höchstens zum normalen Intervall (S-10).
Die App bleibt dabei voll nutzbar; der Zustand ist über status() abrufbar.
"""
import threading
from pathlib import Path
from typing import Callable

from .. import clock
from ..db.connection import connect
from .errors import AuthExpired, NotConfigured, NotConnected
from .read import CalendarClient, ensure_timasy_calendar, sync_calendar_list, sync_external

FIRST_RETRY_SECONDS = 60


def default_client_factory() -> CalendarClient:
    # Erst hier importieren: Tests und App ohne Google-Bibliotheken bleiben schnell
    from .google_client import open_client
    return open_client()


class SyncService:
    def __init__(self, db_path: Path | str, client_factory: Callable[[], CalendarClient] = default_client_factory,
                 interval_minutes: int = 5):
        self.db_path = db_path
        self.client_factory = client_factory
        self.interval_seconds = interval_minutes * 60
        self._state = "idle"
        self._last_synced_at: str | None = None
        self._last_error: str | None = None
        self._failures = 0
        self._wakeup = threading.Event()
        self._lock = threading.Lock()   # nie zwei Abgleiche gleichzeitig
        self._thread: threading.Thread | None = None
        self._stop = False

    # --- Zustand ---------------------------------------------------------------

    def status(self) -> dict:
        """state: idle | syncing | ok | error | not_configured | disconnected |
        reconnect | connecting"""
        return {
            "state": self._state,
            "last_synced_at": self._last_synced_at,
            "last_error": self._last_error,
            "interval_minutes": self.interval_seconds // 60,
        }

    def next_wait_seconds(self) -> int:
        """Wartezeit bis zum nächsten Versuch (wächst nach Fehlern, S-10)."""
        if self._failures == 0:
            return self.interval_seconds
        return min(FIRST_RETRY_SECONDS * 2 ** (self._failures - 1), self.interval_seconds)

    # --- Abgleich ----------------------------------------------------------------

    def run_once(self) -> None:
        with self._lock:
            previous = self._state
            self._state = "syncing"
            try:
                client = self.client_factory()
                conn = connect(self.db_path)
                try:
                    ensure_timasy_calendar(conn, client)
                    sync_calendar_list(conn, client)
                    sync_external(conn, client, clock.today(), clock.now())
                    conn.commit()
                finally:
                    conn.close()
            except NotConfigured:
                self._set("not_configured")
            except NotConnected:
                self._set("disconnected")
            except AuthExpired:
                self._set("reconnect")
            except Exception as e:  # Netz weg, Google-Fehler …: später erneut versuchen
                self._failures += 1
                self._state = "error"
                # Nur die Meldung, nie Zugangsdaten (T-8)
                self._last_error = f"{type(e).__name__}: {e}"[:300]
            else:
                self._failures = 0
                self._last_error = None
                self._state = "ok"
                self._last_synced_at = clock.now().isoformat(timespec="seconds")
            if self._state == "syncing":  # sollte nicht vorkommen
                self._state = previous

    def _set(self, state: str) -> None:
        self._state = state
        self._failures = 0
        self._last_error = None

    # --- Hintergrund ---------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="timasy-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self._wakeup.set()

    def trigger(self) -> None:
        """Sofort abgleichen ("Jetzt synchronisieren", S-9)."""
        self._wakeup.set()

    def _loop(self) -> None:
        while not self._stop:
            self.run_once()
            self._wakeup.wait(self.next_wait_seconds())
            self._wakeup.clear()

    def connect_google(self) -> None:
        """Anmeldung im Browser starten (läuft im Hintergrund, S-1)."""
        def work():
            from .google_client import connect_interactive
            self._state = "connecting"
            try:
                connect_interactive()
            except Exception as e:
                self._state = "error"
                self._last_error = f"Anmeldung fehlgeschlagen: {type(e).__name__}: {e}"[:300]
                return
            self._state = "idle"
            self.trigger()
            if self._thread is None:   # ohne Hintergrund-Thread direkt abgleichen
                self.run_once()
        threading.Thread(target=work, name="timasy-connect", daemon=True).start()

    def disconnect_google(self) -> None:
        from .google_client import disconnect
        disconnect()
        self._set("disconnected")
