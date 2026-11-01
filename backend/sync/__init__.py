"""Abgleich mit Google Calendar (M4 lesen, M5 schreiben).

Die Logik hier spricht nur mit einem "Client"-Objekt. Der echte Client
(google_client.py) ruft die Google-API auf; in den Tests ersetzt ihn ein
simulierter Google. So lässt sich alles ohne Internet prüfen.
"""
