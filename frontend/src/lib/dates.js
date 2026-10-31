// Datumshilfen. Daten werden als Text 'JJJJ-MM-TT' weitergegeben, wie im Backend.

export function parseISO(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toISO(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function addDays(iso, n) {
  const d = parseISO(iso)
  d.setDate(d.getDate() + n)
  return toISO(d)
}

const longFormat = new Intl.DateTimeFormat('de-CH', { weekday: 'long', day: 'numeric', month: 'long' })
const shortFormat = new Intl.DateTimeFormat('de-CH', { weekday: 'short', day: 'numeric', month: 'short' })

export const formatLong = (iso) => longFormat.format(parseISO(iso))
export const formatShort = (iso) => shortFormat.format(parseISO(iso))

export function relativeLabel(iso, today) {
  if (iso === today) return 'Heute'
  if (iso === addDays(today, 1)) return 'Morgen'
  if (iso === addDays(today, -1)) return 'Gestern'
  return null
}

// "überfällig seit n Tagen" (R-10)
export function overdueText(days) {
  if (days == null) return ''
  if (days === 1) return 'überfällig seit 1 Tag'
  return `überfällig seit ${days} Tagen`
}
