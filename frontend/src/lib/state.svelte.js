// Gemeinsamer Zustand der App.
//
// Neues Konzept: $state macht ein Objekt "reaktiv". Ändert sich ein Wert,
// aktualisiert Svelte automatisch alle Stellen, die ihn anzeigen.

import { ServerDownError, api, setConnectionListener } from './api.js'

export const app = $state({
  view: 'today',          // 'today', 'week', 'month', 'backlog', 'series' oder 'settings'
  today: null,            // heutiges Datum laut Backend
  date: null,             // angezeigter Tag; null = immer der heutige Tag
  tags: [],               // alle bestehenden Tags (für Vorschläge)
  version: 0,             // wird erhöht, wenn die Ansichten neu laden sollen
  error: '',
  pendingDelete: null,    // { taskId, title } während der Rückgängig-Frist
  sync: null,             // Zustand des Google-Abgleichs (S-10)
  serverDown: false,      // Backend nicht erreichbar (Fehlerzustand)
  helpOpen: false,        // Übersicht der Tastenkürzel offen?
  selectedId: null,       // per Tastatur gewählter Eintrag in Heute (UX-4)
})

// Server wieder erreichbar: alles neu laden
setConnectionListener((ok) => {
  const wasDown = app.serverDown
  app.serverDown = !ok
  if (ok && wasDown) reload()
})

export function reload() {
  app.version++
  api.tags().then((t) => (app.tags = t)).catch(() => {})
}

export function showError(e) {
  if (e instanceof ServerDownError) return   // zeigt schon das Banner oben
  app.error = e?.message || String(e)
  setTimeout(() => (app.error = ''), 5000)
}

// --- Aufgabe löschen mit kurzer Rückgängig-Möglichkeit (R-8) -----------------
// Die Aufgabe wird sofort ausgeblendet, aber erst nach einigen Sekunden
// wirklich gelöscht. "Rückgängig" bricht das Löschen ab.

const UNDO_SECONDS = 6
let deleteTimer = null

export function deleteTaskWithUndo(taskId, title) {
  commitPendingDelete()
  app.pendingDelete = { taskId, title }
  deleteTimer = setTimeout(commitPendingDelete, UNDO_SECONDS * 1000)
}

export function undoDelete() {
  clearTimeout(deleteTimer)
  app.pendingDelete = null
}

export function commitPendingDelete() {
  clearTimeout(deleteTimer)
  const pending = app.pendingDelete
  if (!pending) return
  app.pendingDelete = null
  api.deleteTask(pending.taskId).then(reload).catch(showError)
}

// --- Abgleich mit Google (S-9, S-10) ------------------------------------------
// Der Zustand wird regelmässig abgefragt. Ist ein Abgleich fertig geworden,
// laden die Ansichten neu, damit neue Termine erscheinen.

export async function pollSync() {
  try {
    const status = await api.syncStatus()
    const finished = app.sync && status.last_synced_at !== app.sync.last_synced_at
    app.sync = status
    if (finished) reload()
  } catch {}
}

// --- Theme und Akzentfarbe (V-6, UX-2) ----------------------------------------------------------------
// "system" folgt der Systemeinstellung; "light"/"dark" setzen data-theme am <html>.

export function applyTheme(theme, accent = 'blue') {
  const root = document.documentElement
  if (theme === 'light' || theme === 'dark') root.dataset.theme = theme
  else delete root.dataset.theme
  // Akzentfarbe (UX-2): Blau ist Standard und braucht kein Attribut
  if (accent && accent !== 'blue') root.dataset.accent = accent
  else delete root.dataset.accent
}
