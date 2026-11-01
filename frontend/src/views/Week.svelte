<script>
  // Wochenansicht (V-2): Raster Montag bis Sonntag mit Zeitachse.
  // Seitenleiste mit Wochen-Einträgen (nach Stufe) und nicht eingeplanten
  // Tages-Einträgen; diese lassen sich auf einen Tag oder eine Uhrzeit ziehen.
  import { api } from '../lib/api.js'
  import { app, showError } from '../lib/state.svelte.js'
  import { addDays, formatShort } from '../lib/dates.js'
  import EntryItem from '../components/EntryItem.svelte'
  import ProgressBar from '../components/ProgressBar.svelte'
  import TimeGrid from '../components/TimeGrid.svelte'

  let data = $state(null)

  $effect(() => {
    const date = app.date
    app.version
    api.week(date)
      .then((d) => {
        data = d
        app.today = d.today
      })
      .catch(showError)
  })

  const notDeleted = (e) => e.task_id !== app.pendingDelete?.taskId
  let entries = $derived(data ? data.entries.filter(notDeleted) : [])
  let weekEntries = $derived(data ? data.week_entries.filter(notDeleted) : [])
  let weekMust = $derived(weekEntries.filter((e) => e.tier === 'must'))
  let weekBonus = $derived(weekEntries.filter((e) => e.tier === 'bonus'))
  let unplanned = $derived(entries.filter((e) => !e.block && e.status === 'open'))

  // Kalenderwoche nach ISO 8601 (Woche mit dem ersten Donnerstag des Jahres)
  function isoWeek(iso) {
    const d = new Date(iso + 'T12:00:00')
    d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7))
    const firstThursday = new Date(d.getFullYear(), 0, 4)
    return 1 + Math.round(((d - firstThursday) / 86400000 - 3 + ((firstThursday.getDay() + 6) % 7)) / 7)
  }
</script>

{#if data}
  <header>
    <div class="nav">
      <button class="icon" onclick={() => (app.date = addDays(data.week_start, -7))}
              title="Vorherige Woche" aria-label="Vorherige Woche">‹</button>
      <button class="icon" onclick={() => (app.date = addDays(data.week_start, 7))}
              title="Nächste Woche" aria-label="Nächste Woche">›</button>
      {#if !data.days.includes(data.today)}
        <button class="text" onclick={() => (app.date = null)}>Diese Woche</button>
      {/if}
    </div>
    <h1>KW {isoWeek(data.week_start)} <span class="range">· {formatShort(data.days[0])} – {formatShort(data.days[6])}</span></h1>
    <div class="progress">
      <ProgressBar label="Wochenfortschritt Pflicht" prominent done={data.progress.must_done}
                   total={data.progress.must_total} ratio={data.progress.must_ratio} />
      <ProgressBar label="Gesamt" done={data.progress.all_done}
                   total={data.progress.all_total} ratio={data.progress.all_ratio} />
    </div>
  </header>

  <div class="layout">
    <aside>
      <p class="hint">Auf einen Tag ziehen: zuweisen. Auf eine Uhrzeit ziehen: einplanen.</p>
      <h2>Woche · Pflicht</h2>
      {#if weekMust.length}<ul>{#each weekMust as entry (entry.id)}<EntryItem {entry} />{/each}</ul>
      {:else}<p class="empty">Keine.</p>{/if}
      <h2>Woche · Bonus</h2>
      {#if weekBonus.length}<ul>{#each weekBonus as entry (entry.id)}<EntryItem {entry} />{/each}</ul>
      {:else}<p class="empty">Keine.</p>{/if}
      <h2>Nicht eingeplant</h2>
      {#if unplanned.length}<ul>{#each unplanned as entry (entry.id)}<EntryItem {entry} />{/each}</ul>
      {:else}<p class="empty">Alle Tages-Einträge sind eingeplant.</p>{/if}
    </aside>

    <section class="grid">
      <TimeGrid days={data.days} today={data.today} {entries} events={data.events} height="calc(100vh - 300px)" />
    </section>
  </div>
{/if}

<style>
  header { display: grid; gap: 8px; margin-bottom: 16px; }
  .nav { display: flex; gap: 4px; }
  h1 { margin: 0; font-size: 1.6rem; font-weight: 600; }
  .range { color: var(--muted); font-weight: 400; font-size: 1.1rem; }
  .progress { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; align-items: end; }
  .layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 24px; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
  aside { max-height: calc(100vh - 260px); overflow-y: auto; padding-right: 8px; }
  h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em;
       color: var(--muted); margin: 20px 0 4px; font-weight: 600; }
  .hint { font-size: 0.8rem; color: var(--muted); margin: 0; }
  ul { padding: 0; margin: 0; }
  .empty { color: var(--muted); font-size: 0.85rem; margin: 4px 0; }
  /* In der schmalen Seitenleiste Einträge kompakter darstellen */
  aside :global(.entry) { font-size: 0.9rem; padding: 6px 0; }
</style>
