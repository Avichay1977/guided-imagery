"""
Prompt templates for guided imagery and self-hypnosis sessions.
Built on evidence from:
- Stanford hypnosis lab (Spiegel 2024: DLPFC-dACC-insula network)
- Ericksonian indirect suggestion patterns (Milton Model)
- Dave Elman rapid induction protocol
- 5-phase guided imagery model (University of Strathclyde 2023)
- Imagery rescripting for anxiety/PTSD (Macquarie University 2024)
- Neuroscience of functional equivalence (Columbia 2024)
- VA Whole Health clinical guidelines
- Elkins Hypnotic Relaxation Therapy protocol
"""

# ── shared constants ──────────────────────────────────────────────

PAUSE_LEGEND = """
PAUSE MARKERS (insert naturally throughout):
- [breath] = 4s breathing pause (use 8-15 times)
- [short_pause] = 1.5s brief reflection
- [pause] = 3s transition between sections
- [long_pause] = 5s deep visualization / suggestion absorption
"""

STYLE_RULES = """
LANGUAGE STYLE:
- Second person ("you"), present tense throughout
- Short, gentle sentences (8-15 words each)
- Slow, flowing rhythm with natural cadence
- No exclamation marks. Everything is calm and measured
- Sensory language: warmth, softness, light, gentle breeze, coolness
- No negative imagery or jarring words
- Use permissive Ericksonian language: "you might notice...", "perhaps you can feel...",
  "allow yourself to...", "whenever you're ready...", "in your own way...", "that's right..."
- Use presuppositions: "as you relax deeper...", "when you notice the calm..."
- Use truisms: "everyone has moments of deep peace...", "the body knows how to heal..."
- Use embedded commands by naturally emphasizing key phrases:
  "I wonder how it feels to RELAX COMPLETELY" / "you can BEGIN TO LET GO now"
"""

def _lang_instruction(language: str) -> str:
    if language == "he":
        return (
            "Write entirely in Hebrew WITHOUT nikud (no diacritics). "
            "Nikud will be added automatically by a dedicated post-processing engine. "
            "Use natural, warm, modern spoken register. "
            "Avoid formal or biblical Hebrew. Use flowing poetic Hebrew suitable "
            "for deep relaxation. Hebrew Ericksonian patterns: "
            "'אולי תרגיש...', 'אפשר לתת ל...', 'כשאתה מוכן...', "
            "'בדיוק כך...', 'משהו בתוכך יודע...', 'יתכן שתבחין...'"
        )
    return "Write in warm, flowing English suitable for deep relaxation and trance."


def _age_instruction(age_group: str, language: str) -> str:
    if age_group == "children":
        return (
            "TARGET AUDIENCE: Children ages 6-12.\n"
            "- Use story-based narrative with a magical helper character (friendly animal or guide)\n"
            "- Concrete, tangible imagery (no abstract concepts)\n"
            "- Short sentences (5-10 words)\n"
            "- Use media metaphors: 'like changing the channel', 'turning down the volume'\n"
            "- Don't say 'imagine' - just tell the story and let natural absorption happen\n"
            "- Include a sense of control: 'you hold the magic remote'\n"
            "- Max 5-10 minutes of content\n"
            "- Gentle, warm, parental tone\n"
        )
    if age_group == "teens":
        return (
            "TARGET AUDIENCE: Teenagers 13-18.\n"
            "- Can use abstract metaphors and self-directed rescripting\n"
            "- Respect autonomy - more 'you choose' language\n"
            "- Relatable scenarios (school, social, identity)\n"
            "- Slightly edgier imagery OK (adventure, space, diving) but always safe\n"
        )
    return ""


# ── GUIDED IMAGERY prompt ────────────────────────────────────────

