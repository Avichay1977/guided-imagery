export const INTERVENTION_STYLES = ['balanced', 'grounded', 'rehearsal']

const STYLE_DIRECTIVES = {
  balanced: `SESSION APPROACH PREFERENCE — BALANCED:
Within every earlier focus, age and neurodivergent rule, keep the session balanced.
Use grounding, imagery and practical integration in roughly equal measure.
Do not introduce exposure or difficult material unless the earlier focus rules explicitly allow it.
Earlier safety and focus rules always win over this preference.`,

  grounded: `SESSION APPROACH PREFERENCE — GROUNDED:
Within every earlier focus, age and neurodivergent rule, make the session more concrete and external.
Prioritize anchors that can be detected from outside the body: chair, floor, hands, room sounds and air temperature.
Reduce abstract symbolism and elaborate inner imagery. End with one portable grounding cue that can be used in ordinary life.
Do not add exposure, intensify difficult material, or override any earlier safety rule. Earlier safety and focus rules always win.`,

  rehearsal: `SESSION APPROACH PREFERENCE — REHEARSAL:
Within every earlier focus, age and neurodivergent rule, devote more of the core work to rehearsing ONE small real-world sequence relevant to the user's topic.
Keep the sequence ordinary, optional and repeatable: notice the cue, pause, use the permitted coping response, then continue.
Do not rehearse trauma or loss directly. Do not escalate exposure. For grief, pain or sensory overload, rehearse only safe coping, recovery or transition steps allowed by the focus rules.
Earlier safety and focus rules always win over this preference.`,
}

export function normalizeInterventionStyle(style) {
  return INTERVENTION_STYLES.includes(style) ? style : 'balanced'
}

export function applyInterventionStyle(topic, style = 'balanced') {
  const normalized = normalizeInterventionStyle(style)
  const cleanTopic = String(topic || '').trim()
  return `${cleanTopic}\n\n${STYLE_DIRECTIVES[normalized]}`.trim()
}
