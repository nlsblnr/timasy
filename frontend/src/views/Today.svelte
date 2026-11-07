<script>
  // Heute-Ansicht (V-1): Datum, Fortschritt, Pflicht- und Bonus-Liste,
  // darunter "Diese Woche" mit offenen Wochen-Einträgen (v0.10).
  // Daneben die Tages-Zeitleiste mit Blöcken (Akzentfarbe) und Fremdterminen (grau).
  import { api } from '../lib/api.js'
  import { app, showError } from '../lib/state.svelte.js'
  import { addDays, formatLong, formatShort, relativeLabel } from '../lib/dates.js'
  import EntryItem from '../components/EntryItem.svelte'
  import ProgressBar from '../components/ProgressBar.svelte'
  import TagFilter from '../components/TagFilter.svelte'
  import TimeGrid from '../components/TimeGrid.svelte'
  import { isShortcut } from '../lib/keys.js'
  import { reload } from '../lib/state.svelte.js'

  let data = $state(null)
  let tagFilter = $state(null)

  // Neu laden, wenn sich der Tag ändert oder irgendwo etwas gespeichert wurde.
  // $effect läuft automatisch erneut, wenn app.date oder app.version sich ändern.
  $effect(() => {
    const date = app.date
    app.version
    api.day(date)
      .then((d) => {
        data = d
        app.today = d.today
      })
      .catch(showError)
  })

  const visible = (entries) =>
    entries.filter((e) =>
      e.task_id !== app.pendingDelete?.taskId &&
      (!tagFilter || e.task.tags.includes(tagFilter)))

  let entries = $derived(data ? visible(data.entries) : [])
  let must = $derived(entries.filter((e) => e.tier === 'must'))
  let bonus = $derived(entries.filter((e) => e.tier === 'bonus'))
  let weekEntries = $derived(data ? visible(data.week_entries) : [])
  let allTags = $derived(
    data ? [...new Set([...data.entries, ...data.week_entries].flatMap((e) => e.task.tags))].sort() : [])
  // Einem vergangenen Tag zuweisen ergibt keinen Sinn: Die Übertragung (R-9)
  // würde den Eintrag sofort als überfällig auf heute legen.
  // --- Tastatur (UX-4) ------------------------------------------------------
  // ↑/↓ wählen, Leertaste abhaken, Shift+←/→ verschieben, t Stufe, Enter
  // bearbeiten, ←/→ Tag wechseln. Übersicht: Taste ?
  let ordered = $derived([...must, ...bonus])
  let editingId = $state(null)
  let selected = $derived(ordered.find((e) => e.id === app.selectedId) ?? null)

  async function call(fn) {
    try {
      await fn()
      reload()
    } catch (e) {
      showError(e)
    }
  }

  function step(delta) {
    if (!ordered.length) return
    const i = ordered.findIndex((e) => e.id === app.selectedId)
    const next = i === -1 ? (delta > 0 ? 0 : ordered.length - 1)
                          : Math.min(Math.max(i + delta, 0), ordered.length - 1)
    app.selectedId = ordered[next].id
  }

  function onkeydown(e) {
    if (!data || app.helpOpen || editingId || !isShortcut(e)) return
    const key = e.key
    if (key === 'ArrowDown' || key === 'ArrowUp') {
      e.preventDefault()
      step(key === 'ArrowDown' ? 1 : -1)
    } else if ((key === 'ArrowLeft' || key === 'ArrowRight') && e.shiftKey) {
      if (!selected || selected.status !== 'open') return
      e.preventDefault()
      const moved = selected
      // Auswahl auf den Nachbarn setzen, da der Eintrag die Liste verlässt
      const i = ordered.indexOf(moved)
      app.selectedId = (ordered[i + 1] ?? ordered[i - 1])?.id ?? null
      call(() => api.changeEntry(moved.id, { day: addDays(moved.period_start, key === 'ArrowRight' ? 1 : -1) }))
    } else if (key === 'ArrowLeft' || key === 'ArrowRight') {
      e.preventDefault()
      app.date = addDays(data.date, key === 'ArrowRight' ? 1 : -1)
    } else if (key === ' ' && selected) {
      e.preventDefault()
      call(() => api.changeEntry(selected.id, { done: selected.status !== 'done' }))
    } else if (key === 't' && selected) {
      call(() => api.changeEntry(selected.id, { tier: selected.tier === 'must' ? 'bonus' : 'must' }))
    } else if (key === 'Enter' && selected) {
      e.preventDefault()
      editingId = selected.id
    }
  }

  let relative = $derived(data ? relativeLabel(data.date, data.today) : null)
