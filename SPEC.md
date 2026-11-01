# Timasy – Spezifikation

*Version 0.6 · Stand 31. Oktober 2026 · Persönliches Planungstool für eine Person, lokal auf dem Desktop · Oberfläche auf Deutsch*

## 0. So benutzt du dieses Dokument

- **Für dich:** Abschnitte 1–3 geben den Überblick, 4–10 sind die Details. Du kannst jeden Text direkt ändern. Trage Änderungen zusätzlich in Abschnitt 14 ein und passe Regeln an, die davon betroffen sind.
- **Für Claude:** Dieses Dokument ist die verbindliche Grundlage der Umsetzung. Regeln haben feste IDs (z.B. R-9), damit man gezielt darauf verweisen kann („setze R-9 um“). Bei Lücken oder Widersprüchen fragt Claude nach, statt zu raten. Arbeitsweise: Meilenstein für Meilenstein (Abschnitt 11); zuerst Tests für die fachlichen Regeln, dann der Code; nichts bauen, was nicht hier steht.
- **Kennzeichnung:** **\[Entscheid\]** = von dir entschieden. **\[Annahme\]** = Vorschlag von Claude, bitte prüfen. Alle Annahmen sind in Abschnitt 12 gesammelt.

## 1. Zweck und Leitidee

Timasy vereint eine elegante To-Do-Liste, eine erweiterte Kalenderansicht und (später) eine Zeitplanung an einem Ort. Es ersetzt Papierlisten, verstreute Google-Calendar-Einträge und Dinge, die man nur im Kopf hat.

**Leitidee „Boden und Decke“:** Für jeden Tag und jede Woche gibt es **Pflicht**-Aufgaben (Minimalziele, die geschafft werden müssen) und **Bonus**-Aufgaben (Maximalziele, schön wenn es klappt). So ist das Wesentliche gesichert, und Bonus-Aufgaben erzeugen keinen Druck.

**Ziele:** (1) Jederzeit sehen, was noch offen ist. (2) Zeitlicher Überblick über Tag, Woche und Monat. (3) Schnell erfassen. (4) Ruhig und effizient bedienbar, ohne Ablenkung; der Sinn ist ein Effizienzgewinn.

**Nicht-Ziele:** mehrere Nutzer, Cloud oder Server, Teamfunktionen.

## 2. Rahmenentscheide

- **D-1 \[Entscheid\]** Eine Person, rein lokal auf dem eigenen Desktop. Kein gemieteter Server.
- **D-2 \[Entscheid\]** Keine laufenden Kosten, keine kostenpflichtigen Dienste oder APIs. (Die Google Calendar API ist laut Google-Dokumentation kostenlos.)
- **D-3 \[Entscheid\]** Auf dem Handy genügt die Ansicht des Plans in der Google-Calendar-App (möglich, weil Blöcke in Google erscheinen). Zugriff auf Timasy selbst im Heimnetz ist ausgeschlossen.
- **D-4 \[Entscheid\]** Zwei-Wege-Sync mit Google Calendar nur für Task-Blöcke. Fremde Termine werden nur gelesen.
- **D-5 \[Entscheid\]** Keine Pflicht-Kategorisierung; Tags sind optional.
- **D-6 \[Entscheid\]** Nicht in Version 1: Zeitplan-Optimierer, Zugriff im Heimnetz, Druckansicht.

## 3. Begriffe

Format: **UI-Begriff** (`Code-Name`) – Bedeutung. Die Oberfläche nutzt deutsche Begriffe, der Code englische Bezeichner.

