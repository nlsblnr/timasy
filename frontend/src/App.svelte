<script>
  // Rahmen der App: Navigation, Tastenkürzel, Schnellerfassung,
  // Rückgängig-Leiste und Fehlermeldungen.
  //
  // Tastenkürzel (wenn kein Eingabefeld aktiv ist):
  //   n = Schnellerfassung, h = Heute, b = Backlog
  import { onMount } from 'svelte'
  import { app, commitPendingDelete, reload, undoDelete } from './lib/state.svelte.js'
  import QuickCapture from './components/QuickCapture.svelte'
  import Today from './views/Today.svelte'
  import Backlog from './views/Backlog.svelte'

  let quickOpen = $state(false)

  function isTyping(target) {
    return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
  }

  function onkeydown(e) {
    if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return
    if (e.key === 'n') { e.preventDefault(); quickOpen = true }
    if (e.key === 'h') app.view = 'today'
    if (e.key === 'b') app.view = 'backlog'
  }

  onMount(() => {
    reload()
    // Jede Minute neu laden: So greift der Tageswechsel (R-9), solange die App läuft.
    const timer = setInterval(reload, 60_000)
    window.addEventListener('focus', reload)
    // Ein noch ausstehendes Löschen beim Schliessen des Fensters ausführen
    window.addEventListener('pagehide', commitPendingDelete)
    return () => {
      clearInterval(timer)
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
    <button class="tab" class:active={app.view === 'backlog'} onclick={() => (app.view = 'backlog')}
            title="Backlog (b)">Backlog</button>
    <span class="spacer"></span>
    <button class="filled" onclick={() => (quickOpen = true)} title="Neue Aufgabe (n)">+ Neu</button>
  </nav>

  {#if quickOpen}
    <div class="quick"><QuickCapture onclose={() => (quickOpen = false)} /></div>
  {/if}

  <main>
    {#if app.view === 'today'}<Today />{:else}<Backlog />{/if}
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
  .shell { max-width: 1100px; margin: 0 auto; padding: 16px 32px 96px; }
  nav { display: flex; align-items: center; gap: 4px; margin-bottom: 24px; }
  .brand { font-weight: 700; margin-right: 16px; }
  .spacer { flex: 1; }
  .quick { margin-bottom: 24px; }
  .snackbar {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
    display: flex; align-items: center; gap: 16px; padding: 10px 12px 10px 20px;
    border-radius: 12px; background: var(--inverse); color: var(--inverse-text);
  }
  .snackbar button { color: var(--inverse-accent); }
</style>
