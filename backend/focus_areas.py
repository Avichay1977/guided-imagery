"""
Clinical targets and audience adaptations for session scripts.

Two things live here that the prompt templates pull from.

`FOCUS_AREAS` turns a chosen concern into the specific therapeutic approach for
it, so the model is not left to infer an approach from a free-text topic. The
free-text topic still carries the personal detail ("before a maths test",
"when my sister slams the door"); the focus area carries the clinical shape.

`NEURO_ADAPTATIONS` rewrites how the script speaks. Standard relaxation scripts
carry assumptions — that you can picture a beach, that you can feel your own
heartbeat, that sitting still is restful, that "let go" means something
concrete. Those assumptions fail often enough for autistic and ADHD listeners
that a script built on them can be not just useless but actively unpleasant.
None of this is a substitute for treatment; it is a support that sits alongside.
"""

# ── Clinical targets ──────────────────────────────────────────────

FOCUS_AREAS = {
    "general": {
        "label": "General calm",
        "guidance": """
FOCUS — GENERAL RELAXATION:
- No clinical target. Build a pleasant, absorbing experience and rest in it.
- Prioritise enjoyment and safety over any therapeutic manoeuvre.
""",
    },
    "anxiety": {
        "label": "Anxiety and worry",
        "guidance": """
FOCUS — ANXIETY AND WORRY:
- Do NOT try to argue the worry away or reassure it out of existence.
- Teach the shape of anxiety instead: it rises, it peaks, it passes on its own.
- Build a safe place FIRST and make it richly detailed, so there is always
  somewhere to return to before anything difficult is approached.
- Worry containment: a box, a drawer, a locker where worries wait. They are not
  destroyed and not dismissed — they are set down for the length of this
  session, and they will still be there afterwards if they are needed.
- Only if the topic invites it, approach the feared thing gradually and from
  the safe place, with an explicit exit available at every step.
- Close with something portable: one breath, one gesture, one sentence that
  works in a classroom or a corridor where nobody can lie down.
""",
    },
    "panic": {
        "label": "Panic and racing heart",
        "guidance": """
FOCUS — PANIC:
- The goal is riding it out, not preventing it. Never promise it will not happen.
- Name the physical sensations plainly and normalise them: a fast heart, tight
  chest, tingling hands are the body's alarm, not damage, and they subside.
- Emphasise the longer out-breath — it is the single most reliable lever.
- Give a concrete grounding sequence that works anywhere and needs no props.
- Keep sentences short and the voice steady. Do not use long dreamy passages;
  someone rehearsing for panic needs structure, not drift.
- Absolutely no suggestion of losing control, floating away, or dissolving.
""",
    },
    "sleep": {
        "label": "Falling asleep",
        "guidance": """
FOCUS — SLEEP:
- There is no return phase. The session simply fades out. Never count anyone up
  or tell them to become alert at the end.
- Use descending, sinking, heavy, warm imagery throughout.
- Let the rhythm become monotonous on purpose — repetition is the point.
- Sentences get shorter and slower toward the end, trailing off rather than
  concluding.
- No questions, no instructions to notice anything, nothing that requires effort
  in the last third.
""",
    },
    "bfrb": {
        "label": "Hair pulling, skin picking, nail biting",
        "guidance": """
FOCUS — BODY-FOCUSED REPETITIVE BEHAVIOUR (pulling, picking, biting):
- Never shame. No "bad habit", no "stop", no language implying weakness or
  fault. These behaviours are self-regulating, not misbehaving.
- Frame the hands as trying to help — they are seeking a sensation. The work is
  to give them another way to get it, not to punish them.
- Urge surfing is the core: an urge rises, crests, and falls whether or not it
  is acted on. Rehearse noticing one and letting it pass, several times.
- Rehearse the moment BEFORE: the hand drifting upward, the pause, the choice.
  Mental rehearsal of the gap is what transfers to real life.
- Offer a competing sensation the hands can have instead — pressing palms
  together, squeezing a fist, a textured object, hands under thighs.
- Explicitly normalise relapse: pulling again does not undo anything learned.
- This supports habit reversal training, it does not replace it. Do not imply
  the recording alone will stop the behaviour.
""",
    },
    "anger": {
        "label": "Anger and frustration",
        "guidance": """
FOCUS — ANGER AND FRUSTRATION:
- Treat anger as information and as energy, never as something shameful.
- Do not suggest suppressing it. Suggest slowing the gap between feeling it and
  acting on it.
- Physical discharge imagery works better than stillness here: pressing feet
  into the floor, pushing against a wall, heat leaving through the hands.
- Rehearse the early warning signs specifically — jaw, fists, heat in the face,
  narrowing vision — so they can be caught before the peak.
- Close with repair rather than guilt: everyone loses their temper, and what
  matters is what happens next.
""",
    },
    "focus": {
        "label": "Restlessness and focus",
        "guidance": """
FOCUS — RESTLESSNESS AND ATTENTION:
- Do NOT ask for an empty mind or sustained stillness. That is the hardest
  possible demand for this listener and sets up failure.
- Frame a wandering mind as expected and unremarkable. Returning attention is
  the exercise; wandering is not a mistake, it is the repetition.
- Keep the voice near-continuous. Long silences invite drift and boredom.
- Use active, engaging imagery with movement in it rather than static scenes.
- Rehearse one concrete transition: starting a task, or coming back after an
  interruption.
- Permit movement outright — fidgeting, rocking, walking are all fine.
""",
    },
    "social": {
        "label": "Social situations",
        "guidance": """
FOCUS — SOCIAL ANXIETY:
- Rehearse a specific, ordinary moment rather than an abstract fear: walking
  into a room, joining a conversation, being looked at.
- Shift attention outward. Self-monitoring is what makes social anxiety worse,
  so practise noticing the room and other people instead of oneself.
- Include the possibility of it going imperfectly and surviving that — a
  conversation that stalls, a joke that lands flat, and life continuing.
- Do not promise being liked, being smooth, or being confident. Aim for
  tolerable and worth doing.
""",
    },
    "transitions": {
        "label": "Changes and transitions",
        "guidance": """
FOCUS — TRANSITIONS AND CHANGE:
- Name the specific difficulty: stopping something absorbing, or starting
  something unfamiliar, is genuinely hard and not a character flaw.
- Rehearse the transition itself in slow, literal detail, step by step.
- Build in a bridge: a sequence, an object, a phrase that marks the move from
  one thing to the next.
- Predictability is the medicine. Describe exactly what will happen and in what
  order, and then do exactly that.
- Acknowledge that unexpected change is harder still, and rehearse recovering
  from it rather than tolerating it gracefully.
""",
    },
    "sensory": {
        "label": "Sensory overload",
        "guidance": """
FOCUS — SENSORY OVERLOAD AND RECOVERY:
- Overload is a real physical event, not an overreaction. Say so plainly.
- Reduce, do not add. Fewer sensory descriptions, not more. No rich layering of
  smells and textures — that is the opposite of what is needed here.
- Emphasise turning input down: darkness, quiet, pressure, weight, stillness.
- Deep pressure imagery is the most useful: heavy blanket, firm hug, weight on
  the shoulders, being held down gently.
- Recovery takes as long as it takes and it is not a failure to need it.
- Rehearse leaving early and asking for a break as legitimate, effective moves.
""",
    },
    "confidence": {
        "label": "Confidence and self-worth",
        "guidance": """
FOCUS — CONFIDENCE AND SELF-WORTH:
- Ground it in specific remembered evidence, not affirmations. "You are amazing"
  does not survive contact with a bad day; "you did the thing on Tuesday when it
  was hard" does.
- Recall concrete moments of coping, effort or kindness, and dwell on the
  details of them.
- Separate worth from performance explicitly.
- Include self-compassion in the same voice one would use for a friend.
- Avoid comparison with others entirely.
""",
    },
    "pain": {
        "label": "Pain and physical discomfort",
        "guidance": """
FOCUS — PAIN AND DISCOMFORT:
- Never promise pain will disappear. Aim at the relationship with it: less
  bracing, less fear, more room around it.
- Use dial and temperature imagery — turning intensity down a notch, cool water,
  warmth spreading, space widening around a tight place.
- Alternate attention between the painful area and a comfortable one, so
  attention learns it can move.
- Reduce the muscular guarding that pain creates, since that adds pain of
  its own.
""",
    },
    "grief": {
        "label": "Loss and grief",
        "guidance": """
FOCUS — GRIEF AND LOSS:
- Do not try to resolve, reframe or shorten grief. Accompany it.
- Stabilisation only. Never approach the loss itself directly or in detail.
- Build the safe place first and return to it often.
- Permit the full range: sadness, anger, numbness, relief, and nothing at all
  are all normal and none of them are wrong.
- Continuing bonds rather than letting go: what was loved stays, in a form that
  can be carried.
- Check in frequently and keep every step optional.
""",
    },
}