- **Aufgabe** (`Task`) – Das, was getan werden soll: Titel, Notiz, Tags, geschätzte Dauer. Eine Aufgabe hat selbst keinen Zeitpunkt.
- **Eintrag** (`Entry`) – Eine Aufgabe, die einem Zeitraum und einer Stufe zugewiesen ist. Der Eintrag wird abgehakt.
- **Stufe** (`tier`) – `must` = **Pflicht** (Minimalziel), `bonus` = **Bonus** (Maximalziel).
- **Zeitraum** (`scope`, `period_start`) – ein **Tag** (`day`) oder eine **Woche** (`week`, Start Montag).
- **Block** (`Block`) – Eingeplante Uhrzeit (Start und Ende) für einen Tages-Eintrag. Wird in Google Calendar zu einem Kalendereintrag.
- **Serie** (`Series`) – Wiederholungsregel, die laufend Einträge erzeugt.
- **Fremdtermin** (`ExternalEvent`) – Termin aus Google Calendar, der nicht von Timasy stammt. Nur lesbar.
- **Backlog** – Aufgaben, die keinem Zeitraum zugewiesen sind: Sie haben keinen offenen Eintrag und wurden nie erledigt. Erledigte Aufgaben erscheinen nicht im Backlog.
- **Überfällig** – Kennzeichnung eines Eintrags, der aus einem vergangenen Zeitraum übertragen wurde.

## 4. Datenmodell

Alle Felder sind fachlich beschrieben; die genauen Datenbanktypen legt die Umsetzung fest.

- **Task:** `id`, `title` (Pflicht), `notes`, `estimated_minutes` (optional), `created_at`. Tags über eine n:m-Beziehung.
- **Tag:** `id`, `name` (eindeutig).
- **Entry:** `id`, `task_id`, `scope`, `period_start`, `tier`, `status` (`open`, `done`, `missed`), `done_at`, `overdue` (ja/nein), `overdue_since` (Datum des ursprünglichen Zeitraums), `series_id` und `occurrence_date` (nur bei Serien), `is_exception` (ja/nein).
- **Block:** `id`, `entry_id` (höchstens ein Block pro Eintrag), `start`, `end`, `google_event_id`, `local_updated_at`, `last_synced_at`.
- **Series:** `id`, `task_id` (Vorlage), `rrule` (Wiederholungsregel), `starts_on`, `end_type` (`never`, `until`, `count`), `until_date`, `count`, `tier`, `scope`, optional feste Uhrzeit und Dauer, `carry_over` (Standard: nein).
- **ExternalEvent** (Zwischenspeicher): `calendar_id`, `google_event_id`, `title`, `start`, `end`, `all_day`, `updated`.
- **SyncState:** pro Kalender der Sync-Token und der Zeitpunkt des letzten Abgleichs; ID des Timasy-Kalenders.
- **Settings:** Zeitzone (Standard `Europe/Zurich`), Wochenstart (Montag), Sync-Intervall (5 Minuten), gewählte Kalender, Theme.

**Beziehungen:** Eine Aufgabe hat viele Einträge (nacheinander, z.B. durch Übertragung); ein Eintrag hat null oder einen Block. Eine Aufgabe gilt als zugewiesen, solange sie einen offenen Eintrag hat. Sie gilt als erledigt, sobald einer ihrer Einträge erledigt ist; erledigte Aufgaben erscheinen nicht im Backlog.

**Speicherung:** eine SQLite-Datei; Schema-Änderungen laufen über versionierte Migrationen. Zeiten werden mit Zeitzone gespeichert. Serien rechnen in lokaler Zeit, damit eine Uhrzeit über die Sommerzeit-Umstellung hinweg gleich bleibt.

## 5. Fachliche Regeln

### Stufen und Fortschritt

- **R-1 \[Entscheid\]** Jeder Eintrag hat genau eine Stufe. Die Stufe gehört zum Eintrag, nicht zur Aufgabe: Dieselbe Aufgabe kann diese Woche Pflicht und nächste Woche Bonus sein.
- **R-2 \[Entscheid\]** Fortschritt Pflicht = erledigte Pflicht-Einträge geteilt durch alle Pflicht-Einträge des Zeitraums. Fortschritt gesamt = alle erledigten durch alle Einträge. Gezählt wird nach Anzahl, nicht nach Dauer.
- **R-3** „Minimum erreicht“ wird angezeigt, sobald es mindestens einen Pflicht-Eintrag gibt und alle erledigt sind.
- **R-4** Der Wochenfortschritt zählt die Wochen-Einträge und alle Tages-Einträge dieser Woche zusammen.

### Zuweisen, erledigen, löschen

