"""Versionierte Schema-Migrationen (Abschnitt 4).

Jede Migration ist ein SQL-Text. Die Datenbank merkt sich in
"PRAGMA user_version", wie viele Migrationen schon gelaufen sind. Beim Start
werden nur die neuen ausgeführt. Bestehende Migrationen nie ändern, sondern
immer eine neue anhängen.
"""
import sqlite3

MIGRATIONS: list[str] = [
    # 1: Kern für M1 – Aufgaben, Tags, Einträge
    """
    CREATE TABLE task (
        id                INTEGER PRIMARY KEY,
        title             TEXT    NOT NULL,
        notes             TEXT    NOT NULL DEFAULT '',
        estimated_minutes INTEGER,
        created_at        TEXT    NOT NULL          -- ISO-Zeit mit Zeitzone
    );

    CREATE TABLE tag (
        id   INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE task_tag (
        task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
        tag_id  INTEGER NOT NULL REFERENCES tag(id)  ON DELETE CASCADE,
        PRIMARY KEY (task_id, tag_id)
    );

    CREATE TABLE entry (
        id            INTEGER PRIMARY KEY,
        task_id       INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
        scope         TEXT    NOT NULL CHECK (scope IN ('day', 'week')),
        period_start  TEXT    NOT NULL,             -- ISO-Datum
        tier          TEXT    NOT NULL CHECK (tier IN ('must', 'bonus')),
        status        TEXT    NOT NULL DEFAULT 'open'
                              CHECK (status IN ('open', 'done', 'missed')),
        done_at       TEXT,                         -- ISO-Zeit mit Zeitzone
        overdue       INTEGER NOT NULL DEFAULT 0,   -- 0 = nein, 1 = ja
        overdue_since TEXT                          -- ISO-Datum
    );

    CREATE INDEX entry_period ON entry (period_start);
    CREATE INDEX entry_task   ON entry (task_id);
    CREATE INDEX entry_status ON entry (status);
    """,
    # 2: Blöcke (M2) – höchstens ein Block pro Eintrag
    """
    CREATE TABLE block (
        id               INTEGER PRIMARY KEY,
        entry_id         INTEGER NOT NULL UNIQUE REFERENCES entry(id) ON DELETE CASCADE,
        start            TEXT    NOT NULL,      -- ISO-Zeit mit Zeitzone
        "end"            TEXT    NOT NULL,      -- "end" ist in SQL ein Schlüsselwort
        google_event_id  TEXT,                  -- ab M5
        local_updated_at TEXT,
        last_synced_at   TEXT
    );
    """,
    # 3: Serien (M3)
    """
    CREATE TABLE series (
        id               INTEGER PRIMARY KEY,
        task_id          INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
        rrule            TEXT    NOT NULL,   -- z.B. FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE
        starts_on        TEXT    NOT NULL,   -- ISO-Datum
        end_type         TEXT    NOT NULL CHECK (end_type IN ('never', 'until', 'count')),
        until_date       TEXT,
        count            INTEGER,
        tier             TEXT    NOT NULL CHECK (tier IN ('must', 'bonus')),
        scope            TEXT    NOT NULL CHECK (scope IN ('day', 'week')),
        start_minute     INTEGER,            -- feste Uhrzeit, Minuten seit Mitternacht
        duration_minutes INTEGER,
        carry_over       INTEGER NOT NULL DEFAULT 0,
        exdates          TEXT    NOT NULL DEFAULT ''  -- gelöschte Vorkommen, durch Komma getrennt
    );

    -- Wird eine Serie gelöscht, bleiben erledigte Vorkommen als Verlauf (series_id wird leer).
    ALTER TABLE entry ADD COLUMN series_id INTEGER REFERENCES series(id) ON DELETE SET NULL;
    ALTER TABLE entry ADD COLUMN occurrence_date TEXT;
    ALTER TABLE entry ADD COLUMN is_exception INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX entry_series ON entry (series_id, occurrence_date);
    """,
]


def migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in enumerate(MIGRATIONS, start=1):
        if version <= current:
            continue
        with conn:  # eine Transaktion pro Migration
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {version}")