</script>

<svelte:window {onkeydown} />

{#if data}
  <div class="layout">
    <section class="day">
      <header>
        <div class="nav">
          <button class="icon" onclick={() => (app.date = addDays(data.date, -1))}
                  title="Vorheriger Tag" aria-label="Vorheriger Tag">‹</button>
          <button class="icon" onclick={() => (app.date = addDays(data.date, 1))}
                  title="Nächster Tag" aria-label="Nächster Tag">›</button>
          {#if data.date !== data.today}
            <button class="text" onclick={() => (app.date = null)}>Heute</button>
          {/if}
        </div>
        <p class="relative">{relative ?? ''}</p>
        <h1>{formatLong(data.date)}</h1>
      </header>

      <div class="progress">
        <ProgressBar label="Pflicht" prominent done={data.progress.must_done}
                     total={data.progress.must_total} ratio={data.progress.must_ratio} />
        <ProgressBar label="Gesamt" done={data.progress.all_done}
                     total={data.progress.all_total} ratio={data.progress.all_ratio} />
        {#if data.progress.minimum_reached}
          <p class="minimum">Minimum erreicht</p>
        {/if}
      </div>

      <TagFilter tags={allTags} bind:selected={tagFilter} />

      <h2>Pflicht</h2>
      {#if must.length}
        <ul>{#each must as entry (entry.id)}
          <EntryItem {entry} selected={entry.id === app.selectedId}
                     onselect={() => (app.selectedId = entry.id)}
                     bind:editing={() => editingId === entry.id, (v) => (editingId = v ? entry.id : null)} />
        {/each}</ul>
      {:else}
        <p class="empty">Keine Pflicht-Einträge. Mit <kbd>n</kbd> erfassen.</p>
      {/if}

      <h2>Bonus</h2>
      {#if bonus.length}
        <ul>{#each bonus as entry (entry.id)}
          <EntryItem {entry} selected={entry.id === app.selectedId}
                     onselect={() => (app.selectedId = entry.id)}
                     bind:editing={() => editingId === entry.id, (v) => (editingId = v ? entry.id : null)} />
        {/each}</ul>
      {:else}
        <p class="empty">Keine Bonus-Einträge.</p>
      {/if}

      <div class="week">
        <h2>Diese Woche</h2>
        <p class="sub">ab {formatShort(data.week_start)}</p>
        <ProgressBar label="Wochenfortschritt" done={data.week_progress.must_done}
                     total={data.week_progress.must_total} ratio={data.week_progress.must_ratio} />
        {#if weekEntries.length}
          <ul>
            {#each weekEntries as entry (entry.id)}
              <EntryItem {entry} assignTo={data.date >= data.today ? data.date : null}
                         assignLabel={relative ? `→ ${relative}` : '→ Tag'} />
            {/each}
          </ul>
        {:else}
          <p class="empty">Keine offenen Wochen-Einträge.</p>
        {/if}
      </div>
    </section>

    <aside class="side">
      <h2>Zeitleiste</h2>
      <p class="sub">Einträge hierher ziehen, um sie einzuplanen.</p>
      <TimeGrid days={[data.date]} today={data.today} showHeader={false} height="calc(100vh - 170px)"
                events={data.events}
                entries={data.entries.filter((e) => e.task_id !== app.pendingDelete?.taskId)} />

    </aside>
  </div>
{/if}

<style>
  .layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, 1fr); gap: 48px; }
  @media (max-width: 820px) { .layout { grid-template-columns: 1fr; } }
  header { display: grid; gap: 2px; margin-bottom: 20px; }
  .nav { display: flex; gap: 4px; align-items: center; }
  .relative { margin: 8px 0 0; color: var(--accent); font-weight: 600; min-height: 1.2em; }
  h1 { margin: 0; font-size: 2rem; font-weight: 600; }
  .progress { display: grid; gap: 12px; margin-bottom: 20px; }
  .minimum { margin: 0; color: var(--accent); font-weight: 600; }
  h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em;
       color: var(--muted); margin: 28px 0 4px; font-weight: 600; }
  .side h2 { margin-top: 8px; }
  .week { margin-top: 40px; }
  .sub { margin: 0 0 16px; color: var(--muted); font-size: 0.85rem; }
  ul { padding: 0; margin: 0; }
  .empty { color: var(--muted); font-size: 0.9rem; }
  .side { border-left: 1px solid var(--line); padding-left: 32px; position: sticky; top: 12px; align-self: start; }
  @media (max-width: 820px) { .side { border: none; padding: 0; } }
</style>
