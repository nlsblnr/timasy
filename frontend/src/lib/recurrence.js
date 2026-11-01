// Hilfen für Wiederholungen (R-14, R-15, V-8).
import { formatShort, parseISO } from './dates.js'
import { formatTime } from './timegrid.js'

export const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']   // 0 = Montag
const ORDINALS = ['ersten', 'zweiten', 'dritten', 'vierten', 'fünften']
const WEEKDAY_NAMES = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

// Standardwerte für eine neue Wiederholung
export function defaultRecurrence() {
  return { freq: 'weekly', interval: 1, weekdays: [], monthly_by: 'day',
           end_type: 'never', until_date: '', count: 10 }
}

// Wochentag eines Datums, 0 = Montag
export const weekdayOf = (iso) => (parseISO(iso).getDay() + 6) % 7

// "am 15." oder "am ersten Montag" für monatliche Serien (R-29)
export function monthlyText(startsOn, monthlyBy) {
  const d = parseISO(startsOn)
  if (monthlyBy === 'weekday') {
    return `am ${ORDINALS[Math.floor((d.getDate() - 1) / 7)]} ${WEEKDAY_NAMES[weekdayOf(startsOn)]}`
  }
  return `am ${d.getDate()}.`
}

// Beschreibung in Worten, z.B. "alle 2 Wochen am Mo, Mi · bis 29.12.2026 · um 07:00"
export function describe(s) {
  const n = s.interval
  const units = {
    daily: ['täglich', `alle ${n} Tage`],
    weekly: ['wöchentlich', `alle ${n} Wochen`],
    monthly: ['monatlich', `alle ${n} Monate`],
    yearly: ['jährlich', `alle ${n} Jahre`],
  }[s.freq]
  let text = n === 1 ? units[0] : units[1]
  if (s.freq === 'weekly' && s.weekdays?.length) {
    text += ' am ' + s.weekdays.map((d) => WEEKDAYS[d]).join(', ')
  }
  if (s.freq === 'monthly') text += ' ' + monthlyText(s.starts_on, s.monthly_by)
  if (s.freq === 'yearly') {
    text += ' am ' + new Intl.DateTimeFormat('de-CH', { day: 'numeric', month: 'long' })
      .format(parseISO(s.starts_on))
  }
  if (s.end_type === 'until' && s.until_date) {
    text += ' · bis ' + new Intl.DateTimeFormat('de-CH').format(parseISO(s.until_date))
  }
  if (s.end_type === 'count') text += ` · ${s.count} Mal`
  if (s.start_minute != null) text += ` · um ${formatTime(s.start_minute)}`
  return text
}

export { formatShort }

// Uhrzeit-Feld ("07:30") <-> Minuten seit Mitternacht
export function timeToMinutes(value) {
  if (!value) return null
  const [h, m] = value.split(':').map(Number)
  return h * 60 + m
}
export const minutesToTime = (m) => (m == null ? '' : formatTime(m))

// Nur die Felder, die das Backend für eine Wiederholung braucht
export function recurrencePayload(rec) {
  return {
    freq: rec.freq,
    interval: Number(rec.interval) || 1,
    weekdays: rec.freq === 'weekly' ? rec.weekdays : [],
    monthly_by: rec.monthly_by,
    end_type: rec.end_type,
    until_date: rec.end_type === 'until' ? rec.until_date || null : null,
    count: rec.end_type === 'count' ? Number(rec.count) || null : null,
  }
}
