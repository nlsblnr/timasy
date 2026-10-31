<script>
  // Fortschrittsbalken (R-2). "prominent" für Pflicht, dezent für gesamt (V-1).
  let { label, done, total, ratio, prominent = false } = $props()
</script>

<div class="progress" class:prominent>
  <div class="row">
    <span class="label">{label}</span>
    <span class="count">{done} / {total}</span>
  </div>
  <div class="track" role="progressbar" aria-label={label}
       aria-valuemin="0" aria-valuemax={total} aria-valuenow={done}>
    <div class="fill" style="width: {Math.round(ratio * 100)}%"></div>
  </div>
</div>

<style>
  .progress { display: grid; gap: 4px; }
  .row { display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--muted); }
  .track { height: 4px; border-radius: 99px; background: var(--track); overflow: hidden; }
  .fill { height: 100%; background: var(--muted); border-radius: 99px; transition: width 0.2s; }
  .prominent .row { font-size: 0.95rem; color: var(--text); }
  .prominent .track { height: 10px; }
  .prominent .fill { background: var(--accent); }
</style>
