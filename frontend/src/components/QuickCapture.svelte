<script>
  // Schnellerfassung (V-7). Öffnet sich mit der Taste "n" in jeder Ansicht.
  //  - Enter: speichern
  //  - Tab: Stufe Pflicht/Bonus umschalten (oder Tag-Vorschlag übernehmen)
  //  - Esc: schliessen
  //  - "#name" im Titel fügt einen Tag hinzu
  // In Heute, Woche und Monat entsteht ein Eintrag für den angezeigten Tag,
  // im Backlog eine Aufgabe ohne Zeitraum. "Details" öffnet den erweiterten Dialog.
  import { api } from '../lib/api.js'
  import { app, reload, showError } from '../lib/state.svelte.js'
  import { formatShort } from '../lib/dates.js'
  import { parseTagList, suggest } from '../lib/tags.js'
  import TagInput from './TagInput.svelte'

  let { onclose } = $props()

  let text = $state('')
  let tier = $state('must')               // Standardstufe Pflicht (A-3)
  let extended = $state(false)
  // svelte-ignore state_referenced_locally
  let period = $state(app.view === 'backlog' ? 'none' : 'day')   // 'day' | 'week' | 'none'
  // svelte-ignore state_referenced_locally
  let date = $state(app.date ?? app.today)
  let minutes = $state('')
  let notes = $state('')
  let tags = $state('')
  let input

  // Vorschläge, wenn das letzte Wort mit # beginnt
  let hashWord = $derived(text.match(/(?:^|\s)#([\p{L}\p{N}_-]*)$/u)?.[1] ?? null)
  let suggestions = $derived(hashWord ? suggest(hashWord, app.tags) : [])

  let target = $derived(
    period === 'none' ? 'Backlog'
      : period === 'week' ? `Woche von ${formatShort(date)}`
      : formatShort(date)
  )

  $effect(() => input.focus())

  function completeTag(tag) {
    text = text.replace(/#[\p{L}\p{N}_-]*$/u, `#${tag} `)
    input.focus()
  }

  function onkeydown(e) {
    if (e.key === 'Escape') onclose()
    if (e.key === 'Tab' && e.target === input) {
      e.preventDefault()
      if (suggestions.length) completeTag(suggestions[0])
      else tier = tier === 'must' ? 'bonus' : 'must'
    }
  }

  async function submit(e) {
    e.preventDefault()
    if (!text.trim()) return
    try {
      await api.quick({
        text,
        tier,
        scope: period === 'week' ? 'week' : 'day',
        date: period === 'none' ? null : date,
        notes,
        estimated_minutes: minutes === '' ? null : Number(minutes),
        tags: parseTagList(tags),
      })
      text = ''
      tier = 'must'   // jede neue Eingabe startet wieder mit Pflicht
      notes = ''
      minutes = ''
      tags = ''
      reload()
      input.focus()   // offen lassen für die nächste Eingabe
    } catch (err) {
      showError(err)
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Esc/Tab im ganzen Formular) -->
<form class="quick" onsubmit={submit} {onkeydown}>
  <div class="line">
    <input bind:this={input} bind:value={text} type="text" class="title"
           placeholder="Neue Aufgabe … (#tag, Tab = Stufe, Esc = schliessen)" autocomplete="off" />
    <button type="button" class="chip tier" class:bonus={tier === 'bonus'}
            onclick={() => (tier = tier === 'must' ? 'bonus' : 'must')}>
      {tier === 'must' ? 'Pflicht' : 'Bonus'}
    </button>
    <span class="target">{target}</span>
    <button type="button" class="text" onclick={() => (extended = !extended)}>
      {extended ? 'Weniger' : 'Details'}
    </button>
  </div>

  {#if suggestions.length}
    <div class="suggestions">
      {#each suggestions as tag}
        <button type="button" class="chip" onclick={() => completeTag(tag)}>#{tag}</button>
      {/each}
    </div>
  {/if}

  {#if extended}
    <div class="details">
      <label>Zeitraum
        <select bind:value={period}>
          <option value="day">Tag</option>
          <option value="week">Woche</option>
          <option value="none">Kein Zeitraum (Backlog)</option>
        </select>
      </label>
      {#if period !== 'none'}
        <label>{period === 'week' ? 'Woche mit Datum' : 'Datum'}
          <input type="date" bind:value={date} required />
        </label>
      {/if}
      <label>Dauer (Minuten) <input type="number" min="1" step="1" bind:value={minutes} /></label>
      <label class="wide">Notiz <textarea rows="2" bind:value={notes}></textarea></label>
      <label class="wide">Weitere Tags <TagInput bind:value={tags} /></label>
      <!-- Ein Absende-Knopf sorgt auch dafür, dass Enter in jedem Feld speichert:
           Browser senden ein Formular mit mehreren Feldern nur mit so einem Knopf ab. -->
      <div class="wide submit"><button type="submit" class="filled">Hinzufügen</button></div>
    </div>
  {/if}
</form>

<style>
  .quick {
    background: var(--surface-raised); border-radius: 20px; padding: 12px 16px;
    box-shadow: 0 2px 12px var(--shadow); display: grid; gap: 10px;
  }
  .line { display: flex; align-items: center; gap: 10px; }
  .title { flex: 1; border: none; background: transparent; font-size: 1.05rem; padding: 6px 0; }
  .title:focus { outline: none; }
  .target { font-size: 0.85rem; color: var(--muted); white-space: nowrap; }
  .tier { min-width: 70px; }
  .tier.bonus { background: transparent; }
  .suggestions { display: flex; gap: 6px; flex-wrap: wrap; }
  .details { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .wide { grid-column: 1 / -1; }
  .submit { display: flex; justify-content: flex-end; }
</style>
