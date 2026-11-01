"""Zustände, in denen der Abgleich mit Google nicht möglich ist."""


class NotConfigured(Exception):
    """Die Zugangsdaten-Datei credentials.json fehlt (Einrichtung, S-1)."""


class NotConnected(Exception):
    """Noch nicht bei Google angemeldet."""


class AuthExpired(Exception):
    """Zugang abgelaufen oder widerrufen -> "Neu verbinden" (S-10)."""


class SyncTokenInvalid(Exception):
    """Google meldet: Sync-Token ungültig (HTTP 410) -> neu abgleichen (S-4)."""
