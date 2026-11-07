// Gemeinsame Regeln für Tastenkürzel (UX-4).

// Tastenkürzel nur unterdrücken, wenn gerade Text getippt wird
// (nicht bei Checkboxen oder Knöpfen, z.B. direkt nach dem Abhaken).
const NON_TEXT_INPUTS = ['checkbox', 'radio', 'button', 'submit', 'range', 'color']

export function isTyping(target) {
  if (target.tagName === 'INPUT') return !NON_TEXT_INPUTS.includes(target.type)
  return ['TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
}

// Soll ein Tastendruck als Kürzel gelten? (keine Ctrl/Cmd/Alt-Kombination, nicht beim Tippen)
export function isShortcut(event) {
  return !(event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target))
}

// Alle Tastenkürzel für die Übersicht (Taste ?)
export const SHORTCUTS = [
  { group: 'Überall', items: [
    [['n'], 'Neue Aufgabe erfassen'],
    [['h'], 'Heute'],
    [['w'], 'Woche'],
    [['m'], 'Monat'],
    [['b'], 'Backlog'],
    [['s'], 'Serien'],
    [['e'], 'Einstellungen'],
    [['?'], 'Diese Übersicht'],
    [['Esc'], 'Schliessen bzw. abbrechen'],
  ] },
  { group: 'Heute', items: [
    [['↑', '↓'], 'Eintrag wählen'],
    [['Leertaste'], 'Abhaken bzw. wieder öffnen'],
    [['⇧', '→'], 'Eintrag einen Tag später'],
    [['⇧', '←'], 'Eintrag einen Tag früher'],
    [['t'], 'Stufe wechseln (Pflicht/Bonus)'],
    [['Enter'], 'Eintrag bearbeiten'],
    [['←', '→'], 'Vorheriger bzw. nächster Tag'],
  ] },
  { group: 'Woche und Monat', items: [
    [['←', '→'], 'Vorherige bzw. nächste Woche oder Monat'],
  ] },
  { group: 'Schnellerfassung', items: [
    [['Enter'], 'Speichern'],
    [['Tab'], 'Stufe wechseln oder Tag-Vorschlag übernehmen'],
    [['#name'], 'Tag hinzufügen (im Titel)'],
  ] },
]
