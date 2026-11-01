<script>
  // Rahmen der App: Navigation, Tastenkürzel, Schnellerfassung,
  // Rückgängig-Leiste und Fehlermeldungen.
  //
  // Tastenkürzel (wenn kein Eingabefeld aktiv ist):
  //   n = Schnellerfassung, h = Heute, w = Woche, m = Monat, b = Backlog, s = Serien, e = Einstellungen
  import { onMount } from 'svelte'
  import { app, commitPendingDelete, pollSync, reload, undoDelete } from './lib/state.svelte.js'
  import QuickCapture from './components/QuickCapture.svelte'
  import Today from './views/Today.svelte'
  import Backlog from './views/Backlog.svelte'
  import Month from './views/Month.svelte'
  import Series from './views/Series.svelte'
  import Settings from './views/Settings.svelte'
  import Week from './views/Week.svelte'

  let quickOpen = $state(false)

  // Tastenkürzel nur unterdrücken, wenn gerade Text getippt wird
  // (nicht bei Checkboxen oder Knöpfen, z.B. direkt nach dem Abhaken).
  const NON_TEXT_INPUTS = ['checkbox', 'radio', 'button', 'submit', 'range', 'color']
  function isTyping(target) {
    if (target.tagName === 'INPUT') return !NON_TEXT_INPUTS.includes(target.type)
    return ['TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
  }

  function onkeydown(e) {
    if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return
    if (e.key === 'n') { e.preventDefault(); quickOpen = true }
    if (e.key === 'h') app.view = 'today'
    if (e.key === 'w') app.view = 'week'
    if (e.key === 'm') app.view = 'month'
    if (e.key === 'b') app.view = 'backlog'
    if (e.key === 's') app.view = 'series'
    if (e.key === 'e') app.view = 'settings'
  }

  onMount(() => {
    reload()
    pollSync()
    // Zustand des Google-Abgleichs alle 10 Sekunden abfragen (S-10)
    const syncTimer = setInterval(pollSync, 10_000)
    // Jede Minute neu laden: So greift der Tageswechsel (R-9), solange die App läuft.
    const timer = setInterval(reload, 60_000)
    window.addEventListener('focus', reload)
    // Ein noch ausstehendes Löschen beim Schliessen des Fensters ausführen
    window.addEventListener('pagehide', commitPendingDelete)
    return () => {
      clearInterval(timer)
      clearInterval(syncTimer)
      window.removeEventListener('focus', reload)
      window.removeEventListener('pagehide', commitPendingDelete)
    }
  })
</script>

<svelte:window {onkeydown} />

<div class="shell">
  <nav>
    <span class="brand">Timasy</span>
    <button class="tab" class:active={app.view === 'today'} onclick={() => (app.view = 'today')}
            title="Heute (h)">Heute</button>
    <button class="tab" class:active={app.view === 'week'} onclick={() => (app.view = 'week')}
            title="Woche (w)">Woche</button>
    <button class="tab" class:active={app.view === 'month'} onclick={() => (app.view = 'month')}
            title="Monat (m)">Monat</button>
    <button class="tab" class:active={app.view === 'backlog'} onclick={() => (app.view = 'backlog')}
            title="Backlog (b)">Backlog</button>
    <button class="tab" class:active={app.view === 'series'} onclick={() => (app.view = 'series')}
            title="Serien (s)">Serien</button>
    <span class="spacer"></span>
    <!-- Sync-Status dezent als Punkt; Details in den Einstellungen (S-10) -->
    {#if app.sync && !['not_configured', 'disconnected'].includes(app.sync.state)}
      <button class="icon syncdot" onclick={() => (app.view = 'settings')}
              title="Google: {app.sync.state === 'ok' ? 'abgeglichen' : app.sync.state === 'reconnect' ? 'Neu verbinden nötig' : app.sync.state === 'error' ? 'Fehler, wird erneut versucht' : 'wird abgeglichen'}"
              aria-label="Status des Google-Abgleichs"><span class="dot {app.sync.state}"></span></button>
    {/if}
    {#if app.sync?.state === 'reconnect'}
      <button class="text" onclick={() => (app.view = 'settings')}>Neu verbinden</button>
    {/if}
    <button class="tab" class:active={app.view === 'settings'} onclick={() => (app.view = 'settings')}
            title="Einstellungen (e)">Einstellungen</button>
    <button class="filled" onclick={() => (quickOpen = true)} title="Neue Aufgabe (n)">+ Neu</button>
  </nav>

  {#if quickOpen}
    <div class="quick"><QuickCapture onclose={() => (quickOpen = false)} /></div>
  {/if}

  <main>
    {#if app.view === 'today'}<Today />
    {:else if app.view === 'week'}<Week />
    {:else if app.view === 'month'}<Month />
    {:else if app.view === 'series'}<Series />
    {:else if app.view === 'settings'}<Settings />
    {:else}<Backlog />{/if}
  </main>

  {#if app.pendingDelete}
    <div class="snackbar" role="status">
      <span>«{app.pendingDelete.title}» gelöscht</span>
      <button class="text" onclick={undoDelete}>Rückgängig</button>
    </div>
  {/if}
  {#if app.error}
    <div class="snackbar" role="alert">{app.error}</div>
  {/if}
</div>

<style>
  .shell { max-width: 1280px; margin: 0 auto; padding: 16px 32px 96px; }
  nav { display: flex; align-items: center; gap: 4px; margin-bottom: 24px; }
  .brand { font-weight: 700; margin-right: 16px; }
  .spacer { flex: 1; }
  .syncdot { padding: 6px 10px; display: flex; }
  .quick { margin-bottom: 24px; }
  .snackbar {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
    display: flex; align-items: center; gap: 16px; padding: 10px 12px 10px 20px;
    border-radius: 12px; background: var(--inverse); color: var(--inverse-text);
  }
  .snackbar button { color: var(--inverse-accent); }
</style>
