"""Timasy starten (T-4): python run.py

Startet den Server auf 127.0.0.1 (nur dieser Rechner, T-3) und öffnet die App
im Browser. Vorher einmal das Frontend bauen: cd frontend && npm install && npm run build
"""
import threading
import webbrowser

import uvicorn

from backend.api.app import create_app
from backend.config import DB_PATH, FRONTEND_DIST, HOST, PORT


def main() -> None:
    if not FRONTEND_DIST.exists():
        print("Hinweis: Frontend ist noch nicht gebaut. Im Ordner frontend/ "
              "'npm install' und 'npm run build' ausführen.")
    url = f"http://{HOST}:{PORT}"
    print(f"Timasy läuft auf {url} (Datenbank: {DB_PATH}). Beenden mit Ctrl+C.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(DB_PATH), host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
