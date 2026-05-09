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

### Website signals as a talking point

Website signals are one input — not the default angle. Always weigh them against CRM signals and choose whichever is strongest and most specific for this lead.

Website observations are particularly useful when:
- CRM data is thin and there is no strong relationship signal to build on
- A clear, observable mismatch exists between what the website shows and what you would expect
- You want to show the prospect you have done your homework before reaching out

A website mismatch is a talking point, not a strategy. It works best as a door-opener — something specific you noticed that invites a response — not as the main commercial argument.

**Mismatches worth considering (use only when genuinely present):**

- **Book Now CTA but no booking software detected** (`has_book_now_cta: true`, `has_direct_booking: false`) — something to gently surface: "I saw a Book Now button but couldn't find where it goes."
- **No booking capability at all** (`no_booking_detected: true`) — confirms the direct booking gap is real and visible from the outside.
- **Competitor software on site** (`detected_software` is Rezdy, Checkfront, Bokun, etc.) — useful context. Do not pitch against it. It may surface a question about how it is working for them.
- **OTA badges prominent, no direct booking widget** — OTA dependency is visible from the outside. Useful supporting signal, rarely a standalone angle.
- **CRM says one software, website shows another** — worth noting as a gap in what we know, not as an angle in itself.

If the CRM has a stronger signal — a prior conversation, a pain point already surfaced, a trigger event, a relationship — lead with that instead.

### General rules

- The angle must be explainable in one sentence
- The claim must be proportionate to your evidence — weak signals = weak claims
- "Why now" must be grounded in something real (timing, stale deal, competitor signal, season) — not invented urgency
- Avoid vague claims: "improve operations", "grow bookings", "save time" — these are not angles
- A website observation is not an accusation — frame it as something you noticed, not something you know

Return this JSON structure:

{
  "primary_pain_point": "the specific problem this company has right now",
  "sales_angle": "the single sentence insight or reframe to lead with",
  "supporting_signal": "the specific CRM fact or observation that supports this angle",
  "why_now": "concrete reason this is worth raising at this moment — not generic urgency",
  "claim_strength": "strong | moderate | weak",
  "claim_strength_reasoning": "why you rated the claim strength this way"
}
