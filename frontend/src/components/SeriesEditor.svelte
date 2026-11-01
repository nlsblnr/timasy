<script>
  // Serie bzw. Vorkommen bearbeiten (R-17, R-25, V-5, V-8).
  // Mit entry: Auswahl "nur dieses Vorkommen / dieses und alle folgenden / alle".
  // Ohne entry (aus der Serien-Liste): immer "alle".
  import { api } from '../lib/api.js'
  import { reload, showError } from '../lib/state.svelte.js'
  import { minutesToTime, recurrencePayload, timeToMinutes } from '../lib/recurrence.js'
  import { parseTagList } from '../lib/tags.js'
  import RecurrenceFields from './RecurrenceFields.svelte'
  import TagInput from './TagInput.svelte'

  let { seriesId, entry = null, onclose } = $props()

  let series = $state(null)
  let mode = $state('this')
  let form = $state(null)

  // svelte-ignore state_referenced_locally
  api.getSeries(seriesId)
    .then((s) => {
      series = s
      mode = entry ? 'this' : 'all'
      fill()
    })
    .catch(showError)

  // Formular mit den Werten des Vorkommens bzw. der Serie füllen
  function fill() {
    const task = mode === 'this' && entry ? entry.task : series.task
    const block = mode === 'this' && entry?.block
    form = {
      title: task.title,
      notes: task.notes,
      minutes: task.estimated_minutes ?? '',
      tags: task.tags.join(', '),
      tier: mode === 'this' && entry ? entry.tier : series.tier,
      day: entry?.period_start,
      time: block ? minutesToTime(block.start_minute) : minutesToTime(series.start_minute),
      duration: block ? block.end_minute - block.start_minute : (series.duration_minutes ?? ''),
      starts_on: series.starts_on,
      carry_over: series.carry_over,
      rec: {
        freq: series.freq, interval: series.interval, weekdays: series.weekdays,
        monthly_by: series.monthly_by, end_type: series.end_type,
        until_date: series.until_date ?? '', count: series.count ?? 10,
      },
    }
  }

  function changeMode(m) {
    mode = m
    fill()
  }

  let isDay = $derived(series?.scope === 'day')

  async function save(event) {
    event.preventDefault()
    const data = {
      title: form.title,
      notes: form.notes,
      estimated_minutes: form.minutes === '' ? null : Number(form.minutes),
      tags: parseTagList(form.tags),
      tier: form.tier,
    }
    if (isDay) {
      data.start_minute = timeToMinutes(form.time)          // leer = ohne Uhrzeit
      data.duration_minutes = form.duration === '' ? null : Number(form.duration)
    }
    if (mode === 'this') {
      if (isDay) data.day = form.day
    } else {
      Object.assign(data, recurrencePayload(form.rec), { carry_over: form.carry_over })
      if (mode === 'all') data.starts_on = form.starts_on
    }
    try {
      if (entry) await api.editOccurrence(entry.id, { mode, ...data })
      else await api.updateSeries(seriesId, data)
      reload()
      onclose()
    } catch (e) {
      showError(e)
    }
  }
</script>

{#if form}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions (Esc schliesst) -->
  <form class="editor" onsubmit={save} onkeydown={(e) => e.key === 'Escape' && onclose()}>
    {#if entry}
      <div class="modes" role="radiogroup" aria-label="Was ändern?">
        <button type="button" class="chip" class:active={mode === 'this'} onclick={() => changeMode('this')}>Nur dieses Vorkommen</button>
        <button type="button" class="chip" class:active={mode === 'following'} onclick={() => changeMode('following')}>Dieses und alle folgenden</button>
        <button type="button" class="chip" class:active={mode === 'all'} onclick={() => changeMode('all')}>Alle</button>
      </div>
    {/if}

    <label>Titel <input type="text" bind:value={form.title} required /></label>
    <label>Notiz <textarea rows="2" bind:value={form.notes}></textarea></label>
    <div class="row">
      <label>Stufe
        <select bind:value={form.tier}>
          <option value="must">Pflicht</option>
          <option value="bonus">Bonus</option>
        </select>
      </label>
      <label>Geschätzte Dauer (Minuten) <input type="number" min="1" bind:value={form.minutes} /></label>
      <label>Tags <TagInput bind:value={form.tags} /></label>
    </div>

    {#if isDay}
      <div class="row">
        {#if mode === 'this'}
          <label>Tag <input type="date" bind:value={form.day} required /></label>
        {/if}
        <label>Uhrzeit (leer = ohne) <input type="time" bind:value={form.time} /></label>
        <label>Dauer des Blocks (Minuten) <input type="number" min="1" bind:value={form.duration} /></label>
      </div>
    {/if}

    {#if mode !== 'this'}
      {#if mode === 'all'}
        <label class="narrow">Start <input type="date" bind:value={form.starts_on} required /></label>
      {/if}
      <RecurrenceFields bind:rec={form.rec} scope={series.scope}
                        startsOn={mode === 'all' ? form.starts_on : entry?.occurrence_date} />
      <label class="check">
        <input type="checkbox" bind:checked={form.carry_over} />
        Unerledigte Vorkommen auf den nächsten Tag übertragen (sonst „verpasst“)
      </label>
    {/if}

    <div class="actions">
      <button type="button" class="text" onclick={onclose}>Abbrechen</button>
      <button type="submit" class="filled">Speichern</button>
    </div>
  </form>
{/if}

<style>
  .editor { display: grid; gap: 12px; padding: 12px 0 4px; }
  .modes { display: flex; flex-wrap: wrap; gap: 6px; }
  .row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .narrow { max-width: 220px; }
  .check { display: flex; align-items: center; gap: 8px; color: var(--text); font-size: 0.9rem; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
