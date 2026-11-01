// Hilfen für Zeitraster (Wochenansicht und Tages-Zeitleiste).
// Zeiten sind Minuten seit Mitternacht, z.B. 9:15 Uhr = 555.

export const HOUR_PX = 48          // Höhe einer Stunde in Pixeln
export const SNAP = 15             // Raster in Minuten (V-2)
export const DAY_MINUTES = 24 * 60
export const SCROLL_TO_HOUR = 7    // beim Öffnen sichtbar ab 7 Uhr

export const snap = (minute) => Math.round(minute / SNAP) * SNAP
export const clamp = (v, min, max) => Math.min(Math.max(v, min), max)

export function formatTime(minute) {
  const h = String(Math.floor(minute / 60)).padStart(2, '0')
  const m = String(minute % 60).padStart(2, '0')
  return `${h}:${m}`
}

// Überschneidende Blöcke nebeneinander anordnen (R-23).
// Jeder Block bekommt eine Spur (lane) und die Anzahl Spuren seiner Gruppe.
export function layoutOverlaps(items) {
  const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end)
  const result = new Map()
  let group = []
  let groupEnd = -1
  let lanes = []            // pro Spur: Ende des letzten Blocks

  function closeGroup() {
    for (const item of group) result.get(item.id).lanes = lanes.length
    group = []
    lanes = []
  }

  for (const item of sorted) {
    if (group.length && item.start >= groupEnd) {
      closeGroup()
      groupEnd = -1
    }
    let lane = lanes.findIndex((end) => end <= item.start)
    if (lane === -1) {
      lane = lanes.length
      lanes.push(item.end)
    } else {
      lanes[lane] = item.end
    }
    result.set(item.id, { lane, lanes: 1 })
    group.push(item)
    groupEnd = Math.max(groupEnd, item.end)
  }
  closeGroup()
  return result
}

// Drag & Drop von Einträgen aus Listen auf Tage oder Uhrzeiten
export const ENTRY_MIME = 'application/x-timasy-entry'
