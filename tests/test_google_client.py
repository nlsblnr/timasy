"""Prüft die Übersetzung von Google-Fehlern (ohne Verbindung zu Google)."""
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from backend.sync.errors import AuthExpired, SyncTokenInvalid
from backend.sync.google_client import SCOPES, _call


class FakeRequest:
    def __init__(self, status):
        self.status = status

    def execute(self):
        raise HttpError(Response({"status": self.status}), b"{}")


def test_410_means_sync_token_invalid():
    with pytest.raises(SyncTokenInvalid):
        _call(FakeRequest(410))


def test_401_means_reconnect():
    with pytest.raises(AuthExpired):
        _call(FakeRequest(401))


def test_other_errors_pass_through():
    with pytest.raises(HttpError):
        _call(FakeRequest(500))


def test_scopes_are_minimal():
    # S-2: keine umfassenden Berechtigungen wie .../auth/calendar
    assert all(s.rsplit("/", 1)[1].startswith("calendar.") for s in SCOPES)
    assert "https://www.googleapis.com/auth/calendar" not in SCOPES
