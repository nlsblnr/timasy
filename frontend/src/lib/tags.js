// Hilfen für Tags (R-22) und den Tag-Filter.

export function normalizeTag(name) {
  return name.trim().replace(/^#+/, '').trim().toLowerCase()
}

// Tags aus einer Texteingabe wie "arbeit, haus" lesen
export function parseTagList(text) {
  const tags = text.split(/[,\s]+/).map(normalizeTag).filter(Boolean)
  return [...new Set(tags)]
}

export function suggest(prefix, existing) {
  const p = normalizeTag(prefix)
  if (!p) return []
  return existing.filter((t) => t.startsWith(p) && t !== p).slice(0, 5)
}