- **R-5** Eine Aufgabe aus dem Backlog wird einem Tag oder einer Woche mit einer Stufe zugewiesen. Dabei entsteht ein Eintrag.
- **R-6** Ein Wochen-Eintrag kann einem Tag zugewiesen werden. Er wird dabei zum Tages-Eintrag (nicht kopiert); die Stufe bleibt, ausser sie wird geändert.
- **R-7** Abhaken setzt den Eintrag auf erledigt; das ist jederzeit rückgängig zu machen.
- **R-8 \[Entscheid\]** „Aus Zeitraum entfernen“ löscht nur den Eintrag; die Aufgabe geht zurück in den Backlog. „Aufgabe löschen“ entfernt sie endgültig, mit kurzer Rückgängig-Möglichkeit.

### Übertragung unerledigter Einträge

- **R-9 \[Entscheid\]** Beim ersten Start der App an einem neuen Tag (und beim Tageswechsel, solange sie läuft) werden alle offenen Tages-Einträge vergangener Tage auf den heutigen Tag übertragen (Vorkommen von Serien: siehe R-13). Die Stufe bleibt: Unerledigte Pflicht-Einträge bleiben Pflicht, unerledigte Bonus-Einträge bleiben Bonus. Lag die App mehrere Tage still, landen sie ebenfalls auf heute.
- **R-10 \[Entscheid\]** Übertragene Einträge tragen den Vermerk „überfällig“. `overdue_since` behält das ursprüngliche Datum, auch bei mehrfacher Übertragung; angezeigt wird „überfällig seit n Tagen“.
- **R-11 \[Entscheid\]** Dasselbe gilt für Wochen: Offene Wochen-Einträge vergangener Wochen werden in die aktuelle Woche übertragen, Stufe bleibt, Vermerk „überfällig“.
- **R-12 \[Entscheid\]** Hatte ein übertragener Eintrag einen Block, wird dieser Block gelöscht (auch der Kalendereintrag in Google). Der Eintrag ist am neuen Tag zunächst nicht eingeplant.
- **R-13 \[Entscheid\]** Vorkommen einer Serie werden standardmässig nicht übertragen: Ein offenes Vorkommen eines vergangenen Tages wird auf `missed` (verpasst) gesetzt. Pro Serie einstellbar über `carry_over`.

### Wiederholung

- **R-14 \[Entscheid\]** Muster: täglich, wöchentlich (Wochentage wählbar), monatlich (am n-ten Tag des Monats oder am n-ten Wochentag, z.B. erster Montag), jährlich; jeweils „alle n Einheiten“.
- **R-15 \[Entscheid\]** Ende: nie, an einem Datum (einschliesslich) oder nach n Vorkommen. Beispiele: „jede Woche bis am 29. Dezember“, „nur 14 Mal“.
- **R-16 \[Entscheid\]** Aus einer Serie werden Einträge für die nächsten 90 Tage erzeugt; beim Start und beim Tageswechsel wird nachgezogen. Eine Serie hat Stufe, Zeitraum (Tag oder Woche) und optional eine feste Uhrzeit mit Dauer. Mit Uhrzeit entsteht pro Vorkommen ein Block.
- **R-17** Bearbeiten und Löschen wie in Kalender-Apps: **nur dieses Vorkommen** (wird zur Ausnahme und bleibt von späteren Serienänderungen unberührt), **dieses und alle folgenden** (die Serie wird geteilt), **alle** (die Serie wird geändert; offene künftige Vorkommen werden neu erzeugt, Ausnahmen bleiben).
- **R-18 \[Entscheid\]** Gibt es einen Termin in einem Monat nicht (z.B. der 31.), entfällt das Vorkommen in diesem Monat (Verhalten des Wiederholungsstandards).
- **R-24 \[Entscheid\]** Serien mit Zeitraum Woche wiederholen sich nur wöchentlich bzw. alle n Wochen; Wochentage und Uhrzeit gibt es dafür nicht. Jedes Vorkommen ist ein Wochen-Eintrag.
- **R-25 \[Entscheid\]** Bei „nur dieses Vorkommen“ ist alles änderbar: Stufe, Tag, Uhrzeit sowie Titel, Notiz und Tags. Ändert sich der Text, erhält das Vorkommen eine eigene Kopie der Aufgabe; die übrigen Vorkommen behalten den Text der Serie.
- **R-26 \[Entscheid\]** „Serie beenden“ (V-5) setzt das Ende auf heute: Offene Vorkommen ab morgen werden entfernt; heutige und vergangene bleiben.
- **R-27 \[Entscheid\]** Abhaken ist keine Änderung. Andere Änderungen an einem einzelnen Vorkommen ausserhalb des Serien-Dialogs (Stufe umschalten, Block ziehen, Tag ändern, Block entfernen) gelten als „nur dieses Vorkommen“. „Aus Zeitraum entfernen“ löscht nur dieses Vorkommen.
- **R-28 \[Entscheid\]** „Löschen: alle“ entfernt die Serie und alle offenen und verpassten Vorkommen; erledigte bleiben als Verlauf erhalten. „Dieses und alle folgenden“ lässt Ausnahmen (R-17) bestehen, wie bei „alle“.
- **R-29 \[Entscheid\]** Monatliche Serien wiederholen sich am Tag oder am n-ten Wochentag des Startdatums (z.B. Start Montag, 2.11. → „am 2.“ oder „am ersten Montag“), jährliche am Datum des Starts.

