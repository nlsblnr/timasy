# Google Calendar einrichten (einmalig)

Damit Timasy deine Google-Termine lesen und später (M5) seine Blöcke in einen
eigenen Kalender „Timasy“ schreiben kann, brauchst du ein eigenes, kostenloses
Google-Cloud-Projekt. Das dauert etwa 15 Minuten und ist nur einmal nötig.

Die Schritte folgen der Google-Dokumentation (Stand Oktober 2026) und wurden
im November 2026 an der deutschen Oberfläche der Console nachgeführt. Die Google
Cloud Console ist manchmal auf Englisch, manchmal auf Deutsch; die Begriffe
stehen deshalb in beiden Sprachen, wo sie sich unterscheiden.

> **Wichtig:** Die Datei, die du in Schritt 6 herunterlädst, ist dein
> Zugangsschlüssel. Sie gehört nur auf deinen Computer, nie in ein Repository
> oder eine E-Mail (T-8). Der Ordner `data/` ist deshalb in `.gitignore`.

## 1. Projekt anlegen

1. Öffne <https://console.cloud.google.com> und melde dich mit dem Google-Konto
   an, dessen Kalender Timasy nutzen soll.
2. Oben links auf die Projektauswahl klicken → **New project / Neues Projekt**.
3. Name: `Timasy` → **Create / Erstellen**. Warte, bis das Projekt angelegt ist,
   und wähle es oben in der Projektauswahl aus.

## 2. Google Calendar API aktivieren

1. Menü ☰ → **APIs & Services / APIs und Dienste** → **Library / Bibliothek**.
2. Nach `Google Calendar API` suchen, anklicken → **Enable / Aktivieren**.

## 3. Zustimmungsbildschirm einrichten (Google Auth Platform)

1. Menü ☰ → **Google Auth Platform** → **Branding**.
   Steht dort „Google Auth platform not configured yet“, auf **Get Started** klicken.
2. **App Information:** App-Name `Timasy`, bei „User support email“ deine
   E-Mail-Adresse wählen → **Next**.
3. **Audience:** **External** wählen → **Next**.
   (Internal gibt es nur für Google-Workspace-Organisationen.)
4. **Contact Information:** deine E-Mail-Adresse → **Next**.
5. **Finish:** der „Google API Services: User Data Policy“ zustimmen →
   **Continue** → **Create**.

## 4. Dich selbst als Testnutzer eintragen

Das Projekt bleibt im Status **Test / Testing** (S-1). Dann dürfen sich nur
Konten anmelden, die als Testnutzer eingetragen sind:

1. **Google Auth Platform** → **Zielgruppe / Audience**.
2. Bei **Testnutzer / Test users** auf **Nutzer hinzufügen / Add users** klicken,
   deine Gmail-Adresse eintragen und **Speichern / Save**.

Unter **Datenzugriff / Data Access** musst du nichts eintragen. Timasy fragt
seine drei Berechtigungen bei der Anmeldung selbst an (S-2):

| Berechtigung | Wozu |
|---|---|
| `calendar.calendarlist.readonly` | Liste deiner Kalender sehen (für die Auswahl) |
| `calendar.events.readonly` | Termine lesen (nur aus den Kalendern, die du in Timasy auswählst) |
| `calendar.app.created` | eigenen Kalender „Timasy“ anlegen und nur darin Termine ändern |

## 5. Gut zu wissen: Anmeldung gilt 7 Tage

Im Status Testing lässt Google die Anmeldung nach **7 Tagen** ablaufen
(Google-Dokumentation zu OAuth 2.0). Timasy zeigt dann oben „Neu verbinden“;
ein Klick darauf und eine Bestätigung im Browser genügen.

*Warum nicht veröffentlichen?* Für „App veröffentlichen“ verlangt Google auf der
Seite **Branding** eine Startseite und eine Datenschutzerklärung auf einer
eigenen Domain. „Intern“ ist nur für Google-Workspace-Organisationen möglich,
nicht für ein Gmail-Konto.

## 6. Zugangsdaten für die Desktop-App erstellen

1. **Google Auth Platform** → **Clients** → **Create Client**.
2. **Application type:** **Desktop app**. Name z.B. `Timasy Desktop`.
   Die Option für „AI-powered agent“ nicht anwählen.
3. **Create**. Im Fenster danach (oder in der Liste über das Download-Symbol)
   die Datei im **JSON**-Format herunterladen.

## 7. Datei in Timasy ablegen

Lege die heruntergeladene Datei im Timasy-Ordner so ab:

```
timasy/
└── data/
    └── google/
        └── credentials.json
```

Unter Windows (PowerShell, im Timasy-Ordner; Dateiname anpassen):

```powershell
mkdir data\google
Move-Item "$env:USERPROFILE\Downloads\client_secret_*.json" data\google\credentials.json
```

## 8. Verbinden

1. Timasy starten (`.venv\Scripts\python run.py`) und **Einstellungen** öffnen
   (Taste `e`).
2. **Mit Google verbinden** klicken. Es öffnet sich ein Browserfenster.
3. Google-Konto wählen. Google weist darauf hin, dass die App nicht überprüft
   ist bzw. sich im Test befindet: **Weiter / Continue** (bei manchen Varianten
   zuerst **Erweitert**). Das ist hier in Ordnung: Es ist deine eigene App auf
   deinem eigenen Computer.
4. Die Berechtigungen bestätigen. Danach steht im Browser „Timasy ist mit
   Google verbunden“; das Fenster kannst du schliessen.
5. Zurück in Timasy legt der erste Abgleich den Kalender **„Timasy“** in deinem
   Google Calendar an (er bleibt bis M5 leer).
6. Unter **Termine anzeigen aus** die Kalender ankreuzen, deren Termine du in
   Timasy sehen willst (z.B. deinen Hauptkalender). Standard ist: keiner.

Die Termine erscheinen grau in Heute, Woche und Monat. Änderungen in Google
(z.B. am Handy) übernimmt Timasy spätestens nach 5 Minuten oder sofort mit
**Jetzt synchronisieren**.

## Wenn etwas nicht klappt

- **„Zugriff blockiert“ / „Access blocked“ bei der Anmeldung:** Deine
  E-Mail-Adresse ist nicht als Testnutzer eingetragen. Schritt 4 ausführen.
- **Timasy zeigt „Neu verbinden“:** Normal nach 7 Tagen (Schritt 5), oder der
  Zugang wurde widerrufen. Auf **Neu verbinden** klicken und bestätigen.
- **„Noch nicht eingerichtet“:** Die Datei liegt nicht unter
  `data/google/credentials.json` oder heisst anders.
- **Zugriff entziehen:** In Timasy **Verbindung trennen**; zusätzlich unter
  <https://myaccount.google.com/permissions> den Zugriff von „Timasy“ entfernen.
