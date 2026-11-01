<script>
  // Details einer Aufgabe bearbeiten: Titel, Notiz, Dauer, Tags.
  import { api } from '../lib/api.js'
  import { reload, showError } from '../lib/state.svelte.js'
  import { parseTagList } from '../lib/tags.js'
  import TagInput from './TagInput.svelte'

  let { task, onclose } = $props()

  // Eigene Kopie der Werte, damit "Abbrechen" nichts verändert.
  // svelte-ignore state_referenced_locally
  let form = $state({
    title: task.title,
    notes: task.notes,
    minutes: task.estimated_minutes ?? '',
    tags: task.tags.join(', '),
  })

  async function save(event) {
    event.preventDefault()
    try {
      await api.updateTask(task.id, {
        title: form.title,
        notes: form.notes,
        estimated_minutes: form.minutes === '' ? null : Number(form.minutes),
        tags: parseTagList(form.tags),
      })
      reload()
      onclose()
    } catch (e) {
      showError(e)
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Esc schliesst) -->
<form class="editor" onsubmit={save} onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <label>Titel <input type="text" bind:value={form.title} required /></label>
  <label>Notiz <textarea rows="3" bind:value={form.notes}></textarea></label>
  <div class="two">
    <label>Geschätzte Dauer (Minuten)
      <input type="number" min="1" step="1" bind:value={form.minutes} />
    </label>
    <label>Tags <TagInput bind:value={form.tags} /></label>
  </div>
  <div class="actions">
    <button type="button" class="text" onclick={onclose}>Abbrechen</button>
    <button type="submit" class="filled">Speichern</button>
  </div>
</form>

<style>
  .editor { display: grid; gap: 12px; padding: 12px 0 4px; }
  .two { display: grid; grid-template-columns: 1fr 2fr; gap: 12px; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