### Blöcke

- **R-19 \[Entscheid\]** Ein Block liegt innerhalb eines Tages (keine Ganztags- oder Mitternachts-Blöcke) und gehört zu genau einem Tages-Eintrag. Ein Wochen-Eintrag muss erst einem Tag zugewiesen werden (R-6).
- **R-20** Überschneidet sich ein Block mit einem Fremdtermin, ist das erlaubt, wird aber sichtbar markiert.
- **R-30 \[Annahme\]** Ganztägige Fremdtermine (z.B. Geburtstage, Ferien) gelten nicht als Überschneidung im Sinn von R-20.
- **R-21 \[Entscheid\]** Neue Blöcke übernehmen als Dauer `estimated_minutes`, sonst 30 Minuten.
- **R-23 \[Entscheid\]** Wird ein Block auf einen anderen Tag verschoben, wandert sein Eintrag mit auf diesen Tag (R-19: Ein Block liegt immer am Tag seines Eintrags). Eigene Blöcke dürfen sich überschneiden; sie werden nebeneinander dargestellt.

### Tags

- **R-22 \[Entscheid\]** Tags sind optional und frei wählbar, mehrere pro Aufgabe. Es gibt keine vordefinierten Tags; bestehende werden beim Tippen vorgeschlagen. Alle Listen lassen sich nach Tag filtern.

## 6. Ansichten und Bedienung

