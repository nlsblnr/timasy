<script>
  // Backlog (V-4): Aufgaben ohne Zeitraum, mit Suche und Tag-Filter.
  // Von hier aus einem Tag oder einer Woche mit Stufe zuweisen (R-5).
  import { api } from '../lib/api.js'
  import { app, deleteTaskWithUndo, reload, showError } from '../lib/state.svelte.js'
  import TagFilter from '../components/TagFilter.svelte'
  import TaskEditor from '../components/TaskEditor.svelte'

  let tasks = $state([])
  let search = $state('')
  let tagFilter = $state(null)
  let editingId = $state(null)
  let assigningId = $state(null)
  let assign = $state({ scope: 'day', date: '', tier: 'must' })

  $effect(() => {
    app.version
    api.backlog().then((d) => (tasks = d.tasks)).catch(showError)
  })

  let allTags = $derived([...new Set(tasks.flatMap((t) => t.tags))].sort())
  let shown = $derived(tasks.filter((t) =>
    t.id !== app.pendingDelete?.taskId &&
    (!tagFilter || t.tags.includes(tagFilter)) &&
    (!search || (t.title + ' ' + t.notes).toLowerCase().includes(search.toLowerCase()))))

  function startAssign(task) {
    assigningId = task.id
    assign = { scope: 'day', date: app.today, tier: 'must' }
  }

  async function doAssign(task, event) {
    event.preventDefault()
    try {
      await api.createEntry({ task_id: task.id, scope: assign.scope,
                              period_start: assign.date, tier: assign.tier })
      assigningId = null
      reload()
    } catch (e) {
      showError(e)
    }
  }
</script>

<h1>Backlog</h1>
<div class="tools">
  <input type="search" placeholder="Suchen …" bind:value={search} />
  <TagFilter tags={allTags} bind:selected={tagFilter} />
</div>

{#if shown.length}
  <ul>
    {#each shown as task (task.id)}
      <li>
        <div class="main">
          <div class="info">
            <span>{task.title}</span>
            <span class="meta">
              {#if task.estimated_minutes}<span>{task.estimated_minutes} min</span>{/if}
              {#each task.tags as tag}<span>#{tag}</span>{/each}
            </span>
          </div>
          <button class="text" onclick={() => startAssign(task)}>Zuweisen</button>
          <button class="text" onclick={() => (editingId = task.id)}>Bearbeiten</button>
          <button class="text" onclick={() => deleteTaskWithUndo(task.id, task.title)}>Löschen</button>
        </div>

        {#if assigningId === task.id}
          <form class="assign" onsubmit={(e) => doAssign(task, e)}>
            <select bind:value={assign.scope} aria-label="Zeitraum">
              <option value="day">Tag</option>
              <option value="week">Woche</option>
            </select>
            <input type="date" bind:value={assign.date} min={app.today} required aria-label="Datum" />
            <select bind:value={assign.tier} aria-label="Stufe">
              <option value="must">Pflicht</option>
              <option value="bonus">Bonus</option>
            </select>
            <button type="button" class="text" onclick={() => (assigningId = null)}>Abbrechen</button>
            <button type="submit" class="filled">Zuweisen</button>
          </form>
        {/if}

        {#if editingId === task.id}
          <TaskEditor {task} onclose={() => (editingId = null)} />
        {/if}
      </li>
    {/each}
  </ul>
{:else}
  <p class="empty">
    {tasks.length ? 'Keine Treffer.' : 'Der Backlog ist leer. Mit n erfassen.'}
  </p>
{/if}

<style>
  h1 { font-size: 2rem; font-weight: 600; margin: 0 0 20px; }
  .tools { display: grid; gap: 12px; margin-bottom: 16px; }
  ul { padding: 0; margin: 0; }
  li { list-style: none; padding: 10px 0; border-bottom: 1px solid var(--line); }
  .main { display: flex; align-items: center; gap: 4px; }
  .info { flex: 1; display: grid; gap: 2px; }
  .meta { display: flex; gap: 8px; font-size: 0.8rem; color: var(--muted); }
  .meta:empty { display: none; }
  .assign { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 10px; align-items: center; }
  .empty { color: var(--muted); }
</style>
