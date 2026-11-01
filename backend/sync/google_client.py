"""Verbindung zur Google-Calendar-API (S-1, S-2).

Zugangsdaten liegen nur lokal im Ordner data/google/ (T-8, nicht im Repository):
- credentials.json: OAuth-Client "Desktop-App" aus der Google Cloud Console
- token.json: Zugangstoken nach der Anmeldung (wird von Timasy angelegt)
Inhalte dieser Dateien werden nie ausgegeben oder geloggt.
"""
import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import DB_PATH
from .errors import AuthExpired, NotConfigured, NotConnected, SyncTokenInvalid

# S-2 (geprüft v0.6): so gering wie möglich
SCOPES = [
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",  # Kalenderliste sehen
    "https://www.googleapis.com/auth/calendar.events.readonly",        # Termine lesen
    "https://www.googleapis.com/auth/calendar.app.created",            # eigener Kalender (M5)
]

GOOGLE_DIR = DB_PATH.parent / "google"
CREDENTIALS_FILE = GOOGLE_DIR / "credentials.json"
TOKEN_FILE = GOOGLE_DIR / "token.json"


def _save_token(creds: Credentials) -> None:
    GOOGLE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)   # nur für den eigenen Benutzer lesbar
    except OSError:
        pass                          # z.B. unter Windows nicht nötig


def load_credentials() -> Credentials:
    """Gespeicherten Zugang laden und bei Bedarf erneuern."""
    if not CREDENTIALS_FILE.exists():
        raise NotConfigured()
    if not TOKEN_FILE.exists():
        raise NotConnected()
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.valid:
        return creds
    if not creds.refresh_token:
        raise AuthExpired()
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise AuthExpired() from e
    _save_token(creds)
    return creds


def connect_interactive() -> None:
    """Anmeldung im Browser (S-1).

    Google leitet nach der Zustimmung an http://127.0.0.1:<freier Port> weiter;
    die Bibliothek nimmt die Antwort dort entgegen (mit PKCE).
    """
    if not CREDENTIALS_FILE.exists():
        raise NotConfigured()
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=True, timeout_seconds=300,
        authorization_prompt_message="",
        success_message="Timasy ist mit Google verbunden. Du kannst dieses Fenster schliessen.",
    )
    _save_token(creds)


def disconnect() -> None:
    """Verbindung trennen: gespeicherten Zugang löschen."""
    TOKEN_FILE.unlink(missing_ok=True)


def open_client() -> "GoogleClient":
    return GoogleClient(load_credentials())


class GoogleClient:
    """Die wenigen Aufrufe, die Timasy braucht (siehe sync.read.CalendarClient)."""

    def __init__(self, creds: Credentials):
        self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_calendars(self) -> list[dict]:
        result, page_token = [], None
        while True:
            page = _call(self.service.calendarList().list(pageToken=page_token))
            for c in page.get("items", []):
                result.append({
                    "id": c["id"],
                    "summary": c.get("summaryOverride") or c.get("summary") or c["id"],
                    "color": c.get("backgroundColor"),
                })
            page_token = page.get("nextPageToken")
            if not page_token:
                return result

    def list_events(self, calendar_id: str, time_min: str | None = None, time_max: str | None = None,
                    sync_token: str | None = None, page_token: str | None = None) -> dict:
        # Wiederkehrende Termine als einzelne Vorkommen (singleEvents, S-4).
        # Mit Sync-Token sind timeMin/timeMax nicht erlaubt (Google-Doku events.list).
        params = {"calendarId": calendar_id, "singleEvents": True, "maxResults": 250,
                  "pageToken": page_token}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            params["timeMin"] = time_min
            params["timeMax"] = time_max
        return _call(self.service.events().list(**params))

    def create_calendar(self, summary: str, time_zone: str) -> str:
        body = {"summary": summary, "timeZone": time_zone}
        return _call(self.service.calendars().insert(body=body))["id"]


def _call(request):
    """Google-Aufruf ausführen und Fehler in unsere Fälle übersetzen."""
    try:
        return request.execute()
    except HttpError as e:
        if e.resp.status == 410:
            raise SyncTokenInvalid() from e
        if e.resp.status == 401:
            raise AuthExpired() from e
        raise
    except RefreshError as e:
        raise AuthExpired() from e