- **V-1 Heute (Startseite):** Oben Datum und Fortschritt (Pflicht-Balken prominent, Gesamt-Balken dezent) sowie der Hinweis „Minimum erreicht“. Darunter die Pflicht-Liste, dann die Bonus-Liste. Überfällige Einträge tragen den Vermerk aus R-10 in ruhiger Farbe. Daneben eine Tages-Zeitleiste mit Fremdterminen (grau) und Blöcken (Akzentfarbe). Nicht eingeplante Einträge lassen sich per Drag & Drop auf die Zeitleiste ziehen. Eine kleine Leiste „Diese Woche“ zeigt offene Wochen-Einträge, die sich einem Tag zuweisen lassen.
- **V-2 Woche:** Raster Montag bis Sonntag mit Zeitachse. Fremdtermine sind nur lesbar; Blöcke lassen sich verschieben und in der Länge ändern (Raster 15 Minuten). Die Zeitachse zeigt 0 bis 24 Uhr und ist beim Öffnen auf 7 Uhr gescrollt; dasselbe gilt für die Tages-Zeitleiste in V-1. Eine Seitenleiste listet Wochen-Einträge (nach Stufe) und nicht eingeplante Tages-Einträge; sie lassen sich auf einen Tag (zuweisen) oder auf eine Uhrzeit (Block anlegen) ziehen. Oben der Wochenfortschritt.
- **V-3 Monat:** Monatsraster. Pro Tag eine dezente Zahl offener Pflicht-Einträge und kleine Striche für Termine. Klick öffnet den Tag. Vor- und Zurückblättern.
- **V-4 Backlog:** Liste aller Aufgaben ohne offenen Eintrag, mit Suche und Tag-Filter. Von hier aus Zuweisen zu Tag oder Woche inklusive Stufe.
- **V-5 Serien:** Liste aller Serien; bearbeiten, beenden, `carry_over` umschalten.
- **V-6 Einstellungen:** Google-Verbindung und Sync-Status, Kalenderauswahl, Zeitzone, Sync-Intervall, Theme, Backup (Kopie der Datenbankdatei erstellen).
- **V-7 Schnellerfassung:** Ein Tastenkürzel öffnet in jeder Ansicht eine Eingabezeile. Titel eingeben, Enter. In Heute, Woche und Monat entsteht ein Eintrag für den angezeigten Tag, im Backlog eine Aufgabe ohne Zeitraum. **\[Entscheid\]** Standardstufe ist Pflicht, per Tastenkürzel umschaltbar. `#name` im Titel fügt einen Tag hinzu. Details (Stufe, Zeitraum, Dauer, Notiz, Tags, Uhrzeit, Wiederholung) im erweiterten Dialog.
- **V-8 Wiederholung erfassen:** Wie in Kalender-Apps: „Wiederholt sich“ → Rhythmus, Intervall, Wochentage, Ende (nie / am Datum / nach n Mal), mit Vorschau der nächsten Vorkommen.

## 7. Google-Calendar-Sync

- **S-1 Anmeldung:** OAuth 2.0 für Desktop-Apps (Weiterleitung an `http://127.0.0.1:<port>`, mit PKCE). Einmalige Einrichtung: eigenes Google-Cloud-Projekt, Calendar API aktivieren, Zugangsdaten vom Typ „Desktop-App“ erstellen. \[Entscheid v0.6\] Das Projekt wird auf „In Produktion“ gestellt, weil Google im Status „Testing“ Zugangstokens nach 7 Tagen ablaufen lässt; für die eigene Nutzung ist keine Prüfung durch Google nötig, bei der Anmeldung erscheint einmalig der Hinweis „nicht überprüfte App“. Anleitung: `docs/google-einrichtung.md`.
- **S-2 Berechtigungen:** so gering wie möglich (geprüft in der Google-Dokumentation, Stand 2026-09-03): `calendar.calendarlist.readonly` (Kalenderliste sehen), `calendar.events.readonly` (Termine lesen), `calendar.app.created` (eigene Kalender anlegen und nur darin Termine ändern). \[Entscheid v0.6\] Alle drei werden schon in M4 angefragt, damit die Anmeldung nur einmal nötig ist; geschrieben wird erst ab M5.
- **S-3 \[Entscheid\] Eigener Kalender:** Beim ersten Sync legt Timasy einen Kalender „Timasy“ an und merkt sich dessen ID. Alle Blöcke leben nur dort.
- **S-4 Fremdtermine lesen:** \[Entscheid v0.5\] nur aus den Kalendern, die in den Einstellungen ausdrücklich gewählt sind (Standard: keiner; der Timasy-Kalender ist nie wählbar). Gespeichert werden Titel und Zeiten. Zeitfenster: ab heute bis 90 Tage voraus, keine vergangenen Tage. Abgleich inkrementell über Sync-Token; ist der Token ungültig, wird neu abgeglichen. Wiederkehrende Fremdtermine erscheinen als einzelne Vorkommen. Ganztägige Termine werden als Streifen am Tagesanfang dargestellt.
- **S-5 Zuordnung:** Jeder Block entspricht genau einem Ereignis im Timasy-Kalender. Das Ereignis trägt private Zusatzfelder mit Block-ID und Eintrags-ID, der Block speichert die Google-Ereignis-ID.
- **S-6 \[Annahme\] Was synchronisiert wird:** Die Zeit (Start und Ende) in beide Richtungen. Titel und Beschreibung (diese enthält die Stufe, z.B. „Pflicht“) nur von Timasy nach Google; Änderungen daran in Google werden beim nächsten Abgleich überschrieben.
- **S-7 \[Entscheid\] Konflikte:** Verschiebst du einen Block in Google (z.B. am Handy), übernimmt Timasy die neue Zeit. Sind beide Seiten seit dem letzten Abgleich geändert, gewinnt die zuletzt gemachte Änderung.
- **S-8 \[Entscheid\] Löschen:** Wird ein Block in Google gelöscht, verschwindet er auch in Timasy; die Aufgabe geht nicht verloren und kehrt in den Backlog zurück (Auslegung siehe A-2). Wird ein Block in Timasy gelöscht, wird das Ereignis in Google gelöscht. Ein in Google gelöschter Fremdtermin verschwindet aus dem Zwischenspeicher.
- **S-9 Zeitpunkte:** beim Start (holt alles Verpasste nach), danach alle 5 Minuten (einstellbar), solange die App läuft, sofort nach lokalen Änderungen und per Knopf „Jetzt synchronisieren“.
- **S-10 Fehler und Offline:** Lokale Änderungen werden in einer Warteschlange gesammelt und mit wachsenden Wartezeiten erneut versucht. Die App bleibt voll nutzbar. Der Sync-Status ist dezent sichtbar (kleiner Punkt, Details in den Einstellungen). Ist der Zugang abgelaufen, erscheint der Hinweis „Neu verbinden“.
- **S-11 \[Annahme\] Serien:** Jedes Vorkommen mit Uhrzeit wird als einzelnes Google-Ereignis angelegt (keine Google-Serien), nur innerhalb des 90-Tage-Horizonts aus R-16.
- **S-12:** Es werden keine Google-Tasks synchronisiert. Aufgaben leben nur in Timasy.

