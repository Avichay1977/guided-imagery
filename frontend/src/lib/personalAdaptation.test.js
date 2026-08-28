import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clearPersonalAdaptation,
  dismissFollowUp,
  getDueFollowUp,
  getEffectiveOutcomeDelta,
  getIntensityBand,
  getInterventionPlan,
  normalizeStateFingerprint,
  recordCompletedSession,
  saveDelayedOutcome,
  saveOutcome,
  stateFingerprintDistance,
} from './personalAdaptation.js'
import { applyInterventionStyle } from './interventionRecipes.js'

class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null
  }

  setItem(key, value) {
    this.values.set(key, String(value))
  }

  removeItem(key) {
    this.values.delete(key)
  }
}

globalThis.localStorage = new MemoryStorage()

function complete(
  id,
  style,
  after,
  helpfulness,
  intensityBefore = 8,
  stateFingerprint = null,
) {
  recordCompletedSession(id, {
    focus: 'anxiety',
    mode: 'imagery',
    pace: 'slow',
    duration: 10,
    neuroprofile: 'none',
    ageGroup: 'adult',
    interventionStyle: style,
    interventionSource: 'explore',
    intensityBefore,
    stateFingerprint,
  })
  assert.equal(saveOutcome(id, { intensityAfter: after, helpfulness }), true)
}

function completeDurable(id, style, after, later, helpfulness, now) {
  recordCompletedSession(id, {
    focus: 'anxiety',
    mode: 'imagery',
    pace: 'slow',
    duration: 10,
    neuroprofile: 'none',
    ageGroup: 'adult',
    interventionStyle: style,
    interventionSource: 'learned',
    intensityBefore: 8,
  })
  assert.equal(saveOutcome(id, { intensityAfter: after, helpfulness }, now), true)
  assert.equal(saveDelayedOutcome(id, { intensityLater: later }, now + 31 * 60 * 1000), true)
}

test('intensity is reduced to three stable context bands', () => {
  assert.equal(getIntensityBand(0), 'low')
  assert.equal(getIntensityBand(3), 'low')
  assert.equal(getIntensityBand(4), 'medium')
  assert.equal(getIntensityBand(6), 'medium')
  assert.equal(getIntensityBand(7), 'high')
  assert.equal(getIntensityBand(10), 'high')
  assert.equal(getIntensityBand(undefined), null)
})

test('state fingerprint accepts only complete 0/1/2 ratings and has stable distance', () => {
  const a = { bodyActivation: 0, thoughtLoop: 2, movementNeed: 0 }
  const b = { bodyActivation: 2, thoughtLoop: 0, movementNeed: 2 }
  assert.deepEqual(normalizeStateFingerprint(a), a)
  assert.equal(normalizeStateFingerprint({ bodyActivation: 0, thoughtLoop: 2 }), null)
  assert.equal(normalizeStateFingerprint({ ...a, movementNeed: 3 }), null)
  assert.equal(stateFingerprintDistance(a, a), 0)
  assert.equal(stateFingerprintDistance(a, b), 6)
  assert.equal(stateFingerprintDistance(a, null), null)
})

test('auto still explores each safe recipe only twice, then learns', () => {
  clearPersonalAdaptation()
  const fingerprint = { bodyActivation: 1, thoughtLoop: 1, movementNeed: 1 }
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'balanced')

  complete('b1', 'balanced', 3, 5, 8, fingerprint)
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'grounded')

  complete('g1', 'grounded', 5, 4, 8, fingerprint)
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'rehearsal')

  complete('r1', 'rehearsal', 6, 3, 8, fingerprint)
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'balanced')

  complete('b2', 'balanced', 2, 5, 8, fingerprint)
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'grounded')

  complete('g2', 'grounded', 5, 4, 8, fingerprint)
  assert.equal(getInterventionPlan('anxiety', 8, fingerprint).style, 'rehearsal')

  complete('r2', 'rehearsal', 6, 3, 8, fingerprint)
  const learned = getInterventionPlan('anxiety', 8, fingerprint)
  assert.equal(learned.phase, 'learned')
  assert.equal(learned.style, 'balanced')
  assert.equal(learned.totalSamples, 6)
})

