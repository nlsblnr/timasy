<script>
  // Serien (V-5): alle Serien; bearbeiten, beenden, carry_over umschalten, löschen.
  import { api } from '../lib/api.js'
  import { app, reload, showError } from '../lib/state.svelte.js'
  import { formatShort } from '../lib/dates.js'
  import { describe } from '../lib/recurrence.js'
  import ConfirmBar from '../components/ConfirmBar.svelte'
  import SeriesEditor from '../components/SeriesEditor.svelte'

  let list = $state([])
  let editingId = $state(null)
  let confirmingId = $state(null)   // Serie, deren Löschen gerade bestätigt wird

  $effect(() => {
    app.version
    api.seriesList().then((l) => (list = l)).catch(showError)
  })

  async function call(fn) {
    try {
      await fn()
      reload()
    } catch (e) {
      showError(e)
    }
  }

  const ended = (s) => s.next_occurrence == null
</script>

<h1>Serien</h1>
<p class="intro">Neue Serie: <kbd>n</kbd> → Details → „Wiederholt sich“.</p>

{#if list.length}
  <ul>
    {#each list as s (s.id)}
      <li class:ended={ended(s)}>
        <div class="main">
          <div class="info">
            <span class="title">{s.title}</span>
            <span class="meta">
              <span>{s.tier === 'must' ? 'Pflicht' : 'Bonus'} · {s.scope === 'week' ? 'Woche' : 'Tag'}</span>
              <span>{describe(s)}</span>
              <span>{ended(s) ? 'beendet' : `nächstes: ${formatShort(s.next_occurrence)}`}</span>
              {#each s.task.tags as tag}<span>#{tag}</span>{/each}
            </span>
          </div>
          <label class="toggle" title="Unerledigte Vorkommen übertragen statt „verpasst“ (R-13)">
            <input type="checkbox" checked={s.carry_over}
                   onchange={(e) => call(() => api.setCarryOver(s.id, e.target.checked))} />
            übertragen
          </label>
          <button class="text" onclick={() => (editingId = editingId === s.id ? null : s.id)}>Bearbeiten</button>
          {#if !ended(s)}
            <button class="text" onclick={() => call(() => api.endSeries(s.id))}
                    title="Endet heute; offene Vorkommen ab morgen werden entfernt">Beenden</button>
          {/if}
          <button class="text" onclick={() => (confirmingId = s.id)}
                  title="Erledigte Vorkommen bleiben erhalten">Löschen</button>
        </div>
        {#if confirmingId === s.id}
          <ConfirmBar message={`Serie „${s.title}“ wirklich löschen? Erledigte Vorkommen bleiben erhalten.`}
                      onconfirm={() => { confirmingId = null; call(() => api.deleteSeries(s.id)) }}
                      oncancel={() => (confirmingId = null)} />
        {/if}
        {#if editingId === s.id}
          <SeriesEditor seriesId={s.id} onclose={() => (editingId = null)} />
        {/if}
      </li>
    {/each}
  </ul>
{:else}
  <p class="empty">Noch keine Serien.</p>
{/if}

<style>
  h1 { font-size: 2rem; font-weight: 600; margin: 0 0 4px; }
  .intro { color: var(--muted); margin: 0 0 20px; font-size: 0.9rem; }
  ul { padding: 0; margin: 0; }
  li { list-style: none; padding: 12px 0; border-bottom: 1px solid var(--line); }
  .main { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
  .info { flex: 1 1 300px; display: grid; gap: 2px; }
  .title { font-weight: 500; }
  .ended .title { color: var(--muted); }
  .meta { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 0.8rem; color: var(--muted); }
  .toggle { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; margin-right: 8px; }
  .toggle input { width: 16px; height: 16px; }
  .empty { color: var(--muted); }
</style>
