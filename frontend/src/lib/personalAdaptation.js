import { INTERVENTION_STYLES } from './interventionRecipes.js'

const STORAGE_KEY = 'guided_imagery_personal_adaptation_v1'
const MAX_HISTORY = 120
const MIN_SAMPLES = 3
const MIN_OPTION_SAMPLES = 2
const MIN_STYLE_OPTION_SAMPLES = 2
const MIN_CONTEXT_STYLES = 2
const MIN_FINGERPRINT_STYLES = 2
const MAX_FINGERPRINT_DISTANCE = 2
const FINGERPRINT_KEYS = ['bodyActivation', 'thoughtLoop', 'movementNeed']

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

export function normalizeStateFingerprint(fingerprint) {
  if (!fingerprint || typeof fingerprint !== 'object') return null
  const normalized = {}
  for (const key of FINGERPRINT_KEYS) {
    const value = Number(fingerprint[key])
    if (!Number.isInteger(value) || value < 0 || value > 2) return null
    normalized[key] = value
  }
  return normalized
}

export function stateFingerprintDistance(left, right) {
  const a = normalizeStateFingerprint(left)
  const b = normalizeStateFingerprint(right)
  if (!a || !b) return null
  return FINGERPRINT_KEYS.reduce((sum, key) => sum + Math.abs(a[key] - b[key]), 0)
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
    stateFingerprint: normalizeStateFingerprint(settings.stateFingerprint),
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

function weightedFingerprintScore(items, targetFingerprint) {
  const groups = new Map()
  for (const item of items) {
    const distance = stateFingerprintDistance(item.stateFingerprint, targetFingerprint)
    if (distance === null || distance > MAX_FINGERPRINT_DISTANCE) continue
    const style = item.interventionStyle
    if (!groups.has(style)) groups.set(style, [])
    groups.get(style).push({ item, distance, weight: 1 / (1 + distance) })
  }

  return [...groups.entries()]
    .map(([value, rows]) => {
      const weightTotal = rows.reduce((sum, row) => sum + row.weight, 0)
      return {
        value,
        samples: rows.length,
        weightedSamples: weightTotal,
        averageDistance: rows.reduce((sum, row) => sum + row.distance, 0) / rows.length,
        averageDelta: rows.reduce(
          (sum, row) => sum + (row.item.intensityBefore - row.item.intensityAfter) * row.weight,
          0,
        ) / weightTotal,
        averageHelpfulness: rows.reduce(
          (sum, row) => sum + row.item.helpfulness * row.weight,
          0,
        ) / weightTotal,
      }
    })
    .filter((group) => group.samples >= MIN_STYLE_OPTION_SAMPLES)
    .sort((a, b) =>
      b.averageDelta - a.averageDelta ||
      b.averageHelpfulness - a.averageHelpfulness ||
      a.averageDistance - b.averageDistance ||
      b.samples - a.samples
    )
}

export function getInterventionPlan(
  focus = 'general',
  intensityBefore = null,
  stateFingerprint = null,
) {
  const rows = completedForFocus(focus).filter((item) =>
    INTERVENTION_STYLES.includes(item.interventionStyle)
  )
  const contextBand = getIntensityBand(intensityBefore)
  const contextRows = contextBand
    ? rows.filter((item) => getIntensityBand(item.intensityBefore) === contextBand)
    : []
  const normalizedFingerprint = normalizeStateFingerprint(stateFingerprint)

  const counts = Object.fromEntries(INTERVENTION_STYLES.map((style) => [style, 0]))
  const contextCounts = Object.fromEntries(INTERVENTION_STYLES.map((style) => [style, 0]))
  for (const row of rows) counts[row.interventionStyle] += 1
  for (const row of contextRows) contextCounts[row.interventionStyle] += 1

  // Exploration stays globally bounded to exactly two measured attempts per
  // recipe. State Fingerprint never creates extra mandatory trials.
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
      fingerprintSamples: 0,
      counts,
      contextCounts,
    }
  }

  const globalBest = groupScore(rows, 'interventionStyle', MIN_STYLE_OPTION_SAMPLES)[0]
  const contextualGroups = contextBand
    ? groupScore(contextRows, 'interventionStyle', MIN_STYLE_OPTION_SAMPLES)
    : []
  const fingerprintGroups = normalizedFingerprint && contextBand
    ? weightedFingerprintScore(contextRows, normalizedFingerprint)
    : []

  // Fingerprint may override intensity context only when at least two recipes
  // each have two nearby measured outcomes in the same intensity band. Nearby
  // means Manhattan distance <= 2 across the three 0/1/2 state dimensions.
  const useFingerprint = fingerprintGroups.length >= MIN_FINGERPRINT_STYLES
  const useContext = contextualGroups.length >= MIN_CONTEXT_STYLES
  const best = useFingerprint
    ? fingerprintGroups[0]
    : useContext
      ? contextualGroups[0]
      : globalBest

  const fingerprintRows = normalizedFingerprint && contextBand
    ? contextRows.filter((item) => {
        const distance = stateFingerprintDistance(item.stateFingerprint, normalizedFingerprint)
        return distance !== null && distance <= MAX_FINGERPRINT_DISTANCE
      })
    : []
  const evidenceRows = useFingerprint ? fingerprintRows : useContext ? contextRows : rows

  return {
    style: best?.value || 'balanced',
    phase: 'learned',
    scope: useFingerprint ? 'fingerprint' : useContext ? 'context' : 'global',
    samples: evidenceRows.length,
    totalSamples: rows.length,
    styleSamples: best?.samples || 0,
    averageDelta: best?.averageDelta || 0,
    averageHelpfulness: best?.averageHelpfulness || 0,
    confidence: evidenceRows.length >= 12 ? 'high' : evidenceRows.length >= 8 ? 'medium' : 'early',
    contextBand,
    contextSamples: contextRows.length,
    eligibleContextStyles: contextualGroups.length,
    fingerprintSamples: fingerprintRows.length,
    eligibleFingerprintStyles: fingerprintGroups.length,
    fingerprintAverageDistance: useFingerprint ? fingerprintGroups[0]?.averageDistance ?? null : null,
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