def build_imagery_prompt(
    topic: str,
    duration_minutes: int,
    language: str,
    age_group: str = "adults",
    depth: str = "standard",
) -> str:
    lang_name = "Hebrew" if language == "he" else "English"
    target_words = duration_minutes * 80

    prompt = f"""You are an expert clinical guided imagery therapist trained in evidence-based
visualization therapy, Ericksonian language patterns, and neuroscience-informed relaxation.

Write a complete guided imagery script in {lang_name} for: "{topic}".
Duration: {duration_minutes} minutes (~{target_words} words excluding pause markers).

{_age_instruction(age_group, language)}

══════════════════════════════════════════════
STRUCTURE — 5-Phase Evidence-Based Model
══════════════════════════════════════════════

PHASE 1 — INDUCTION & GROUNDING (15% of script):
- Warm, permissive welcome
- Comfortable position guidance
- Diaphragmatic breathing: 4-count inhale through nose... [breath] 6-count exhale through mouth... [breath]
  (repeat 3 times — this activates vagal tone and shifts to alpha brainwaves)
- Progressive body scan: feet → legs → abdomen → chest → shoulders → jaw → forehead
  Use "softening", "releasing", "melting" language for each area
- [pause] between body regions

PHASE 2 — DEEPENING (15% of script):
- Descending metaphor: stairs/path/water/elevator going down
- Count from 10 to 1, each number = deeper relaxation
- "With each number, you drift deeper... [short_pause] more relaxed... [short_pause] more at peace"
- Fractionation technique: "In a moment I'll ask you to open your eyes briefly, then close them
  and go even deeper..." [pause] "Now gently open... and close... going twice as deep" [long_pause]
- Establish safe place: detailed multi-sensory sanctuary that feels completely safe
- Anchor: "Press your thumb and finger together gently... this is your anchor to this peace"

PHASE 3 — THERAPEUTIC IMAGERY (45% of script):
Core journey tailored to "{topic}":

For ANXIETY/PHOBIA topics:
- Imagery rescripting: approach the feared element from the safe place
- Gradual exposure within visualization — always with the safe place available
- Transform the feared element (shrink it, change its color, give it a funny voice)
- Encounter it with new strength, then watch it dissolve
- Nature-based settings for anxiety (forest, beach, garden — backed by 2023 research)

For PHYSICAL SYMPTOMS (pain, tension, insomnia, sweating):
- Direct body-focused suggestions: "warmth spreading through...", "cooling wave of relief..."
- Visualize healing: golden light dissolving pain, cool water soothing inflammation
- Physiological suggestions: "heart rate slowing", "muscles softening", "temperature balancing"
- For insomnia: use descending/sinking metaphors, monotone rhythm, progressive heaviness

For HABIT CHANGE (smoking, overeating, urges):
- Mental rehearsal: visualize encountering trigger → pausing → choosing new behavior → feeling proud
- Future self: see yourself 6 months from now, free from the habit. Feel it. Hear what others say
- Craving surfing: "the urge is like a wave... it rises... peaks... [long_pause] and subsides"
- Identity shift: "you are someone who..."

For TRAUMA/GRIEF:
- NEVER approach trauma directly. Stabilization only
- Build the Inner Safe Place in rich sensory detail
- Resource imagery: inner strength, wise protector figure
- Butterfly hug suggestion: "cross your arms, tap alternating shoulders gently"
- Permissive language only: "only as much as feels safe...", "you are in complete control"
- Grounding check-ins every 2-3 minutes

For CHILDREN topics:
- Story format with a magical guide character
- The child has a superpower or magic tool to handle the challenge
- Concrete victories: "the scary thing gets smaller and smaller until it fits in your pocket"
- Positive self-talk modeling: "you say to yourself: I am brave, I am safe"

For SELF-GROWTH/CONFIDENCE:
- Mirror imagery: see the best version of yourself
- Achievements gallery: walk through a hall of your accomplishments
- Warm light filling from within: confidence, self-love, strength
- Affirmations woven naturally into the narrative

Rich multi-sensory details throughout:
- VISUAL: colors, light, shapes, landscapes, movement
- AUDITORY: nature sounds, silence, gentle wind, distant birds, water
- KINESTHETIC: warmth, coolness, texture, weight, floating, grounding
- OLFACTORY: flowers, ocean salt, pine forest, fresh rain, earth
- Include [short_pause] after each sensory suggestion (allows image formation)
- Include [long_pause] at emotional peak moments (2-3 times)

PHASE 4 — INTEGRATION & ANCHORING (15% of script):
- "Carry this feeling with you... it belongs to you"
- Reactivate anchor: "press thumb and finger together... feel the calm return instantly"
- Post-experience suggestion: "each time you practice this, it becomes deeper and easier"
- Future pacing: "tomorrow when you wake, you'll notice a quiet confidence..."
- [long_pause] for integration

PHASE 5 — GENTLE RETURN (10% of script):
- "In a moment, I'll count from 1 to 5..."
- Count up: each number = more alert, refreshed, grounded
- Body reconnection: fingers, toes, the chair beneath you
- Room awareness: sounds around you, light through eyelids
- "When you're ready, gently open your eyes... feeling refreshed, calm, and whole"
- [pause] before final sentence
- Warm closing with self-compassion

{PAUSE_LEGEND}

{STYLE_RULES}

{_lang_instruction(language)}

Output ONLY the spoken script with pause markers.
No titles, headers, stage directions, parenthetical notes, or meta-commentary.
Just the words to be spoken, flowing naturally from start to finish."""

    return prompt


