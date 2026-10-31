# Timasy – Projektanweisungen für Claude Code

## Worum es geht
Timasy ist ein persönliches Planungstool (lokal, eine Person): To-Do-Liste mit Pflicht-/Bonus-Einträgen, Kalenderansichten und Zwei-Wege-Sync von Task-Blöcken mit Google Calendar.
Die verbindliche Spezifikation liegt in `SPEC.md`. Lies sie vollständig, bevor du etwas baust.

## Arbeitsweise
- Arbeite meilensteinweise nach Abschnitt 11 der `SPEC.md` (M1 bis M6). Beginne mit dem Meilenstein, den ich nenne, ohne Angabe mit M1. Gehe erst zum nächsten, wenn die „Fertig, wenn“-Kriterien erfüllt sind und ich es bestätigt habe.
- Zuerst Tests für die fachlichen Regeln (R-…, S-…), dann der Code. Tests mit `pytest`.
- Baue nichts, was nicht in `SPEC.md` steht. Bei Lücken, Widersprüchen oder offenen Punkten (Abschnitt 12) frag nach, statt zu raten.
- Ändere die Spezifikation nie stillschweigend. Schlage Änderungen vor; bestätigte trägst du im Änderungsprotokoll (Abschnitt 14) ein.
- Arbeite in kleinen Schritten. Sag nach jedem Schritt kurz, was sich geändert hat und wie ich es ausprobieren kann.
- Ich will den Code verstehen und selbst anpassen können: einfache, lesbare Lösungen vor cleveren; neue Konzepte kurz erklären.

## Rahmen (nicht verhandelbar)
- Rein lokal, ein Nutzer, kein Server, keine kostenpflichtigen Dienste oder APIs (D-1, D-2). Keine Abhängigkeiten, die Kosten verursachen.
- Der Server hört nur auf `127.0.0.1` (T-3).
- Google-Zugangsdaten und Tokens nie ins Repository (T-8, `.gitignore`) und nie in Ausgaben oder Logs.
- Fremdtermine nur lesen; geschrieben wird ausschliesslich im Timasy-Kalender (D-4, S-2, S-3).

## Technik und Konventionen
- Backend: Python, FastAPI, SQLite. Frontend im Browser; die Wahl (Svelte-Vorschlag, A-1) bestätige ich vor dem Start des Frontends.
- Fachliche Logik (Übertragung, Serien, Fortschritt, Sync-Regeln) in reinem Code ohne Datenbank- und Google-Zugriff; die aktuelle Zeit wird von aussen übergeben (T-5).
- Zeitzone `Europe/Zurich`; Zeiten mit Zeitzone speichern; Serien in lokaler Zeit.
- Code-Bezeichner englisch, Kommentare und UI-Texte deutsch (T-9). Begriffe gemäss Glossar (Abschnitt 3).
- Schweizer Rechtschreibung (ss statt ß).
- Struktur: `backend/` (api, domain, db, sync), `frontend/`, `tests/` (T-10).

## Offene Punkte
Klär die Punkte aus Abschnitt 12 mit mir, bevor du den betroffenen Meilenstein beginnst, insbesondere A-1 (Frontend) und A-2 (Löschen eines Blocks in Google).

## Befehle
Halte diesen Abschnitt aktuell.

Einmalig einrichten (Python 3.11+ und Node.js 20.19+ nötig):
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
cd frontend && npm install && npm run build && cd ..
```

- Starten (öffnet den Browser, http://127.0.0.1:8765): `.venv/bin/python run.py`
- Tests: `.venv/bin/python -m pytest`
- Frontend neu bauen nach Änderungen: `cd frontend && npm run build`
- Frontend entwickeln mit Live-Neuladen: Backend mit `run.py` starten, dann `cd frontend && npm run dev` (http://127.0.0.1:5173)
- Tageswechsel simulieren: `TIMASY_TODAY=2026-11-05 .venv/bin/python run.py`
- Andere Datenbankdatei (z.B. zum Ausprobieren): `TIMASY_DB=/tmp/test.db .venv/bin/python run.py`
- Daten liegen in `data/timasy.db` (nicht im Repository).

Unter Windows (PowerShell; Befehle einzeln ausführen, ältere PowerShell kennt kein `&&`):
```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd frontend; npm install; npm run build; cd ..
.venv\Scripts\python run.py
```
- Tests: `.venv\Scripts\python -m pytest`
- Tageswechsel simulieren: `$env:TIMASY_TODAY="2026-11-05"; .venv\Scripts\python run.py` (danach `Remove-Item Env:TIMASY_TODAY`)
- Blockiert PowerShell `npm` (Ausführungsrichtlinie), `npm.cmd` verwenden.
