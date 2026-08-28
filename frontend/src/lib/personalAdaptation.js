import { INTERVENTION_STYLES } from './interventionRecipes'

const STORAGE_KEY = 'guided_imagery_personal_adaptation_v1'
const MAX_HISTORY = 120
const MIN_SAMPLES = 3
const MIN_OPTION_SAMPLES = 2
const MIN_STYLE_OPTION_SAMPLES = 2

function readHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeHistory(history) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-MAX_HISTORY)))
  } catch {
    // Personalization must never block a session if storage is unavailable.
  }
}

export function recordCompletedSession(sessionId, settings) {
  if (!sessionId || !settings) return
  const history = readHistory()
  const index = history.findIndex((item) => item.sessionId === sessionId)
  const settingsOnly = {
    sessionId,
    focus: settings.focus || 'general',
    mode: settings.mode || 'imagery',
    pace: settings.pace || 'slow',
    duration: settings.duration || 10,
    neuroprofile: settings.neuroprofile || 'none',
    ageGroup: settings.ageGroup || 'adult',
    interventionStyle: INTERVENTION_STYLES.includes(settings.interventionStyle)
      ? settings.interventionStyle
      : null,
    interventionSource: settings.interventionSource || null,
    intensityBefore: Number.isFinite(settings.intensityBefore)
      ? settings.intensityBefore
      : null,
  }

  // Re-recording the same rendered session must not erase feedback that may
  // already have been saved by the listener.
  if (index >= 0) history[index] = { ...history[index], ...settingsOnly }
  else {
    history.push({
      ...settingsOnly,
      createdAt: Date.now(),
      intensityAfter: null,
      helpfulness: null,
    })
  }
  writeHistory(history)
}

export function saveOutcome(sessionId, { intensityAfter, helpfulness }) {
  const history = readHistory()
  const index = history.findIndex((item) => item.sessionId === sessionId)
  if (index < 0) return false

  history[index] = {
    ...history[index],
    intensityAfter: Number(intensityAfter),
    helpfulness: Number(helpfulness),
    outcomeAt: Date.now(),
  }
  writeHistory(history)
  return true
}

function completedForFocus(focus) {
  return readHistory().filter((item) =>
    item.focus === focus &&
    Number.isFinite(item.intensityBefore) &&
    Number.isFinite(item.intensityAfter) &&
    Number.isFinite(item.helpfulness)
  )
}

function groupScore(items, key) {
  const groups = new Map()
  for (const item of items) {
    const value = item[key]
    if (value === null || value === undefined || value === '') continue
    if (!groups.has(value)) groups.set(value, [])
    groups.get(value).push(item)
  }

  return [...groups.entries()]
    .map(([value, rows]) => ({
      value,
      samples: rows.length,
      averageDelta: rows.reduce(
        (sum, row) => sum + (row.intensityBefore - row.intensityAfter),
        0,
      ) / rows.length,
      averageHelpfulness: rows.reduce((sum, row) => sum + row.helpfulness, 0) / rows.length,
    }))
    .filter((group) => group.samples >= MIN_OPTION_SAMPLES)
    .sort((a, b) =>
      b.averageDelta - a.averageDelta ||
      b.averageHelpfulness - a.averageHelpfulness ||
      b.samples - a.samples
    )
}

export function getInterventionPlan(focus = 'general') {
  const rows = completedForFocus(focus).filter((item) =>
    INTERVENTION_STYLES.includes(item.interventionStyle)
  )
  const counts = Object.fromEntries(INTERVENTION_STYLES.map((style) => [style, 0]))
  for (const row of rows) counts[row.interventionStyle] += 1

  // Exploration is deterministic and bounded: each safe recipe gets exactly
  // two measured attempts before outcome history is allowed to prefer one.
  const exploreStyle = INTERVENTION_STYLES
    .map((style, order) => ({ style, order, samples: counts[style] }))
    .filter((item) => item.samples < MIN_STYLE_OPTION_SAMPLES)
    .sort((a, b) => a.samples - b.samples || a.order - b.order)[0]

  if (exploreStyle) {
    return {
      style: exploreStyle.style,
      phase: 'explore',
      samples: rows.length,
      styleSamples: exploreStyle.samples,
      counts,
    }
  }

  const best = groupScore(rows, 'interventionStyle')[0]
  return {
    style: best?.value || 'balanced',
    phase: 'learned',
    samples: rows.length,
    styleSamples: best?.samples || 0,
    averageDelta: best?.averageDelta || 0,
    averageHelpfulness: best?.averageHelpfulness || 0,
    confidence: rows.length >= 12 ? 'high' : rows.length >= 8 ? 'medium' : 'early',
    counts,
  }
}

export function getRecommendation(focus = 'general') {
  const rows = completedForFocus(focus)
  if (rows.length < MIN_SAMPLES) return null

  const pace = groupScore(rows, 'pace')[0] || null
  const mode = groupScore(rows, 'mode')[0] || null
  const averageDelta = rows.reduce(
    (sum, row) => sum + (row.intensityBefore - row.intensityAfter),
    0,
  ) / rows.length

  return {
    samples: rows.length,
    pace: pace?.value || null,
    paceSamples: pace?.samples || 0,
    mode: mode?.value || null,
    modeSamples: mode?.samples || 0,
    averageDelta,
    confidence: rows.length >= 8 ? 'high' : rows.length >= 5 ? 'medium' : 'early',
  }
}

export function clearPersonalAdaptation() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // No-op: clearing history is optional and must not break the app.
  }
}