test('the same focus can learn different recipes at low and high intensity', () => {
  clearPersonalAdaptation()

  complete('lb1', 'balanced', 0, 5, 3)
  complete('lb2', 'balanced', 0, 5, 3)
  complete('lg1', 'grounded', 2, 3, 3)
  complete('lg2', 'grounded', 2, 3, 3)
  complete('lr1', 'rehearsal', 1, 4, 3)
  complete('lr2', 'rehearsal', 1, 4, 3)

  complete('hb1', 'balanced', 7, 3, 9)
  complete('hb2', 'balanced', 7, 3, 9)
  complete('hg1', 'grounded', 2, 5, 9)
  complete('hg2', 'grounded', 2, 5, 9)
  complete('hr1', 'rehearsal', 6, 3, 9)
  complete('hr2', 'rehearsal', 6, 3, 9)

  const low = getInterventionPlan('anxiety', 2)
  const high = getInterventionPlan('anxiety', 9)
  const medium = getInterventionPlan('anxiety', 5)

  assert.equal(low.phase, 'learned')
  assert.equal(low.scope, 'context')
  assert.equal(low.contextBand, 'low')
  assert.equal(low.style, 'balanced')

  assert.equal(high.scope, 'context')
  assert.equal(high.contextBand, 'high')
  assert.equal(high.style, 'grounded')

  assert.equal(medium.scope, 'global')
  assert.equal(medium.contextBand, 'medium')
})

test('same focus and intensity can learn different recipes from state fingerprint', () => {
  clearPersonalAdaptation()
  const looping = { bodyActivation: 0, thoughtLoop: 2, movementNeed: 0 }
  const activated = { bodyActivation: 2, thoughtLoop: 0, movementNeed: 2 }
  const middle = { bodyActivation: 1, thoughtLoop: 1, movementNeed: 1 }

  complete('loop-b1', 'balanced', 2, 5, 8, looping)
  complete('loop-b2', 'balanced', 2, 5, 8, looping)
  complete('loop-g1', 'grounded', 6, 2, 8, looping)
  complete('loop-g2', 'grounded', 6, 2, 8, looping)

  complete('act-b1', 'balanced', 6, 2, 8, activated)
  complete('act-b2', 'balanced', 6, 2, 8, activated)
  complete('act-g1', 'grounded', 2, 5, 8, activated)
  complete('act-g2', 'grounded', 2, 5, 8, activated)

  complete('mid-r1', 'rehearsal', 5, 3, 8, middle)
  complete('mid-r2', 'rehearsal', 5, 3, 8, middle)

  const loopingPlan = getInterventionPlan('anxiety', 8, looping)
  const activatedPlan = getInterventionPlan('anxiety', 8, activated)

  assert.equal(loopingPlan.scope, 'fingerprint')
  assert.equal(loopingPlan.style, 'balanced')
  assert.equal(loopingPlan.fingerprintSamples, 4)
  assert.equal(loopingPlan.eligibleFingerprintStyles, 2)

  assert.equal(activatedPlan.scope, 'fingerprint')
  assert.equal(activatedPlan.style, 'grounded')
  assert.equal(activatedPlan.fingerprintSamples, 4)
  assert.equal(activatedPlan.eligibleFingerprintStyles, 2)
})

test('sparse fingerprint evidence falls back to intensity context', () => {
  clearPersonalAdaptation()
  const target = { bodyActivation: 2, thoughtLoop: 2, movementNeed: 0 }
  const far = { bodyActivation: 0, thoughtLoop: 0, movementNeed: 2 }

  complete('b1', 'balanced', 5, 3, 8, target)
  complete('b2', 'balanced', 5, 3, 8, target)
  complete('g1', 'grounded', 2, 5, 8, far)
  complete('g2', 'grounded', 2, 5, 8, far)
  complete('r1', 'rehearsal', 6, 2, 8, far)
  complete('r2', 'rehearsal', 6, 2, 8, far)

  const plan = getInterventionPlan('anxiety', 8, target)
  assert.equal(plan.scope, 'context')
  assert.equal(plan.eligibleFingerprintStyles, 1)
  assert.equal(plan.style, 'grounded')
})

test('one contextual recipe is not enough evidence to override the global plan', () => {
  clearPersonalAdaptation()

  complete('b1', 'balanced', 5, 3, 8)
  complete('b2', 'balanced', 5, 3, 8)
  complete('g1', 'grounded', 2, 5, 5)
  complete('g2', 'grounded', 2, 5, 5)
  complete('r1', 'rehearsal', 6, 2, 8)
  complete('r2', 'rehearsal', 6, 2, 8)

  const medium = getInterventionPlan('anxiety', 5)
  assert.equal(medium.scope, 'global')
  assert.equal(medium.eligibleContextStyles, 1)
})

test('immediate feedback schedules a 30-minute follow-up with a finite validity window', () => {
  clearPersonalAdaptation()
  const now = 1_000_000
  recordCompletedSession('follow1', {
    focus: 'anxiety',
    interventionStyle: 'balanced',
    intensityBefore: 8,
  })
  assert.equal(saveOutcome('follow1', { intensityAfter: 4, helpfulness: 4 }, now), true)

  assert.equal(getDueFollowUp(now + 29 * 60 * 1000), null)
  const due = getDueFollowUp(now + 30 * 60 * 1000)
  assert.equal(due.sessionId, 'follow1')
  assert.equal(due.intensityAfter, 4)
  assert.equal(getDueFollowUp(now + 30 * 60 * 1000 + 6 * 60 * 60 * 1000 + 1), null)
})

