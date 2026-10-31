<script>
  // Eingabe für Tags, getrennt durch Komma oder Leerzeichen.
  // Bestehende Tags werden beim Tippen vorgeschlagen (R-22).
  import { app } from '../lib/state.svelte.js'
  import { suggest } from '../lib/tags.js'

  let { value = $bindable(''), id = undefined } = $props()

  // $derived: wird automatisch neu berechnet, wenn sich value oder app.tags ändert
  let lastWord = $derived(value.split(/[,\s]+/).at(-1) ?? '')
  let suggestions = $derived(suggest(lastWord, app.tags))

  function pick(tag) {
    const parts = value.split(/([,\s]+)/)
    parts[parts.length - 1] = tag
    value = parts.join('') + ', '
  }
</script>

<input {id} type="text" bind:value placeholder="z.B. arbeit, haus" autocomplete="off" />
{#if suggestions.length}
  <div class="suggestions">
    {#each suggestions as tag}
      <button type="button" class="chip" onclick={() => pick(tag)}>#{tag}</button>
    {/each}
  </div>
{/if}

<style>
  .suggestions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
</style>
