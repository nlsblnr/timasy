<script>
  // Ein Eintrag in einer Liste: abhaken, Stufe wechseln, bearbeiten,
  // aus dem Zeitraum entfernen oder die Aufgabe löschen.
  import { api } from '../lib/api.js'
  import { overdueText } from '../lib/dates.js'
  import { deleteTaskWithUndo, reload, showError } from '../lib/state.svelte.js'
  import TaskEditor from './TaskEditor.svelte'

  // assignTo: optional, ein Tag, dem ein Wochen-Eintrag zugewiesen werden kann (R-6)
  let { entry, assignTo = null, assignLabel = '' } = $props()
  let editing = $state(false)
  let done = $derived(entry.status === 'done')

  async function call(fn) {
    try {
      await fn()
      reload()
    } catch (e) {
      showError(e)
    }
  }

  const toggleDone = () => call(() => api.changeEntry(entry.id, { done: !done }))
  const toggleTier = () =>
    call(() => api.changeEntry(entry.id, { tier: entry.tier === 'must' ? 'bonus' : 'must' }))
  const assign = () => call(() => api.changeEntry(entry.id, { day: assignTo }))
  const remove = () => call(() => api.removeEntry(entry.id))
</script>

<li class="entry" class:done>
  <div class="main">
    <input type="checkbox" checked={done} onchange={toggleDone}
           aria-label="{entry.title} abhaken" />
    <div class="text">
      <span class="title">{entry.title}</span>
      <span class="meta">
        {#if entry.overdue && !done}<span class="overdue">{overdueText(entry.overdue_days)}</span>{/if}
        {#if entry.task.estimated_minutes}<span>{entry.task.estimated_minutes} min</span>{/if}
        {#each entry.task.tags as tag}<span class="tag">#{tag}</span>{/each}
      </span>
    </div>
    <div class="buttons">
      {#if assignTo}
        <button class="text" onclick={assign} title="Diesem Tag zuweisen">{assignLabel}</button>
      {/if}
      <button class="text" onclick={toggleTier}
              title="Stufe wechseln">{entry.tier === 'must' ? '→ Bonus' : '→ Pflicht'}</button>
      <details class="more">
        <summary class="icon" title="Mehr">⋯</summary>
        <div class="menu">
          <button class="text" onclick={() => (editing = true)}>Bearbeiten</button>
          <button class="text" onclick={remove}>Aus Zeitraum entfernen</button>
          <button class="text" onclick={() => deleteTaskWithUndo(entry.task_id, entry.title)}>
            Aufgabe löschen
          </button>
        </div>
      </details>
    </div>
  </div>
  {#if editing}
    <TaskEditor task={entry.task} onclose={() => (editing = false)} />
  {/if}
</li>

<style>
  .entry { list-style: none; padding: 10px 0; border-bottom: 1px solid var(--line); }
  .main { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
  .text { flex: 1 1 160px; display: grid; gap: 2px; min-width: 0; }
  .title { overflow-wrap: anywhere; }
  .done .title { color: var(--muted); text-decoration: line-through; }
  .meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.8rem; color: var(--muted); }
  .meta:empty { display: none; }
  /* UX-5: sachlicher Hinweis, keine Warnfarbe */
  .overdue { color: var(--calm); }
  .buttons { display: flex; align-items: center; gap: 4px; margin-left: auto; white-space: nowrap; }
  .more { position: relative; }
  .more summary { list-style: none; cursor: pointer; }
  .more summary::-webkit-details-marker { display: none; }
  .menu {
    position: absolute; right: 0; top: 100%; z-index: 5; display: grid; min-width: 200px;
    background: var(--surface-raised); border-radius: 12px; padding: 6px;
    box-shadow: 0 4px 16px var(--shadow);
  }
  .menu button { text-align: left; }
</style>