test('delayed outcome completes follow-up and can be skipped without blocking learning', () => {
  clearPersonalAdaptation()
  const now = 2_000_000
  recordCompletedSession('later1', {
    focus: 'anxiety',
    interventionStyle: 'balanced',
    intensityBefore: 8,
  })
  saveOutcome('later1', { intensityAfter: 4, helpfulness: 4 }, now)
  assert.equal(saveDelayedOutcome('later1', { intensityLater: 5 }, now + 31 * 60 * 1000), true)
  assert.equal(getDueFollowUp(now + 32 * 60 * 1000), null)

  recordCompletedSession('skip1', {
    focus: 'anxiety',
    interventionStyle: 'grounded',
    intensityBefore: 8,
  })
  saveOutcome('skip1', { intensityAfter: 3, helpfulness: 5 }, now)
  assert.equal(dismissFollowUp('skip1', now + 31 * 60 * 1000), true)
  assert.equal(getDueFollowUp(now + 32 * 60 * 1000), null)
})

test('durable outcome gets 75 percent of delta weight when available', () => {
  const withoutLater = { intensityBefore: 8, intensityAfter: 2, intensityLater: null }
  const withLater = { intensityBefore: 8, intensityAfter: 2, intensityLater: 7 }
  assert.equal(getEffectiveOutcomeDelta(withoutLater), 6)
  assert.equal(getEffectiveOutcomeDelta(withLater), 2.25)
})

test('a durable result can overturn a strong but short-lived immediate result', () => {
  clearPersonalAdaptation()
  const now = 3_000_000

  completeDurable('b1', 'balanced', 2, 7, 5, now)
  completeDurable('b2', 'balanced', 2, 7, 5, now + 1)
  completeDurable('g1', 'grounded', 4, 2, 4, now + 2)
  completeDurable('g2', 'grounded', 4, 2, 4, now + 3)
  completeDurable('r1', 'rehearsal', 6, 6, 3, now + 4)
  completeDurable('r2', 'rehearsal', 6, 6, 3, now + 5)

  const plan = getInterventionPlan('anxiety', 8)
  assert.equal(plan.phase, 'learned')
  assert.equal(plan.style, 'grounded')
  assert.equal(plan.durableSamples, 6)
})

test('free-text topic is never persisted while numeric fingerprint is allowed', () => {
  clearPersonalAdaptation()
  recordCompletedSession('privacy1', {
    focus: 'general',
    mode: 'imagery',
    pace: 'slow',
    interventionStyle: 'balanced',
    intensityBefore: 5,
    stateFingerprint: { bodyActivation: 2, thoughtLoop: 1, movementNeed: 0 },
    topic: 'THIS PHRASE MUST NEVER BE STORED',
  })

  const raw = localStorage.getItem('guided_imagery_personal_adaptation_v1')
  assert.ok(raw)
  assert.equal(raw.includes('THIS PHRASE MUST NEVER BE STORED'), false)
  const parsed = JSON.parse(raw)
  assert.deepEqual(parsed[0].stateFingerprint, {
    bodyActivation: 2,
    thoughtLoop: 1,
    movementNeed: 0,
  })
})

test('re-recording a session preserves feedback already saved', () => {
  clearPersonalAdaptation()
  recordCompletedSession('same1', {
    focus: 'general',
    interventionStyle: 'balanced',
    intensityBefore: 7,
    stateFingerprint: { bodyActivation: 1, thoughtLoop: 1, movementNeed: 1 },
  })
  saveOutcome('same1', { intensityAfter: 3, helpfulness: 5 })
  recordCompletedSession('same1', {
    focus: 'general',
    interventionStyle: 'balanced',
    intensityBefore: 7,
    stateFingerprint: { bodyActivation: 2, thoughtLoop: 1, movementNeed: 1 },
  })

  const raw = JSON.parse(localStorage.getItem('guided_imagery_personal_adaptation_v1'))
  assert.equal(raw[0].intensityAfter, 3)
  assert.equal(raw[0].helpfulness, 5)
  assert.ok(Number.isFinite(raw[0].followUpDueAt))
  assert.equal(raw[0].stateFingerprint.bodyActivation, 2)
})

test('recipe directives stay subordinate to earlier safety rules', () => {
  const grounded = applyInterventionStyle('meeting tomorrow', 'grounded')
  assert.match(grounded, /concrete and external/i)
  assert.match(grounded, /Earlier safety and focus rules always win/i)

  const rehearsal = applyInterventionStyle('joining a conversation', 'rehearsal')
  assert.match(rehearsal, /ONE small real-world sequence/i)
  assert.match(rehearsal, /Do not rehearse trauma or loss directly/i)

  const fallback = applyInterventionStyle('rest', 'not-a-style')
  assert.match(fallback, /BALANCED/)
})
