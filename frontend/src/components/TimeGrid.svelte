<script>
  // Zeitraster mit einer Spalte pro Tag (V-1 Zeitleiste: 1 Tag, V-2 Woche: 7 Tage).
  //  - Blöcke mit der Maus verschieben (auch auf einen anderen Tag, R-23)
  //  - Unterkante ziehen: Länge ändern
  //  - Einträge aus Listen hineinziehen: Block anlegen
  //  - Einträge auf den Tageskopf ziehen: nur dem Tag zuweisen (V-2)
  //  - Fremdtermine (grau, nur lesen, S-4); ganztägige als Streifen oben
  import { onMount } from 'svelte'
  import { api } from '../lib/api.js'
  import { reload, showError } from '../lib/state.svelte.js'
  import { formatShort, parseISO } from '../lib/dates.js'
  import {
    DAY_MINUTES, ENTRY_MIME, HOUR_PX, SCROLL_TO_HOUR, SNAP,
    clamp, formatTime, layoutOverlaps, snap,
  } from '../lib/timegrid.js'

  let { days, today, entries, events = [], showHeader = true, height = '70vh' } = $props()

  let scroller
  let columnsEl
  let drag = $state(null)   // laufendes Verschieben/Ziehen eines Blocks
  let dropHint = $state(null) // { day, minute } beim Hineinziehen aus einer Liste

  onMount(() => (scroller.scrollTop = SCROLL_TO_HOUR * HOUR_PX))

  // Alle Blöcke mit Position; der gerade gezogene Block an seiner neuen Stelle
  let placed = $derived(
    entries
      .filter((e) => e.block)
      .map((e) =>
        drag?.entry.id === e.id
          ? { entry: e, id: e.id, day: drag.day, start: drag.start, end: drag.end }
          : { entry: e, id: e.id, day: e.block.day, start: e.block.start_minute, end: e.block.end_minute })
  )
  // Fremdtermine mit Uhrzeit liegen neben den Blöcken (gemeinsame Anordnung)
  let timedEvents = $derived(
    events.filter((e) => !e.all_day).map((e) => ({
      event: e, id: `ev:${e.calendar_id}:${e.id}:${e.day}`,
      day: e.day, start: e.start_minute, end: Math.max(e.end_minute, e.start_minute + SNAP),
    }))
  )
  let allDay = $derived(events.filter((e) => e.all_day))
  let columns = $derived(
    days.map((day) => {
      const items = placed.filter((p) => p.day === day)
      const evs = timedEvents.filter((e) => e.day === day)
      return { day, items, evs, layout: layoutOverlaps([...evs, ...items]) }
    })
  )

  // Wo befindet sich der Mauszeiger im Raster? -> Spalte und Minute
  function pointerPosition(event) {
    const rect = columnsEl.getBoundingClientRect()
    const col = clamp(Math.floor(((event.clientX - rect.left) / rect.width) * days.length), 0, days.length - 1)
    const minute = ((event.clientY - rect.top) / HOUR_PX) * 60
    return { day: days[col], minute }
  }

  // --- Block verschieben / Länge ändern (Zeiger-Ereignisse) ---------------------

  function startDrag(event, entry, mode) {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    const b = entry.block
    drag = {
      entry, mode, moved: false,
      day: b.day, start: b.start_minute, end: b.end_minute,
      grab: pointerPosition(event).minute - b.start_minute,  // wo der Block angefasst wurde
      x: event.clientX, y: event.clientY,
    }
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp, { once: true })
  }

  function onPointerMove(event) {
    if (!drag) return
    if (Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y) > 3) drag.moved = true
    const pos = pointerPosition(event)
    if (drag.mode === 'move') {
      const duration = drag.entry.block.end_minute - drag.entry.block.start_minute
      drag.start = clamp(snap(pos.minute - drag.grab), 0, DAY_MINUTES - duration)
      drag.end = drag.start + duration
      drag.day = pos.day
    } else {
      drag.end = clamp(snap(pos.minute), drag.start + SNAP, DAY_MINUTES)
    }
  }

  async function onPointerUp() {
    window.removeEventListener('pointermove', onPointerMove)
    const d = drag
    const b = d.entry.block
    const changed = d.day !== b.day || d.start !== b.start_minute || d.end !== b.end_minute
    if (d.moved && changed) {
      try {
        await api.changeBlock(b.id, { day: d.day, start_minute: d.start, end_minute: d.end })
        reload()
      } catch (e) {
        showError(e)
      }
    }
    drag = null
  }

  // --- Einträge aus Listen hineinziehen (HTML Drag & Drop) -------------------

  function onDragOver(event) {
    if (!event.dataTransfer.types.includes(ENTRY_MIME)) return
    event.preventDefault()
    const pos = pointerPosition(event)
    dropHint = { day: pos.day, minute: clamp(snap(pos.minute - SNAP), 0, DAY_MINUTES - SNAP) }
  }

  async function onDrop(event) {
    const id = event.dataTransfer.getData(ENTRY_MIME)
    const hint = dropHint
    dropHint = null
    if (!id || !hint) return
    event.preventDefault()
    try {
      await api.schedule(id, { day: hint.day, start_minute: hint.minute })
      reload()
    } catch (e) {
      showError(e)
    }
  }

  async function onDropOnDay(event, day) {
    const id = event.dataTransfer.getData(ENTRY_MIME)
    if (!id) return
    event.preventDefault()
    try {
      await api.changeEntry(id, { day })
      reload()
    } catch (e) {
      showError(e)
    }
  }

  async function call(fn) {
    try {
      await fn()
      reload()
    } catch (e) {
      showError(e)
    }
  }

  const weekdayShort = new Intl.DateTimeFormat('de-CH', { weekday: 'short' })
