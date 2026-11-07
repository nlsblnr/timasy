<script>
  // Übersicht aller Tastenkürzel (UX-4, v0.9). Öffnet mit ? oder dem Knopf ⌨.
  import { onMount } from 'svelte'
  import { SHORTCUTS } from '../lib/keys.js'

  let { onclose } = $props()
  let panel

  onMount(() => panel.focus())
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions (Esc schliesst global) -->
<div class="backdrop" onclick={onclose}></div>
<div class="panel" bind:this={panel} tabindex="-1" role="dialog" aria-label="Tastenkürzel">
  <header>
    <h2>Tastenkürzel</h2>
    <button class="icon" onclick={onclose} aria-label="Schliessen" title="Schliessen (Esc)">×</button>
  </header>
  {#each SHORTCUTS as section}
    <h3>{section.group}</h3>
    <dl>
      {#each section.items as [keys, text]}
        <dt>{#each keys as k}<kbd>{k}</kbd>{/each}</dt>
        <dd>{text}</dd>
      {/each}
    </dl>
  {/each}
</div>

<style>
  .backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.15); z-index: 20; }
  .panel {
    position: fixed; top: 12px; right: 12px; bottom: 12px; width: min(380px, calc(100vw - 24px));
    z-index: 21; overflow-y: auto; padding: 20px 24px;
    background: var(--surface-raised); border-radius: 24px; box-shadow: 0 8px 32px var(--shadow);
    animation: slide 0.15s ease-out;
  }
  .panel:focus { outline: none; }
  @keyframes slide { from { transform: translateX(16px); opacity: 0; } }
  header { display: flex; align-items: center; justify-content: space-between; }
  h2 { margin: 0; font-size: 1.3rem; font-weight: 600; }
  h3 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted);
       margin: 20px 0 8px; font-weight: 600; }
  dl { display: grid; grid-template-columns: 96px 1fr; gap: 8px 16px; margin: 0; align-items: center; }
  dt { display: flex; gap: 4px; justify-content: flex-end; }
  dd { margin: 0; font-size: 0.92rem; }
  kbd {
    min-width: 26px; text-align: center; padding: 2px 7px; font-size: 0.82rem;
    border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 6px;
    background: var(--surface);
  }
</style>