## 8. Design

- **UX-1:** Vorbild sind die neuesten Android-Versionen (Material 3) und iOS: einfach, klar, effizient.
- **UX-2:** Ruhige Optik: viel Weissraum, grosse klare Typografie mit Systemschrift, weiche Rundungen, ein einziger Akzentfarbton; Statusfarben nur dezent. Hell- und Dunkelmodus folgen der Systemeinstellung.
- **UX-3:** Keine Ablenkung: keine Pop-ups, Zähler-Badges, Töne oder Effekte. Animationen nur kurz und funktional.
- **UX-4:** Häufige Aktionen (erfassen, abhaken, auf einen anderen Tag verschieben, Ansicht wechseln) gehen per Tastatur und in höchstens zwei Schritten.
- **UX-5:** „Überfällig“ ist ein sachlicher Hinweis, kein Alarm: keine grelle Warnfarbe.
- **UX-6:** Das Layout ist fliessend gebaut, damit eine spätere Handy-Ansicht möglich bleibt (nicht Teil von Version 1).

## 9. Technik

- **T-1 \[Entscheid\]** Backend in Python mit FastAPI und SQLite, lokal betrieben. Frontend im Browser.
- **T-2 \[Entscheid\]** Frontend mit Svelte (Vite), das über eine JSON-Schnittstelle mit dem Backend spricht. Das ist der einzige Punkt mit Webentwicklungs-Werkzeugen (Node.js/npm nur zum Entwickeln und Bauen).
- **T-3:** Der Server hört nur auf `127.0.0.1`, ist also von aussen nicht erreichbar. Eine Anmeldung ist deshalb nicht nötig.
- **T-4:** Start mit einem einzigen Befehl (oder Skript), der die App im Browser öffnet.
- **T-5:** Die fachliche Logik (Übertragung, Serien, Fortschritt, Sync-Regeln) steckt in reinem Code ohne Datenbank- und Google-Zugriff. Die aktuelle Uhrzeit wird von aussen übergeben, damit sich Tageswechsel testen lassen.
- **T-6:** Tests mit `pytest`, mindestens für R-2 bis R-18 und S-6 bis S-8.
- **T-7:** Bibliotheken: `python-dateutil` (Wiederholungsregeln), `google-api-python-client` und `google-auth-oauthlib` (Google).
- **T-8:** Zugangsdaten und Tokens liegen nur lokal, nie im Code oder in einem Repository (`.gitignore`).
- **T-9 \[Annahme\]** Code-Bezeichner englisch, Kommentare auf Deutsch, damit du den Code lesen und anpassen kannst.
- **T-10:** Grobe Struktur: `backend/` (api, domain, db, sync), `frontend/`, `tests/`.