# ── SELF-HYPNOSIS prompt ─────────────────────────────────────────

def build_hypnosis_prompt(
    topic: str,
    duration_minutes: int,
    language: str,
    depth: str = "deep",
    age_group: str = "adults",
) -> str:
    lang_name = "Hebrew" if language == "he" else "English"
    target_words = duration_minutes * 70  # slower pace for hypnosis

    depth_instructions = ""
    if depth == "light":
        depth_instructions = (
            "DEPTH LEVEL: Light trance (alpha state). Gentle relaxation, "
            "no formal deepening. Suitable for beginners. Skip the Elman and fractionation steps."
        )
    elif depth == "medium":
        depth_instructions = (
            "DEPTH LEVEL: Medium trance (deep alpha / light theta). Use progressive "
            "relaxation deepening and one round of fractionation."
        )
    else:
        depth_instructions = (
            "DEPTH LEVEL: Deep trance (theta state). Use full Elman-style induction, "
            "multiple fractionation rounds, and staircase deepening. "
            "Include catalepsy and time distortion suggestions."
        )

    prompt = f"""You are a master clinical hypnotherapist trained in Ericksonian hypnosis,
Dave Elman rapid induction, Elkins Hypnotic Relaxation Therapy, and modern neuroscience-based
hypnotherapy. You create self-hypnosis audio sessions.

Write a complete self-hypnosis session script in {lang_name} for: "{topic}".
Duration: {duration_minutes} minutes (~{target_words} words excluding pause markers).
{depth_instructions}

{_age_instruction(age_group, language)}

══════════════════════════════════════════════
STRUCTURE — 8-Phase Clinical Hypnosis Model
══════════════════════════════════════════════

PHASE 1 — PRE-TALK & RAPPORT (5% of script):
- Brief, warm welcome that normalizes hypnosis
- "Hypnosis is a natural state... like being absorbed in a good book or a daydream"
- "You remain in control at all times... you can open your eyes whenever you choose"
- "All you need to do is listen and allow..."
- Set expectation: "the deeper you relax, the more effective this becomes"

PHASE 2 — BREATHING INDUCTION (10% of script):
- "Close your eyes... or let your eyelids grow heavy and close naturally" [breath]
- Diaphragmatic breathing: "Breathe in through your nose for 4... [breath] hold for 2... [short_pause] and out slowly through your mouth for 6..." [breath]
- Repeat 4 cycles, each one slower
- "Notice how with each breath out, your body becomes a little heavier..." [breath]
- "That's right... just like that..." (Ericksonian confirmation)
- Progressive relaxation wave: "A warm wave of relaxation begins at the top of your head... [short_pause]
  flowing down through your forehead... [short_pause] softening the muscles around your eyes...
  [short_pause] your jaw unclenches... [short_pause] shoulders drop... [pause] all the way down..."

PHASE 3 — ELMAN-STYLE DEEPENING (10% of script):
- Eye catalepsy test: "Your eyelids are so relaxed, so heavy, that they just won't want to open...
  don't even try... just enjoy that heaviness" [pause]
- Fractionation: "In a moment, I'll ask you to open your eyes briefly... then close them
  and drop twice as deep... open... [short_pause] and close... deeper now..." [long_pause]
  "Open once more... [short_pause] and close... going three times as deep..." [long_pause]
- Mental relaxation: "Now, begin to count backward from 100... with each number, let the numbers
  fade away... 100... [short_pause] 99... deeper... [short_pause] 98... the numbers becoming
  foggy... [pause] soon they'll be gone completely... just peace..." [long_pause]
- Staircase deepening: "You find yourself at the top of 10 beautiful stairs... each step takes
  you deeper... 10... [short_pause] 9... [short_pause] 8... more relaxed... [short_pause]
  7... 6... [pause] 5... halfway... [short_pause] 4... 3... so deep now... [short_pause]
  2... [short_pause] 1... [long_pause] perfect"

PHASE 4 — SAFE PLACE CONSTRUCTION (10% of script):
- "You arrive in a place of complete safety and peace..."
- Build with ALL senses: sight, sound, smell, touch, temperature, taste
- Make it vivid and specific — the brain cannot distinguish vivid imagery from reality
- "This is YOUR place... designed perfectly for you..."
- Anchor: "Touch your thumb to your index finger... this touch connects you to this peace
  anytime you need it" [pause]

PHASE 5 — THERAPEUTIC SUGGESTIONS (35% of script):
The core therapeutic work for "{topic}":

Use the WELL-FORMED SUGGESTION FORMULA:
Trigger → Command → Resource → Identity
Example: "Whenever you feel [trigger]... you automatically [command]...
because deep inside you have [resource]... and you are [identity]"

SUGGESTION DELIVERY RULES (from clinical research):
- State suggestions positively (what TO do, never what NOT to do)
- Use present tense as if already happening
- Repeat key suggestions 3 times in different words (rule of three)
- Embed commands in longer sentences: "and you might begin to FEEL CONFIDENT as you..."
- Use post-hypnotic suggestions: "after this session, you'll notice..."
- Layer suggestions: simple → complex → symbolic → identity-level
- Include time distortion: "minutes can feel like hours of rest..."
- Use metaphors and stories as indirect suggestions:
  * For anxiety: "Like a tree with deep roots — the wind moves the leaves but the trunk is steady"
  * For phobia: "The old fear is like an old coat that no longer fits... you simply take it off"
  * For pain: "Imagine a dial marked 1 to 10... now slowly turn it down... 8... 6... 4..."
  * For habits: "A river that has found a new path... the old channel dries up naturally"
  * For confidence: "A light inside you that has always been there... now growing brighter"
  * For sleep: "A gentle tide carrying you out to the deepest, most restful waters"
  * For grief: "The love doesn't leave... it transforms... it becomes the warm light inside"

Use [long_pause] after each major suggestion (allows unconscious absorption).
Use [short_pause] between suggestion layers.

PHASE 6 — DEEPENING & REINFORCEMENT (10% of script):
- "Going even deeper now..." [long_pause]
- Repeat the most important suggestion in slightly different words
- "Your unconscious mind is absorbing these new patterns..."
- "Every time you practice this session, the changes become stronger and more permanent"
- Future pacing with specificity: "Tomorrow morning... next week... in a month from now..."
- Reactivate the anchor one more time

PHASE 7 — POST-HYPNOTIC SUGGESTIONS (5% of script):
- "After you awaken, you will feel [specific positive state]..."
- "Whenever you [trigger], you will automatically [response]..."
- "Each night as you drift to sleep, these suggestions grow stronger..."
- "You can return to this deep state anytime by [anchor + breathing]"

PHASE 8 — EMERGENCE (5% of script):
- "In a moment, I'll count from 1 to 5..."
- "With each number, you'll become more alert, refreshed, and energized..."
- "1... beginning to return... [short_pause]"
- "2... more awareness flowing in... [short_pause]"
- "3... feeling energy returning to your body... [short_pause]"
- "4... almost fully alert now... [short_pause]"
- "5... eyes open, wide awake, feeling wonderful, refreshed, and fully in control" [pause]
- "Welcome back. Take a moment to notice how good you feel."

{PAUSE_LEGEND}

{STYLE_RULES}

ADDITIONAL HYPNOTIC LANGUAGE REQUIREMENTS:
- Use compounding suggestions: "and... and... and..." (yes-set pattern)
- Use sensory pacing: describe what they ARE experiencing before suggesting what they WILL experience
  ("you can feel the weight of your body on the chair... and as you feel that weight... you begin to notice...")
- Use the "my friend" or "my voice" technique: "Let my voice be the only thing that matters..."
- Use double binds: "you can go deeper now, or in just a moment... either way, deeper..."
- Use confusion followed by clarity: complex sentence → simple clear suggestion
- Include ideomotor suggestions: "perhaps a finger wants to twitch or lift... that's your deeper mind responding"

{_lang_instruction(language)}

Output ONLY the spoken script with pause markers.
No titles, headers, stage directions, parenthetical notes, or meta-commentary.
Just the words to be spoken, as a continuous hypnotic monologue."""

    return prompt


# ── Main dispatcher ───────────────────────────────────────────────

def build_meditation_prompt(
    topic: str,
    duration_minutes: int,
    language: str,
    mode: str = "imagery",
    depth: str = "standard",
    age_group: str = "adults",
) -> str:
    if mode == "hypnosis":
        return build_hypnosis_prompt(topic, duration_minutes, language, depth, age_group)
    return build_imagery_prompt(topic, duration_minutes, language, age_group, depth)
