<script>
  // Einstellungen (V-6): Google-Verbindung, Sync-Status und -Intervall,
  // Kalenderauswahl, Theme, Backup. Die Zeitzone ist fest Europe/Zurich (v0.9).
  import { api } from '../lib/api.js'
  import { app, applyTheme, pollSync, showError } from '../lib/state.svelte.js'

  let calendars = $state([])
  let settings = $state(null)
  let backups = $state([])
  let backupInfo = $state('')

  // Fehlt ein Teil (z.B. weil noch ein alter Server läuft), nur einen Hinweis zeigen
  let partMissing = $state(false)
  api.settings().then((s) => (settings = s)).catch(() => (partMissing = true))
  const loadBackups = () => api.backups().then((b) => (backups = b)).catch(() => (partMissing = true))
  loadBackups()

  async function save(change) {
    try {
      settings = await api.saveSettings(change)
      applyTheme(settings.theme, settings.accent)
      pollSync()
    } catch (e) {
      showError(e)
    }
  }

  async function makeBackup() {
    try {
      const r = await api.createBackup()
      backupInfo = `Gespeichert als ${r.name}`
      loadBackups()
    } catch (e) {
      showError(e)
    }
  }

  const sizeText = (bytes) => `${Math.max(1, Math.round(bytes / 1024))} KB`
  const themes = [['system', 'Wie System'], ['light', 'Hell'], ['dark', 'Dunkel']]
  const intervals = [1, 5, 10, 15, 30, 60]
  // Akzentfarben (UX-2); die Farbe des Knopfs zeigt den Ton im Hellmodus
  const accents = [['blue', 'Blau', '#3f6ad8'], ['green', 'Grün', '#2f7d5b'],
                   ['violet', 'Violett', '#7a52c7'], ['orange', 'Orange', '#b85f12'],
                   ['rose', 'Rosé', '#c2416e']]

  // Beim Öffnen sofort neu prüfen, z.B. nachdem credentials.json abgelegt wurde
  let checked = false   // nur einmal pro Öffnen der Seite
  $effect(() => {
    if (checked || !app.sync) return
    checked = true
    if (['not_configured', 'disconnected', 'idle'].includes(app.sync.state)) {
      api.syncNow().then(() => setTimeout(pollSync, 1000)).catch(() => {})
    }
  })

  $effect(() => {
    app.version
    api.calendars().then((c) => (calendars = c)).catch(showError)
  })

  async function call(fn) {
    try {
      await fn()
      await pollSync()
    } catch (e) {
      showError(e)
    }
  }

  async function toggle(cal, selected) {
    await call(() => api.selectCalendar(cal.id, selected))
    cal.selected = selected
  }

  const stateText = {
    idle: 'Noch nicht abgeglichen',
    syncing: 'Wird abgeglichen …',
    ok: 'Verbunden',
    error: 'Fehler beim Abgleich – wird automatisch erneut versucht',
    not_configured: 'Noch nicht eingerichtet',
    disconnected: 'Nicht verbunden',
    reconnect: 'Zugang abgelaufen – bitte neu verbinden',
    connecting: 'Anmeldung im Browser läuft …',
  }

  const timeFormat = new Intl.DateTimeFormat('de-CH', { dateStyle: 'medium', timeStyle: 'short' })
  let s = $derived(app.sync)
  let connected = $derived(s && ['ok', 'syncing', 'error', 'idle'].includes(s.state) && calendars.length > 0)
</script>

