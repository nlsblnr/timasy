<script>
  // Monatsansicht (V-3): pro Tag die Zahl offener Pflicht-Einträge und
  // kleine Striche für eingeplante Blöcke (Fremdtermine folgen in M4).
  // Klick auf einen Tag öffnet ihn in der Heute-Ansicht.
  import { api } from '../lib/api.js'
  import { app, showError } from '../lib/state.svelte.js'
  import { parseISO, toISO } from '../lib/dates.js'

  let data = $state(null)

  $effect(() => {
    const date = app.date
    app.version
    api.month(date)
      .then((d) => {
        data = d
        app.today = d.today
      })
      .catch(showError)
  })

  function shiftMonth(n) {
    const d = parseISO(data.month + '-01')
    d.setMonth(d.getMonth() + n)
    app.date = toISO(d)
  }

  function openDay(day) {
    app.date = day
    app.view = 'today'
  }

  const monthTitle = new Intl.DateTimeFormat('de-CH', { month: 'long', year: 'numeric' })
  const weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
  const MAX_STROKES = 5
</script>

{#if data}
  <header>
    <div class="nav">
      <button class="icon" onclick={() => shiftMonth(-1)} title="Vorheriger Monat"
              aria-label="Vorheriger Monat">‹</button>
      <button class="icon" onclick={() => shiftMonth(1)} title="Nächster Monat"
              aria-label="Nächster Monat">›</button>
      {#if !data.today.startsWith(data.month)}
        <button class="text" onclick={() => (app.date = null)}>Dieser Monat</button>
      {/if}
    </div>
    <h1>{monthTitle.format(parseISO(data.month + '-01'))}</h1>
  </header>

  <div class="month">
    {#each weekdays as wd}<div class="wd">{wd}</div>{/each}
    {#each data.weeks as week}
      {#each week as day (day.date)}
        <button class="day" class:other={!day.in_month} class:today={day.date === data.today}
                onclick={() => openDay(day.date)}
                aria-label="{day.date}: {day.open_must} offene Pflicht-Einträge">
          <span class="num">{parseISO(day.date).getDate()}</span>
          {#if day.open_must}<span class="must" title="Offene Pflicht-Einträge">{day.open_must}</span>{/if}
          <span class="strokes">
            {#each Array(Math.min(day.blocks, MAX_STROKES)) as _}<span class="stroke"></span>{/each}
          </span>
        </button>
      {/each}
    {/each}
  </div>
{/if}

<style>
  header { display: grid; gap: 8px; margin-bottom: 16px; }
  .nav { display: flex; gap: 4px; }
  h1 { margin: 0; font-size: 2rem; font-weight: 600; }
  .month { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .wd { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; padding: 4px 8px; }
  .day {
    position: relative; display: grid; grid-template-rows: auto 1fr auto; align-content: start;
    min-height: 92px; padding: 8px; text-align: left; border-radius: 12px; background: var(--surface);
  }
  .day:hover { background: color-mix(in srgb, var(--accent) 10%, var(--surface)); }
  .day.other { background: transparent; color: var(--muted); }
  .num { font-weight: 600; }
  .today .num { color: var(--accent); }
  .must { position: absolute; top: 8px; right: 10px; font-size: 0.8rem; color: var(--muted); }
  .strokes { display: flex; gap: 3px; flex-wrap: wrap; }
  .stroke { width: 14px; height: 3px; border-radius: 2px; background: var(--accent); opacity: 0.7; }
</style>
