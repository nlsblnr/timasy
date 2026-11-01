<script>
  // Einstellungen (V-6), Teil M4: Google-Verbindung, Sync-Status, Kalenderauswahl.
  // Weitere Einstellungen (Zeitzone, Intervall, Theme, Backup) folgen in M6.
  import { api } from '../lib/api.js'
  import { app, pollSync, showError } from '../lib/state.svelte.js'

  let calendars = $state([])

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

{#if calendars.length}
  <section>
    <h2>Termine anzeigen aus</h2>
    <p class="sub">Termine aus diesen Kalendern erscheinen grau in Heute, Woche und Monat (nur lesen,
      heute bis 90 Tage voraus). Der Kalender „Timasy“ ist nicht aufgeführt: Dort legt Timasy
      ab M5 die eingeplanten Blöcke ab.</p>
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
  code { font-size: 0.85em; background: var(--surface); padding: 1px 6px; border-radius: 4px; }
  :global(.dot) { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
  :global(.dot.ok) { background: var(--accent); }
  :global(.dot.syncing), :global(.dot.connecting) { background: var(--accent); opacity: 0.5; }
  :global(.dot.error), :global(.dot.reconnect) { background: var(--calm); }
</style>
