<script>
  // Filter nach Tag (R-22): zeigt die vorhandenen Tags als Chips.
  let { tags, selected = $bindable(null) } = $props()
</script>

{#if tags.length}
  <div class="filter" aria-label="Nach Tag filtern">
    {#each tags as tag}
      <button class="chip" class:active={selected === tag}
              onclick={() => (selected = selected === tag ? null : tag)}>#{tag}</button>
    {/each}
  </div>
{/if}

<style>
  .filter { display: flex; flex-wrap: wrap; gap: 6px; }
</style>