## 10. Qualitätsanforderungen

- Start in unter drei Sekunden, flüssige Bedienung auch mit mehreren tausend Einträgen.
- Voll nutzbar ohne Internet; nur der Google-Abgleich pausiert.
- Keine Telemetrie; keine Daten verlassen den Rechner ausser dem Abgleich mit Google Calendar.
- Alle Daten liegen in einer einzigen Datei und sind per Kopie wiederherstellbar.

## 11. Meilensteine

Jeder Meilenstein ist für sich benutzbar. „Fertig, wenn“ gilt als Abnahmekriterium.

- **M1 Kern, lokal:** Aufgaben, Einträge, Stufen, Tag und Woche, Heute-Ansicht, Backlog, Tags, Schnellerfassung, Übertragung (R-1 bis R-11, R-22). *Fertig, wenn* du eine Aufgabe erfassen, als Pflicht oder Bonus auf heute setzen und abhaken kannst, der Fortschritt stimmt und ein simulierter Tageswechsel unerledigte Einträge als überfällig auf den neuen Tag bringt.
- **M2 Blöcke und Zeitansichten:** Blöcke, Wochen- und Monatsansicht, Drag & Drop, Zuweisung Woche → Tag (R-12, R-19 bis R-21, V-2, V-3). *Fertig, wenn* du in der Wochenansicht Blöcke anlegen und verschieben kannst.
- **M3 Serien:** R-13 bis R-18, V-5, V-8. *Fertig, wenn* „wöchentlich bis 29. Dezember“ und „täglich, 14 Mal“ die richtigen Vorkommen erzeugen und die drei Bearbeitungsarten aus R-17 getestet funktionieren.
- **M4 Google lesen:** S-1 bis S-4. *Fertig, wenn* deine Termine in Heute, Woche und Monat erscheinen und sich nach Änderungen in Google von selbst aktualisieren.
- **M5 Google schreiben, Zwei-Wege:** S-5 bis S-12. *Fertig, wenn* ein Block im Timasy-Kalender erscheint (auch am Handy sichtbar) und Verschieben und Löschen in beide Richtungen wie in S-7 und S-8 funktioniert.
- **M6 Feinschliff:** Design nach Abschnitt 8, Einstellungen, Backup, Fehlerzustände. *Fertig, wenn* du die App im Alltag eine Woche lang ohne Papierliste nutzen kannst.

## 12. Annahmen und offene Punkte

Prüfe diese Punkte; ändere, was nicht passt, und trage es in Abschnitt 14 ein.

- **A-1 Frontend:** *Erledigt (v0.2):* Svelte mit Vite bestätigt (T-2).
- **A-2 „Zurück in den Backlog“ (S-8):** Ich lege es so aus, dass der Eintrag seine Uhrzeit verliert, aber mit seinem Tag und seiner Stufe bestehen bleibt („nicht eingeplant“). Die Alternative wäre, dass die Aufgabe ganz in den Backlog zurückfällt und Tag und Stufe verliert. **Bitte bestätigen.**
- **A-3 Standardstufe:** *Erledigt (v0.2):* Die Schnellerfassung legt Einträge standardmässig als Pflicht an (V-7).
- **A-4 Block bei Übertragung:** *Erledigt (v0.3):* Der alte Block wird gelöscht (R-12).
- **A-5 Fortschritt:** *Erledigt (v0.2):* Zählung nach Anzahl, nicht nach Dauer (R-2).
- **A-6 Synchronisierte Felder:** Zeit in beide Richtungen, Titel und Beschreibung nur nach Google (S-6).
- **A-7 Berechtigungen und Anmeldung:** *Erledigt (v0.6):* siehe S-1 und S-2.
- **A-8 Serien in Google:** Einzelne Ereignisse statt Google-Serien (S-11).
- **A-9 Planungshorizont:** 90 Tage für Serien (R-16, *bestätigt v0.4*); Fremdtermine ab heute bis 90 Tage voraus (S-4, *entschieden v0.5*).

