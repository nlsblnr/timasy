<script>
  // Wiederholung erfassen wie in Kalender-Apps (V-8):
  // Rhythmus, Intervall, Wochentage, Ende – mit Vorschau der nächsten Vorkommen.
  import { api } from '../lib/api.js'
  import { formatShort } from '../lib/dates.js'
  import { WEEKDAYS, monthlyText, recurrencePayload } from '../lib/recurrence.js'

  // rec: { freq, interval, weekdays, monthly_by, end_type, until_date, count }
  let { rec = $bindable(), startsOn, scope = 'day' } = $props()

  let previewDates = $state([])
  let previewError = $state('')

  // R-24: Wochen-Serien nur wöchentlich bzw. alle n Wochen
  $effect(() => {
    if (scope === 'week') {
      rec.freq = 'weekly'
      rec.weekdays = []
    }
  })

  // Vorschau neu laden, sobald sich etwas ändert (kurz verzögert)
  $effect(() => {
    const data = { ...recurrencePayload(rec), starts_on: startsOn, scope }
    if (!startsOn) return
    const timer = setTimeout(() => {
      api.previewSeries(data)
        .then((dates) => { previewDates = dates; previewError = '' })
        .catch((e) => { previewDates = []; previewError = e.message })
    }, 200)
    return () => clearTimeout(timer)
  })

  function toggleWeekday(d) {
    rec.weekdays = rec.weekdays.includes(d)
      ? rec.weekdays.filter((x) => x !== d)
      : [...rec.weekdays, d].sort()
  }

  const unitLabel = { daily: 'Tage', weekly: 'Wochen', monthly: 'Monate', yearly: 'Jahre' }
</script>

<div class="rec">
  <div class="row">
    <label>Rhythmus
      <select bind:value={rec.freq} disabled={scope === 'week'}>
        <option value="daily">täglich</option>
        <option value="weekly">wöchentlich</option>
        <option value="monthly">monatlich</option>
        <option value="yearly">jährlich</option>
      </select>
    </label>
    <label>Alle
      <span class="inline">
        <input type="number" min="1" bind:value={rec.interval} class="small" />
        {unitLabel[rec.freq]}
      </span>
    </label>
    {#if rec.freq === 'monthly' && startsOn}
      <label>Am
        <select bind:value={rec.monthly_by}>
          <option value="day">{monthlyText(startsOn, 'day')}</option>
          <option value="weekday">{monthlyText(startsOn, 'weekday')}</option>
        </select>
      </label>
    {/if}
  </div>

  {#if rec.freq === 'weekly' && scope === 'day'}
    <div class="weekdays" role="group" aria-label="Wochentage">
      {#each WEEKDAYS as name, d}
        <button type="button" class="chip" class:active={rec.weekdays.includes(d)}
                aria-pressed={rec.weekdays.includes(d)} onclick={() => toggleWeekday(d)}>{name}</button>
      {/each}
      <span class="hint">{rec.weekdays.length ? '' : 'ohne Auswahl: Wochentag des Starts'}</span>
    </div>
  {/if}

  <div class="row">
    <label>Ende
      <select bind:value={rec.end_type}>
        <option value="never">nie</option>
        <option value="until">am Datum</option>
        <option value="count">nach n Mal</option>
      </select>
    </label>
    {#if rec.end_type === 'until'}
      <label>Letzter Tag <input type="date" bind:value={rec.until_date} min={startsOn} required /></label>
    {:else if rec.end_type === 'count'}
      <label>Anzahl <input type="number" min="1" bind:value={rec.count} required /></label>
    {/if}
  </div>

  <p class="preview">
    {#if previewError}{previewError}
    {:else if previewDates.length}Nächste: {previewDates.map(formatShort).join(' · ')}{/if}
  </p>
</div>

<style>
  .rec { display: grid; gap: 10px; }
  .row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .inline { display: flex; align-items: center; gap: 8px; color: var(--text); }
  .small { width: 80px; }
  .weekdays { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .weekdays .chip { min-width: 40px; }
  .hint { font-size: 0.8rem; color: var(--muted); }
  .preview { margin: 0; font-size: 0.85rem; color: var(--muted); min-height: 1.2em; }
</style>