</script>

<div class="grid" style="--hour: {HOUR_PX}px; --cols: {days.length}">
  {#if showHeader}
    <div class="header">
      <div class="gutter"></div>
      {#each days as day}
        <div class="dayhead" class:today={day === today} role="region" aria-label="Tag {day}"
             ondragover={(e) => e.dataTransfer.types.includes(ENTRY_MIME) && e.preventDefault()}
             ondrop={(e) => onDropOnDay(e, day)}>
          <span class="wd">{weekdayShort.format(parseISO(day))}</span>
          <span class="num">{parseISO(day).getDate()}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if allDay.length}
    <div class="allday">
      <div class="gutter"></div>
      {#each days as day}
        <div class="allday-col">
          {#each allDay.filter((e) => e.day === day) as e}
            <div class="event-strip" title="{e.title} (ganztägig, aus Google)">{e.title}</div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}

  <div class="scroller" bind:this={scroller} style="height: {height}">
    <div class="body">
      <div class="gutter">
        {#each Array(24) as _, h}
          <div class="hour-label">{h ? formatTime(h * 60) : ''}</div>
        {/each}
      </div>

      <div class="columns" bind:this={columnsEl} role="region" aria-label="Zeitraster"
           ondragover={onDragOver} ondragleave={() => (dropHint = null)} ondrop={onDrop}>
        {#each columns as col (col.day)}
          <div class="column" class:past={col.day < today}>
            {#if dropHint?.day === col.day}
              <div class="drop-hint" style="top: {(dropHint.minute / 60) * HOUR_PX}px">
                {formatTime(dropHint.minute)}
              </div>
            {/if}
            {#each col.evs as ev (ev.id)}
              {@const pos = col.layout.get(ev.id)}
              <div class="event"
                   style="top: {(ev.start / 60) * HOUR_PX}px;
                          height: {((ev.end - ev.start) / 60) * HOUR_PX - 2}px;
                          left: {(pos.lane / pos.lanes) * 100}%;
                          width: calc({100 / pos.lanes}% - 4px)"
                   title="{ev.event.title}, {formatTime(ev.start)}–{formatTime(ev.end)} (aus Google, nur lesen)">
                <span class="event-title">{ev.event.title}</span>
                <span class="block-time">{formatTime(ev.start)}–{formatTime(ev.end)}</span>
              </div>
            {/each}
            {#each col.items as item (item.id)}
              {@const pos = col.layout.get(item.id)}
              {@const done = item.entry.status === 'done'}
              <div
                class="block" class:done class:dragging={drag?.entry.id === item.id}
                class:conflict={item.entry.conflict}
                class:short={item.end - item.start <= 30}
                style="top: {(item.start / 60) * HOUR_PX}px;
                       height: {((item.end - item.start) / 60) * HOUR_PX - 2}px;
                       left: {(pos.lane / pos.lanes) * 100}%;
                       width: calc({100 / pos.lanes}% - 4px)"
                role="button" tabindex="-1" aria-label="{item.entry.title}, {formatTime(item.start)} bis {formatTime(item.end)}"
                onpointerdown={(e) => startDrag(e, item.entry, 'move')}
              >
                <div class="block-top">
                  <input type="checkbox" checked={done} aria-label="{item.entry.title} abhaken"
                         onpointerdown={(e) => e.stopPropagation()}
                         onchange={() => call(() => api.changeEntry(item.entry.id, { done: !done }))} />
                  <span class="block-title">{item.entry.title}</span>
                  {#if item.entry.conflict}<span class="conflict-mark" title="Überschneidet sich mit einem Termin (R-20)">⚠︎</span>{/if}
                  <button class="remove" title="Block entfernen (Eintrag bleibt)"
                          aria-label="Block entfernen"
                          onpointerdown={(e) => e.stopPropagation()}
                          onclick={() => call(() => api.removeBlock(item.entry.block.id))}>×</button>
                </div>
                <span class="block-time">{formatTime(item.start)}–{formatTime(item.end)}</span>
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div class="resize" onpointerdown={(e) => startDrag(e, item.entry, 'resize')}></div>
              </div>
            {/each}
          </div>
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .grid { display: grid; user-select: none; }
  .header, .body { display: grid; grid-template-columns: 48px 1fr; }
  .header { grid-template-columns: 48px repeat(var(--cols), 1fr); border-bottom: 1px solid var(--line); }
  .dayhead { display: grid; justify-items: center; padding: 6px 0; border-radius: 12px; }
  .dayhead .wd { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }
  .dayhead .num { font-size: 1.2rem; font-weight: 600; }
  .dayhead.today .num { color: var(--accent); }
  .scroller { overflow-y: auto; position: relative; }
  .hour-label { height: var(--hour); font-size: 0.7rem; color: var(--muted);
                transform: translateY(-0.6em); text-align: right; padding-right: 8px; }
  .columns {
    display: grid; grid-template-columns: repeat(var(--cols), 1fr); position: relative;
    height: calc(24 * var(--hour));
    background-image: linear-gradient(var(--line) 1px, transparent 1px);
    background-size: 100% var(--hour);
  }
  .column { position: relative; border-left: 1px solid var(--line); }
  .column.past { background: color-mix(in srgb, var(--surface) 50%, transparent); }
  .block {
    position: absolute; margin: 1px 2px; padding: 3px 6px; overflow: hidden;
    background: color-mix(in srgb, var(--accent) 18%, var(--surface-raised));
    border-left: 3px solid var(--accent); border-radius: 8px;
    font-size: 0.8rem; cursor: grab; touch-action: none;
  }
  .block.dragging { cursor: grabbing; box-shadow: 0 4px 12px var(--shadow); z-index: 3; opacity: 0.9; }
  .block.done { opacity: 0.55; }
  .block.done .block-title { text-decoration: line-through; }
  .block-top { display: flex; align-items: center; gap: 4px; }
  .block-top input { width: 14px; height: 14px; flex: none; }
  .block-title { flex: 1; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .block.short .block-time { display: none; }
  .block-time { color: var(--muted); font-size: 0.72rem; }
  .remove { padding: 0 4px; color: var(--muted); visibility: hidden; }
  .block:hover .remove { visibility: visible; }
  /* Fremdtermine: grau, nur lesen (V-1, V-2) */
  .event {
    position: absolute; margin: 1px 2px; padding: 3px 6px; overflow: hidden;
    background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
    font-size: 0.8rem; color: var(--muted); pointer-events: auto; cursor: default;
  }
  .event-title { display: block; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .allday { display: grid; grid-template-columns: 48px repeat(var(--cols), 1fr);
            border-bottom: 1px solid var(--line); padding: 2px 0; }
  .allday-col { display: grid; gap: 2px; padding: 0 2px; align-content: start; }
  .event-strip { font-size: 0.75rem; padding: 1px 6px; border-radius: 6px; color: var(--muted);
                 background: var(--surface); border: 1px solid var(--line);
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* R-20: Überschneidung sichtbar, aber ruhig */
  .block.conflict { border-left-style: dashed; }
  .conflict-mark { color: var(--calm); font-size: 0.75rem; }
  .resize { position: absolute; left: 0; right: 0; bottom: 0; height: 6px; cursor: ns-resize; }
  .drop-hint {
    position: absolute; left: 2px; right: 2px; height: calc(var(--hour) / 2);
    border: 2px dashed var(--accent); border-radius: 8px; font-size: 0.75rem;
    color: var(--accent); padding: 2px 6px; pointer-events: none;
  }
</style>
