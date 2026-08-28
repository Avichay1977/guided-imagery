import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clearPersonalAdaptation,
  getIntensityBand,
  getInterventionPlan,
  recordCompletedSession,
  saveOutcome,
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

function complete(id, style, after, helpfulness, intensityBefore = 8) {
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
  })
  assert.equal(saveOutcome(id, { intensityAfter: after, helpfulness }), true)
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

test('auto still explores each safe recipe only twice, then learns', () => {
  clearPersonalAdaptation()
  assert.equal(getInterventionPlan('anxiety', 8).style, 'balanced')

  complete('b1', 'balanced', 3, 5)
  assert.equal(getInterventionPlan('anxiety', 8).style, 'grounded')

  complete('g1', 'grounded', 5, 4)
  assert.equal(getInterventionPlan('anxiety', 8).style, 'rehearsal')

  complete('r1', 'rehearsal', 6, 3)
  assert.equal(getInterventionPlan('anxiety', 8).style, 'balanced')

  complete('b2', 'balanced', 2, 5)
  assert.equal(getInterventionPlan('anxiety', 8).style, 'grounded')

  complete('g2', 'grounded', 5, 4)
  assert.equal(getInterventionPlan('anxiety', 8).style, 'rehearsal')

  complete('r2', 'rehearsal', 6, 3)
  const learned = getInterventionPlan('anxiety', 8)
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

test('free-text topic is never persisted in adaptation history', () => {
  clearPersonalAdaptation()
  recordCompletedSession('privacy1', {
    focus: 'general',
    mode: 'imagery',
    pace: 'slow',
    interventionStyle: 'balanced',
    intensityBefore: 5,
    topic: 'THIS PHRASE MUST NEVER BE STORED',
  })

  const raw = localStorage.getItem('guided_imagery_personal_adaptation_v1')
  assert.ok(raw)
  assert.equal(raw.includes('THIS PHRASE MUST NEVER BE STORED'), false)
})

test('re-recording a session preserves feedback already saved', () => {
  clearPersonalAdaptation()
  recordCompletedSession('same1', {
    focus: 'general',
    interventionStyle: 'balanced',
    intensityBefore: 7,
  })
  saveOutcome('same1', { intensityAfter: 3, helpfulness: 5 })
  recordCompletedSession('same1', {
    focus: 'general',
    interventionStyle: 'balanced',
    intensityBefore: 7,
  })

  const raw = JSON.parse(localStorage.getItem('guided_imagery_personal_adaptation_v1'))
  assert.equal(raw[0].intensityAfter, 3)
  assert.equal(raw[0].helpfulness, 5)
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
