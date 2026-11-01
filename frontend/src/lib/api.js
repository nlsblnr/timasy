// Alle Aufrufe an das Python-Backend an einer Stelle.

async function request(method, url, body, options = {}) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    ...options,
  })
  if (!res.ok) {
    let message = `Fehler ${res.status}`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') message = data.detail
    } catch {}
    throw new Error(message)
  }
  return res.json()
}

export const api = {
  day: (date) => request('GET', '/api/day' + (date ? `?date=${date}` : '')),
  backlog: () => request('GET', '/api/backlog'),
  tags: () => request('GET', '/api/tags'),
  quick: (data) => request('POST', '/api/quick', data),
  createTask: (data) => request('POST', '/api/tasks', data),
  updateTask: (id, data) => request('PUT', `/api/tasks/${id}`, data),
  // keepalive: der Aufruf wird auch dann noch gesendet, wenn das Fenster schliesst
  deleteTask: (id) => request('DELETE', `/api/tasks/${id}`, null, { keepalive: true }),
  createEntry: (data) => request('POST', '/api/entries', data),
  changeEntry: (id, data) => request('PATCH', `/api/entries/${id}`, data),
  removeEntry: (id) => request('DELETE', `/api/entries/${id}`),
  week: (date) => request('GET', '/api/week' + (date ? `?date=${date}` : '')),
  month: (date) => request('GET', '/api/month' + (date ? `?date=${date}` : '')),
  // Zeiten als Tag + Minuten seit Mitternacht, z.B. { day, start_minute: 555 }
  schedule: (entryId, data) => request('POST', `/api/entries/${entryId}/schedule`, data),
  changeBlock: (id, data) => request('PATCH', `/api/blocks/${id}`, data),
  removeBlock: (id) => request('DELETE', `/api/blocks/${id}`),
}