DEFAULT_FOCUS = "general"


# ── Audience adaptations ──────────────────────────────────────────

_SHARED_ND_RULES = """
- Never require closed eyes. Offer them as one option among several: a soft
  gaze at one spot, or looking out of a window, work just as well.
- Never require stillness. Fidgeting, rocking, pacing, stimming and holding an
  object are all compatible with this and should be named as fine.
- Say what is coming before it comes. No surprises in structure or instruction.
- State the length at the start and keep to it.
- Make every instruction genuinely optional, and mean it. Offer real choices
  rather than commands dressed as invitations.
- Never say "empty your mind", "stop thinking", or "clear your head".
- Do not ask what emotion is present or to name a feeling. Describing feelings
  on demand is hard and turns rest into an exam.
- If a suggestion might not land, say so in advance and make that fine:
  "you might notice this, or you might not, and either is completely fine."
"""

NEURO_ADAPTATIONS = {
    "none": "",
    "autism": {
        "label": "Autistic",
        "guidance": f"""
══════════════════════════════════════════════
ADAPTATION — AUTISTIC LISTENER (overrides conflicting rules above)
══════════════════════════════════════════════
{_SHARED_ND_RULES}
- Use literal, concrete language. Figures of speech that describe the body
  doing impossible things — melting, dissolving, floating away, sinking through
  the floor, your arm becoming a balloon — can be confusing or genuinely
  alarming. Say "heavier", "warmer", "looser", "still", "resting" instead.
- Do not assume mental imagery. Many autistic people picture nothing at all.
  Offer parallel routes every time: something to picture, something to hear,
  something to feel physically, or simply something to think about. Say
  explicitly that not seeing a picture is fine and changes nothing.
- Do not rely on interoception. Instructions to notice a heartbeat, the breath
  in the belly, or warmth in the chest often land on nothing, and hunting for a
  sensation that is not detectable is stressful. Prefer things detectable from
  outside the body: the pressure of the chair, feet against the floor, hands
  against each other, the temperature of the air, sounds in the room.
- Keep sensory description sparse and neutral. Do not pile on smells, textures
  and tastes. Avoid anything commonly aversive: sticky, slimy, buzzing,
  crowds, strong perfume, unexpected touch.
- Structure should be visible and repetitive. The same phrases returning is
  reassuring, not boring.
- If the topic allows, use the listener's own interests as the setting. A deeply
  familiar subject is far more absorbing than a generic beach.
""",
    },
    "adhd": {
        "label": "ADHD",
        "guidance": f"""
══════════════════════════════════════════════
ADAPTATION — ADHD LISTENER (overrides conflicting rules above)
══════════════════════════════════════════════
{_SHARED_ND_RULES}
- Keep the voice nearly continuous. Long silences are where attention leaves and
  frustration arrives. Use [short_pause] as the default and reserve [long_pause]
  for genuine peaks — no more than twice in the whole script.
- Keep it moving. Change scene, angle or sensation regularly rather than
  dwelling on one static image for minutes.
- Prefer imagery with motion and interest in it: travelling, building,
  descending, exploring — not standing still in a meadow.
- Treat a wandering mind as part of the exercise, out loud and more than once.
  Coming back is the repetition being practised. Wandering is never a failure.
- Vary sentence rhythm and length. A perfectly even monotone loses attention
  faster than it relaxes.
- Front-load the point. Say what this session is for in the first few sentences.
- Movement is permitted throughout and should be said so explicitly.
""",
    },
    "audhd": {
        "label": "Autistic + ADHD (AuDHD)",
        "guidance": f"""
══════════════════════════════════════════════
ADAPTATION — AUTISTIC + ADHD LISTENER (overrides conflicting rules above)
══════════════════════════════════════════════
This listener has both profiles at once, and their needs genuinely pull in
opposite directions: predictable sameness and enough novelty to hold attention;
a settled body and permission to move. Serve both rather than averaging them —
keep the STRUCTURE highly predictable while keeping the CONTENT moving.
{_SHARED_ND_RULES}
- Literal, concrete language throughout. No melting, dissolving, floating away,
  or bodies behaving impossibly. Use heavier, warmer, looser, slower, resting.
- Do not assume mental imagery, and do not rely on interoception. Offer a
  picture, a sound, a physical pressure and a thought as parallel routes, and
  anchor to what is detectable from outside: the chair, the floor, the hands,
  the air, the sounds in the room. Say plainly that noticing nothing is fine.
- Predictable frame, moving content: announce the sequence at the start, use the
  same signposting phrases each time, but let the scene itself change and
  develop so attention has somewhere to go.
- Short pauses, not long ones. Silence longer than a few seconds tends to be
  filled with restlessness rather than rest. Use [short_pause] by default,
  [breath] where breathing is guided, and [long_pause] at most twice.
- Sparse, neutral sensory detail. Two or three sensory threads at a time, not
  five. Nothing sticky, buzzing, crowded or strongly scented.
- Movement, fidgeting and stimming are explicitly fine and should be named as
  fine early on, not as a concession but as a normal way to listen.
- A wandering mind is expected and is not a failure. Say this more than once.
- If the topic allows, build the session around something the listener already
  loves. Familiar depth beats generic calm.
- No demand for eye closure, stillness, emptying the mind, or naming feelings.
""",
    },
}

