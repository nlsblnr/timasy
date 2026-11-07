"""Zwei-Wege-Abgleich der Blöcke mit dem Kalender "Timasy" (S-5 bis S-8, S-13, S-14).

Reine Logik:
- event_body: wie ein Block in Google aussieht (S-5, S-6)
- signature: kurzer Text, der den Inhalt eines Ereignisses beschreibt. Ist die
  Signatur dessen, was in Google steht, anders als die des Blocks in Timasy,
  muss Timasy das Ereignis aktualisieren. So werden auch Titel-Änderungen in
  Google wieder überschrieben (S-6).
- decide_incoming: was mit einer Änderung aus Google geschehen soll (S-7, S-8, S-13)
"""
import json
from dataclasses import dataclass
from datetime import date, datetime

from ..config import TIMEZONE
from .blocks import Block, local_minutes, minutes_on_day, MINUTES_PER_DAY
from .models import Entry, Status, Tier

TIER_TEXT = {Tier.MUST: "Pflicht", Tier.BONUS: "Bonus"}


def description(tier: Tier) -> str:
    return f"{TIER_TEXT[tier]}\nEingeplant mit Timasy"


def _google_time(moment: datetime) -> dict:
    return {"dateTime": moment.astimezone(TIMEZONE).isoformat(), "timeZone": TIMEZONE.key}


def event_body(block: Block, title: str, tier: Tier) -> dict:
    """S-5, S-6: Ereignis für einen Block, mit privaten Zusatzfeldern."""
    return {
        "summary": title,
        "description": description(tier),
        "start": _google_time(block.start),
        "end": _google_time(block.end),
        "extendedProperties": {"private": {
            "timasyBlockId": str(block.id),
            "timasyEntryId": str(block.entry_id),
        }},
    }


def signature(summary: str | None, desc: str | None, start: datetime | None,
              end: datetime | None) -> str:
    """Inhalt eines Ereignisses als Text; Zeitformat und Zeitzone spielen keine Rolle."""
    def t(x):
        return x.astimezone(TIMEZONE).isoformat() if x else None
    return json.dumps([summary or "", desc or "", t(start), t(end)], ensure_ascii=False)


@dataclass(frozen=True)
class Incoming:
    """Ein Ereignis aus dem Kalender "Timasy", so wie Google es meldet."""
    google_event_id: str
    block_id: int | None          # aus den privaten Zusatzfeldern (S-5)
    cancelled: bool
    all_day: bool = False
    start: datetime | None = None
    end: datetime | None = None
    updated: datetime | None = None
    summary: str | None = None
    description: str | None = None

    @property
    def signature(self) -> str:
        return signature(self.summary, self.description, self.start, self.end)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TIMEZONE)


def parse_incoming(item: dict) -> Incoming:
    private = item.get("extendedProperties", {}).get("private", {})
    block_id = private.get("timasyBlockId")
    updated = _parse_dt(item["updated"]) if item.get("updated") else None
    if item.get("status") == "cancelled":
        return Incoming(item["id"], int(block_id) if block_id else None, True, updated=updated)
    all_day = "date" in item["start"]
    start = end = None
    if not all_day:
        start, end = _parse_dt(item["start"]["dateTime"]), _parse_dt(item["end"]["dateTime"])
    return Incoming(item["id"], int(block_id) if block_id else None, False, all_day, start, end,
                    updated, item.get("summary"), item.get("description"))


@dataclass(frozen=True)
class Decision:
    """kind:
    - ignore: kein Timasy-Ereignis (S-14)
    - none: Zeit unverändert oder nur das Echo unseres eigenen Uploads
      (Titel o.ä. überschreibt der nächste Upload, S-6)
    - apply_time: neue Zeit aus Google übernehmen (S-7), evtl. anderer Tag (R-23)
    - push: Timasy-Zeit gilt; Google wird überschrieben (S-7, S-13)
    - delete_block: in Google gelöscht -> Block löschen, Eintrag bleibt (S-8, A-2)
    - recreate: in Google gelöscht, aber in Timasy später geändert -> neu anlegen (S-7)
    - delete_event: Timasy-Ereignis ohne Block (z.B. doppelt) -> in Google löschen
    """
    kind: str
    day: date | None = None
    start_minute: int | None = None
    end_minute: int | None = None


def _local_change_time(block: Block) -> datetime | None:
    """Zeitpunkt der Timasy-Änderung, falls seit dem letzten Abgleich geändert."""
    if block.last_synced_at is None:
        return block.local_updated_at or datetime.min.replace(tzinfo=TIMEZONE)
    if block.local_updated_at and block.local_updated_at > block.last_synced_at:
        return block.local_updated_at
    return None


def decide_incoming(inc: Incoming, block: Block | None, entry: Entry | None,
                    today: date) -> Decision:
    if block is None:
        return Decision("ignore" if inc.block_id is None else "delete_event")
    if not inc.cancelled and block.synced_signature == inc.signature:
        return Decision("none")   # in Google unverändert seit unserem letzten Abgleich

    local_change = _local_change_time(block)
    timasy_is_newer = (local_change is not None and inc.updated is not None
                       and local_change > inc.updated)

    if inc.cancelled:
        return Decision("recreate" if timasy_is_newer else "delete_block")

    if inc.all_day or inc.start is None:
        return Decision("push")                       # S-13: ganztägig geht nicht
    day, start_minute = local_minutes(inc.start)
    end_minute = minutes_on_day(day, inc.end)
    if not 0 <= start_minute < end_minute <= MINUTES_PER_DAY:
        return Decision("push")                       # S-13: über Mitternacht

    old_day, old_start = local_minutes(block.start)
    old_end = minutes_on_day(old_day, block.end)
    if (day, start_minute, end_minute) == (old_day, old_start, old_end):
        return Decision("none")
    if timasy_is_newer:
        return Decision("push")                       # S-7: Timasy später geändert
    if entry is not None and entry.status == Status.OPEN and day < today:
        return Decision("push")                       # S-13: offener Eintrag in die Vergangenheit
    return Decision("apply_time", day, start_minute, end_minute)
