## Stage 3 — Angle

You have an assessment and a selected strategy. Your job is to identify the single strongest angle for this lead — one pain point, one insight, one reason to act now.

---

### Assessment (from Stage 1)
{{assessment}}

---

### Strategy result (from Stage 2)
{{strategy_result}}

---

### Strategy instructions
{{strategy_instructions}}

---

## Task

Identify the ONE angle to lead with. Do not combine multiple pain points. Pick the strongest signal and build a single, specific angle from it.

### Priority order for angle selection

Always work through this hierarchy. Stop at the first level where a real signal exists.

**1. CRM relationship signals (strongest)** — anything from an actual interaction: a pain point the rep has already uncovered, an objection raised, a prior conversation thread, a trigger event (ownership change, new tour launch, competitor mentioned), a timing signal from notes, a response or non-response pattern. These are the most specific and credible angles because they reflect what this specific person has actually said or done.

**2. CRM deal/account signals (strong)** — deal size, days since last activity, lead status, current software explicitly mentioned in the CRM, known OTA dependency stated in notes. Concrete and account-specific, but less personal than relationship signals.

**3. Vertical/timing context (moderate)** — seasonal timing, industry-wide patterns, competitor dynamics relevant to this activity type. Useful for "why now" framing but not specific enough to stand alone as an angle.

**4. Website observations (weak — last resort only)** — automated scrape data such as no booking widget detected, Book Now CTA with no booking software, OTA badges visible. Use a website observation as the primary angle ONLY when levels 1–3 yield nothing concrete. A website observation is a cold door-opener, not a commercial argument.

**Before selecting a website observation as your angle:** explicitly confirm that the assessment contains no CRM relationship signals, no CRM deal signals, and no usable vertical timing. If any of those exist — even weakly — use them instead.

### Rules

- The angle must be explainable in one sentence
- The claim must be proportionate to your evidence — weak signals = weak claims
- "Why now" must be grounded in something real — not invented urgency
- Avoid vague claims: "improve operations", "grow bookings", "save time" — these are not angles
- A website observation is not an accusation — if you must use one, frame it as something you noticed, not something you know
- If the only available angle is a generic vertical assumption with no specific signal behind it, set `claim_strength` to "weak" and route toward a discovery approach rather than a pitch

Return this JSON structure:

{
  "primary_pain_point": "the specific problem this company has right now",
  "sales_angle": "the single sentence insight or reframe to lead with",
  "supporting_signal": "the specific CRM fact or observation that supports this angle",
  "why_now": "concrete reason this is worth raising at this moment — not generic urgency",
  "claim_strength": "strong | moderate | weak",
  "claim_strength_reasoning": "why you rated the claim strength this way"
}
