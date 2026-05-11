## Stage 6 — Discovery Package

A rep is about to reach out to a neglected pipeline account. You have the Stage 1 assessment, the selected angle, and contextual knowledge about their activity type and current software.

Generate a discovery package that makes the rep sound like they actually know this type of business.

---

### Assessment (Stage 1)
{{assessment}}

---

### Selected Angle (Stage 3)
{{angle_result}}

---

### Activity Type Context
{{activity_type_context}}

---

### Current Software Context
{{software_context}}

---

## Task

### 1. Discovery questions (3–5)
Questions to ask in the conversation that will confirm or reveal pain points. Rules:
- Don't ask about things you already know from the CRM (check the assessment)
- Questions should open a conversation, not interrogate
- Draw on activity type and software-specific knowledge where available — be specific, not generic
- At least one question should relate to operational process (how do they do X day-to-day)
- If software context exists, include 1–2 questions that naturally surface a specific gap without explicitly referencing the competitor

### 2. Rep tips (2–3 bullet points)
Short context the rep should know before reaching out:
- Timing or seasonality notes relevant to this account right now
- Contact context — who to reach, what they've said before, how the last interaction went
- How to frame the opening given their CRM history (warm re-engagement vs cold)
- Flag any risk (e.g. objection on record, sensitivity to approach)

### 3. Competitor context (1–2 sentences, or null)
If activity_type_context and software_context are both available, describe the specific overlap: what does this activity type specifically struggle with in their current software?

Be precise — not "Rezdy has limits" but "Rezdy's manifest fields are fixed, so scuba operators can't capture cert level or equipment size at booking — that all happens on the day, manually."

Only include competitor_context if both lenses are present and there is genuine, specific overlap. If either is empty, set to null.

---

Return this JSON:

{
  "discovery_questions": ["...", "...", "..."],
  "rep_tips": ["...", "..."],
  "competitor_context": "string or null"
}

Return valid JSON only. No markdown. No preamble. Start with { and end with }.
