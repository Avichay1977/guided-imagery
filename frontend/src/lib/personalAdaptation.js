import { INTERVENTION_STYLES } from './interventionRecipes.js'

const STORAGE_KEY = 'guided_imagery_personal_adaptation_v1'
const MAX_HISTORY = 120
const MIN_SAMPLES = 3
const MIN_OPTION_SAMPLES = 2
const MIN_STYLE_OPTION_SAMPLES = 2
const MIN_CONTEXT_STYLES = 2

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

export function getIntensityBand(value) {
  const intensity = Number(value)
  if (!Number.isFinite(intensity)) return null
  if (intensity <= 3) return 'low'
  if (intensity <= 6) return 'medium'
  return 'high'
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

function groupScore(items, key, minSamples = MIN_OPTION_SAMPLES) {
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
    .filter((group) => group.samples >= minSamples)
    .sort((a, b) =>
      b.averageDelta - a.averageDelta ||
      b.averageHelpfulness - a.averageHelpfulness ||
      b.samples - a.samples
    )
}

export function getInterventionPlan(focus = 'general', intensityBefore = null) {
  const rows = completedForFocus(focus).filter((item) =>
    INTERVENTION_STYLES.includes(item.interventionStyle)
  )
  const contextBand = getIntensityBand(intensityBefore)
  const contextRows = contextBand
    ? rows.filter((item) => getIntensityBand(item.intensityBefore) === contextBand)
    : []

  const counts = Object.fromEntries(INTERVENTION_STYLES.map((style) => [style, 0]))
  const contextCounts = Object.fromEntries(INTERVENTION_STYLES.map((style) => [style, 0]))
  for (const row of rows) counts[row.interventionStyle] += 1
  for (const row of contextRows) contextCounts[row.interventionStyle] += 1

  // Exploration is still globally bounded to exactly two measured attempts per
  // recipe. Context only breaks ties, so v3 never adds a second exploration
  // programme for low, medium and high intensity.
  const exploreStyle = INTERVENTION_STYLES
    .map((style, order) => ({
      style,
      order,
      samples: counts[style],
      contextSamples: contextCounts[style],
    }))
    .filter((item) => item.samples < MIN_STYLE_OPTION_SAMPLES)
    .sort((a, b) =>
      a.samples - b.samples ||
      a.contextSamples - b.contextSamples ||
      a.order - b.order
    )[0]

  if (exploreStyle) {
    return {
      style: exploreStyle.style,
      phase: 'explore',
      scope: 'global',
      samples: rows.length,
      styleSamples: exploreStyle.samples,
      contextBand,
      contextSamples: contextRows.length,
      counts,
      contextCounts,
    }
  }

  const globalBest = groupScore(rows, 'interventionStyle', MIN_STYLE_OPTION_SAMPLES)[0]
  const contextualGroups = contextBand
    ? groupScore(contextRows, 'interventionStyle', MIN_STYLE_OPTION_SAMPLES)
    : []

  // Context may override the global recipe only when at least two different
  // recipes each have two measured outcomes in this same intensity band. This
  // prevents one lucky result from becoming a personalised rule.
  const useContext = contextualGroups.length >= MIN_CONTEXT_STYLES
  const best = useContext ? contextualGroups[0] : globalBest
  const evidenceRows = useContext ? contextRows : rows

  return {
    style: best?.value || 'balanced',
    phase: 'learned',
    scope: useContext ? 'context' : 'global',
    samples: evidenceRows.length,
    totalSamples: rows.length,
    styleSamples: best?.samples || 0,
    averageDelta: best?.averageDelta || 0,
    averageHelpfulness: best?.averageHelpfulness || 0,
    confidence: evidenceRows.length >= 12 ? 'high' : evidenceRows.length >= 8 ? 'medium' : 'early',
    contextBand,
    contextSamples: contextRows.length,
    eligibleContextStyles: contextualGroups.length,
    counts,
    contextCounts,
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