<h1>Einstellungen</h1>
{#if partMissing}
  <p class="sub error">Ein Teil der Einstellungen konnte nicht geladen werden. Läuft eine ältere
    Version von Timasy? Dann <code>run.py</code> beenden (Ctrl+C) und neu starten.</p>
{/if}

<section>
  <h2>Google Calendar</h2>
  {#if s}
    <p class="status"><span class="dot {s.state}"></span>{stateText[s.state] ?? s.state}</p>
    {#if s.last_synced_at}
      <p class="sub">Zuletzt abgeglichen: {timeFormat.format(new Date(s.last_synced_at))}
        · automatisch alle {s.interval_minutes} Minuten</p>
    {/if}
    {#if s.last_error}<p class="sub error">{s.last_error}</p>{/if}

    {#if s.state === 'not_configured'}
      <p>Für die Verbindung braucht Timasy eine Zugangsdatei von Google. Die Anleitung steht in
        <code>docs/google-einrichtung.md</code>. Lege die Datei als
        <code>data/google/credentials.json</code> ab und öffne diese Seite erneut.</p>
    {/if}

    <div class="actions">
      {#if s.state === 'disconnected' || s.state === 'reconnect' || s.state === 'not_configured'}
        <button class="filled" disabled={s.state === 'not_configured'}
                onclick={() => call(api.googleConnect)}>
          {s.state === 'reconnect' ? 'Neu verbinden' : 'Mit Google verbinden'}
        </button>
      {:else}
        <button class="filled" disabled={s.state === 'syncing' || s.state === 'connecting'}
                onclick={() => call(api.syncNow)}>Jetzt synchronisieren</button>
        <button class="text" onclick={() => call(api.googleDisconnect)}>Verbindung trennen</button>
      {/if}
    </div>
  {/if}
</section>

{#if settings}
  <section>
    <h2>Abgleich</h2>
    <label class="inline">Automatisch abgleichen alle
      <select value={settings.sync_interval_minutes}
              onchange={(e) => save({ sync_interval_minutes: Number(e.target.value) })}>
        {#each intervals as m}<option value={m}>{m} {m === 1 ? 'Minute' : 'Minuten'}</option>{/each}
      </select>
    </label>
    <p class="sub">Zusätzlich sofort nach jeder Änderung in Timasy und mit „Jetzt synchronisieren“.</p>
  </section>

  <section>
    <h2>Darstellung</h2>
    <div class="segmented" role="radiogroup" aria-label="Theme">
      {#each themes as [value, label]}
        <button role="radio" aria-checked={settings.theme === value}
                class:active={settings.theme === value}
                onclick={() => save({ theme: value })}>{label}</button>
      {/each}
    </div>
    <div class="accents" role="radiogroup" aria-label="Akzentfarbe">
      {#each accents as [value, label, color]}
        <button role="radio" aria-checked={settings.accent === value} title={label}
                class="swatch-button" class:active={settings.accent === value}
                onclick={() => save({ accent: value })}>
          <span class="swatch-dot" style="background: {color}"></span>{label}
        </button>
      {/each}
    </div>
  </section>
{/if}

<section>
  <h2>Backup</h2>
  <p class="sub">Alle Daten liegen in einer Datei. Ein Backup ist eine vollständige Kopie davon im
    Ordner <code>data/backups/</code>. Timasy erstellt zusätzlich jeden Tag automatisch eines und
    behält die letzten 14.</p>
  <div class="actions">
    <button class="filled" onclick={makeBackup}>Backup erstellen</button>
    {#if backupInfo}<span class="sub ok">{backupInfo}</span>{/if}
  </div>
  {#if backups.length}
    <ul class="backups">
      {#each backups.slice(0, 5) as b (b.name)}
        <li><span>{timeFormat.format(new Date(b.created))}</span>
          <span class="sub">{b.automatic ? 'automatisch' : 'manuell'} · {sizeText(b.size)}</span></li>
      {/each}
    </ul>
  {/if}
  <details class="restore">
    <summary>Wiederherstellen</summary>
    <ol>
      <li>Timasy beenden (im Terminal <kbd>Ctrl</kbd>+<kbd>C</kbd>).</li>
      <li><code>data/timasy.db</code> umbenennen, z.B. in <code>timasy-alt.db</code>.</li>
      <li>Das gewünschte Backup aus <code>data/backups/</code> nach <code>data/timasy.db</code> kopieren.</li>
      <li>Timasy wieder starten.</li>
    </ol>
  </details>
</section>

{#if calendars.length}
  <section>
    <h2>Termine anzeigen aus</h2>
    <p class="sub">Termine aus diesen Kalendern erscheinen grau in Heute, Woche und Monat (nur lesen,
      heute bis 90 Tage voraus). Der Kalender „Timasy“ ist nicht aufgeführt: Dort legt Timasy
      deine eingeplanten Blöcke ab, damit du sie auch am Handy siehst.</p>
    <ul>
      {#each calendars as cal (cal.id)}
        <li>
          <label class="check">
            <input type="checkbox" checked={cal.selected}
                   onchange={(e) => toggle(cal, e.target.checked)} />
            <span class="swatch" style="background: {cal.color ?? 'var(--muted)'}"></span>
            {cal.summary}
          </label>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  h1 { font-size: 2rem; font-weight: 600; margin: 0 0 20px; }
  section { max-width: 680px; margin-bottom: 32px; }
  h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em;
       color: var(--muted); margin: 0 0 8px; font-weight: 600; }
  .status { display: flex; align-items: center; gap: 8px; margin: 0 0 4px; font-weight: 500; }
  .sub { color: var(--muted); font-size: 0.85rem; margin: 0 0 8px; }
  .error { color: var(--calm); }
  .actions { display: flex; gap: 8px; margin-top: 12px; }
  button:disabled { opacity: 0.5; cursor: default; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: 6px 0; }
  .check { display: flex; align-items: center; gap: 10px; color: var(--text); font-size: 1rem; }
  .swatch { width: 12px; height: 12px; border-radius: 4px; }
  .inline { display: flex; align-items: center; gap: 10px; color: var(--text); font-size: 1rem; }
  .inline select { width: auto; }
  .segmented { display: inline-flex; background: var(--surface); border-radius: 99px; padding: 3px; }
  .segmented button { color: var(--muted); }
  .segmented button.active { background: var(--surface-raised); color: var(--text);
                             box-shadow: 0 1px 3px var(--shadow); font-weight: 600; }
  .ok { margin: 0; align-self: center; }
  .accents { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .swatch-button { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line);
                   color: var(--text); padding: 6px 14px 6px 8px; }
  .swatch-button.active { border-color: var(--accent); background: var(--accent-soft); font-weight: 600; }
  .swatch-dot { width: 18px; height: 18px; border-radius: 50%; }
  .backups { margin-top: 12px; }
  .backups li { display: flex; gap: 12px; padding: 4px 0; }
  .backups .sub { margin: 0; }
  .restore { margin-top: 8px; font-size: 0.9rem; }
  .restore summary { cursor: pointer; color: var(--accent); }
  .restore ol { padding-left: 20px; color: var(--muted); }
  code { font-size: 0.85em; background: var(--surface); padding: 1px 6px; border-radius: 4px; }
  :global(.dot) { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
  :global(.dot.ok) { background: var(--accent); }
  :global(.dot.syncing), :global(.dot.connecting) { background: var(--accent); opacity: 0.5; }
  :global(.dot.error), :global(.dot.reconnect) { background: var(--calm); }
</style>
