import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clearPersonalAdaptation,
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

function complete(id, style, after, helpfulness) {
  recordCompletedSession(id, {
    focus: 'anxiety',
    mode: 'imagery',
    pace: 'slow',
    duration: 10,
    neuroprofile: 'none',
    ageGroup: 'adult',
    interventionStyle: style,
    interventionSource: 'explore',
    intensityBefore: 8,
  })
  assert.equal(saveOutcome(id, { intensityAfter: after, helpfulness }), true)
}

test('auto explores each safe recipe twice, then learns the best measured recipe', () => {
  clearPersonalAdaptation()
  assert.deepEqual(getInterventionPlan('anxiety').style, 'balanced')

  complete('b1', 'balanced', 3, 5)
  assert.equal(getInterventionPlan('anxiety').style, 'grounded')

  complete('g1', 'grounded', 5, 4)
  assert.equal(getInterventionPlan('anxiety').style, 'rehearsal')

  complete('r1', 'rehearsal', 6, 3)
  assert.equal(getInterventionPlan('anxiety').style, 'balanced')

  complete('b2', 'balanced', 2, 5)
  assert.equal(getInterventionPlan('anxiety').style, 'grounded')

  complete('g2', 'grounded', 5, 4)
  assert.equal(getInterventionPlan('anxiety').style, 'rehearsal')

  complete('r2', 'rehearsal', 6, 3)
  const learned = getInterventionPlan('anxiety')
  assert.equal(learned.phase, 'learned')
  assert.equal(learned.style, 'balanced')
  assert.equal(learned.samples, 6)
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