## 13. Spätere Ideen (nicht Teil von Version 1)

- **Zeitplan-Optimierer:** Kapazitäts-Check (reicht die freie Zeit für alle Pflicht-Einträge?), danach ein Vorschlag, der Pflicht-Einträge in freie Lücken legt. Vorbereitet durch das Feld `estimated_minutes`.
- Zugriff vom Handy auf Timasy selbst.
- Eingabe in natürlicher Sprache („morgen 14 Uhr Bericht“), Erinnerungen, Wochenrückblick mit Statistik.

## 14. Entscheidungs- und Änderungsprotokoll

- **31.10.2026, v0.1:** Erstfassung aus dem Brainstorming. Entschieden: Pflicht/Bonus pro Tag und Woche; Übertragung unerledigter Einträge mit Vermerk „überfällig“ (Tag und Woche), bei Serien standardmässig nicht; lokal und kostenlos; Zwei-Wege-Sync nur für Blöcke, Fremdtermine nur lesen; Blöcke in eigenem Kalender; Verschieben in Google wird übernommen; optionale Tags; Serien mit Endbedingungen; Optimierer, Heimnetz-Zugriff und Druckansicht vorerst nicht.
- **31.10.2026, v0.2:** Vor Beginn von M1 bestätigt: A-1 Frontend mit Svelte und Vite (T-2); A-3 Standardstufe Pflicht in der Schnellerfassung (V-7); A-5 Fortschritt nach Anzahl (R-2); R-8 Entfernen und Löschen wie beschrieben. Lücke geschlossen: Erledigte Aufgaben erscheinen nicht im Backlog (Abschnitte 3 und 4).
- **31.10.2026:** M1 abgenommen.
- **31.10.2026, v0.3:** Vor Beginn von M2 bestätigt: A-4/R-12 alter Block wird bei Übertragung gelöscht; R-19 und R-21 bestätigt. Neu R-23: Block auf anderen Tag verschieben nimmt den Eintrag mit; Überschneidungen eigener Blöcke erlaubt. V-2: Raster 15 Minuten, Zeitachse 0–24 Uhr, Start bei 7 Uhr.
- **01.11.2026:** M2 abgenommen. Korrekturen: Enter speichert auch im erweiterten Dialog; Menü „⋯“ schliesst bei Klick ausserhalb.
- **01.11.2026, v0.4:** Vor Beginn von M3: R-16, R-18 und A-9 übernommen (keine Präferenz, Vorschlag gilt). Neu: R-24 Wochen-Serien nur alle n Wochen; R-25 einzelnes Vorkommen voll änderbar; R-26 Serie beenden ab morgen. Zur Prüfung: R-27 bis R-29.
- **01.11.2026:** Bestätigt: R-16, R-18, A-9, R-24, R-25 wie umgesetzt; R-27 bis R-29 als Entscheid übernommen.
- **01.11.2026:** M3 abgenommen. Rückfrage vor dem Löschen einer Serie ergänzt.
- **01.11.2026, v0.5:** Vor Beginn von M4 (S-4): Fremdtermine nur aus ausdrücklich gewählten Kalendern (Standard keiner), Titel und Zeiten werden gespeichert, Zeitfenster ab heute bis 90 Tage voraus (vorher: alle sichtbaren Kalender, 30 Tage zurück bis 365 voraus).
- **01.11.2026:** Zur Prüfung: R-30 (ganztägige Termine zählen nicht als Überschneidung).
- **01.11.2026, v0.6:** A-7 gegen die Google-Dokumentation geprüft: Berechtigungen in S-2 präzisiert (nur Kalenderliste lesen, Termine lesen, eigener Kalender); alle drei schon in M4 anfragen. Projekt „In Produktion“, weil Tokens im Status „Testing“ nach 7 Tagen ablaufen (S-1).
