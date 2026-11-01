<script>
  // Ruhige Rückfrage direkt in der Liste (statt Pop-up, UX-3).
  // Esc oder "Abbrechen" schliesst, "Löschen" führt die Aktion aus.
  import { onMount } from 'svelte'

  let { message, confirmLabel = 'Löschen', onconfirm, oncancel } = $props()
  let confirmButton

  onMount(() => confirmButton.focus())
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Esc bricht ab) -->
<div class="confirm" role="alertdialog" aria-label={message}
     onkeydown={(e) => e.key === 'Escape' && oncancel()}>
  <span>{message}</span>
  <button type="button" class="text" onclick={oncancel}>Abbrechen</button>
  <button type="button" class="filled" bind:this={confirmButton} onclick={onconfirm}>{confirmLabel}</button>
</div>

<style>
  .confirm {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px;
    padding: 8px 8px 8px 14px; border-radius: 12px; background: var(--surface);
  }
  span { flex: 1 1 200px; font-size: 0.9rem; }
</style>