DEFAULT_NEUROPROFILE = "none"


# ── Age bands ─────────────────────────────────────────────────────

AGE_BANDS = {
    "young_child": {
        "label": "Young child (4-7)",
        "guidance": """
TARGET AUDIENCE: Young children, roughly 4-7.
- A simple story with a friendly companion character. Not a meditation.
- Very short sentences, 4-8 words.
- Entirely concrete. No abstract ideas, no metaphors about the mind.
- The child is the capable one in the story and holds something helpful.
- Warm, parental, unhurried tone.
- Keep the whole thing brief regardless of the requested length.
""",
    },
    "child": {
        "label": "Child (8-12)",
        "guidance": """
TARGET AUDIENCE: Children, roughly 8-12.
- Story-led, with a guide character or a helpful object.
- Concrete, tangible imagery. Sentences of 5-10 words.
- Everyday metaphors they already own: turning down a volume dial, changing a
  channel, pausing a game, a backpack that can be set down.
- Give them agency and control inside the story.
- Do not lecture and do not moralise.
""",
    },
    "teen": {
        "label": "Teen (13-17)",
        "guidance": """
TARGET AUDIENCE: Teenagers, roughly 13-17.
- Speak to them as a person, not a child. No baby talk, no cutesy characters,
  no forced enthusiasm. Condescension is detected instantly and ends the session.
- Respect autonomy above all: their choice whether to follow anything here.
- Real contexts: school, friendships, family, sleep, phones, pressure, identity.
- Abstract metaphor and self-directed rescripting are fine at this age.
- Do not promise that everything will be fine. Aim for genuinely useful.
- Avoid therapy-speak and slang alike; plain, respectful language works.
""",
    },
    "adult": {
        "label": "Adult",
        "guidance": "",
    },
    "senior": {
        "label": "Older adult",
        "guidance": """
TARGET AUDIENCE: Older adults.
- Unhurried pacing and clear, uncluttered sentences.
- Do not assume physical comfort: offer seated and lying options, and avoid
  instructions that assume easy movement or a flexible body.
- Life review and continuity imagery land well; avoid anything that frames age
  as decline.
- Speak with respect, never with the sing-song tone used for children.
""",
    },
}

# The API used to take three coarse values. Keep them working.
AGE_ALIASES = {"children": "child", "teens": "teen", "adults": "adult"}
DEFAULT_AGE = "adult"


def resolve_age(age_group: str) -> str:
    age = AGE_ALIASES.get(age_group, age_group)
    return age if age in AGE_BANDS else DEFAULT_AGE


def focus_guidance(focus: str) -> str:
    return FOCUS_AREAS.get(focus, FOCUS_AREAS[DEFAULT_FOCUS])["guidance"]


def neuro_guidance(neuroprofile: str) -> str:
    entry = NEURO_ADAPTATIONS.get(neuroprofile)
    if not entry or entry == "":
        return ""
    return entry["guidance"]


def age_guidance(age_group: str) -> str:
    return AGE_BANDS[resolve_age(age_group)]["guidance"]
