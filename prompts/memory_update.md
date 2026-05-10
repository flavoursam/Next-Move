You are updating an account memory document based on new signals from the CRM.

Your job is to MERGE new information into the existing memory — not replace it.
If a new signal contradicts existing memory, update the relevant field and note the change.
If a new signal adds nuance, enrich the existing field.
If a new signal confirms existing knowledge, increase confidence where appropriate.
Never remove information unless it is directly contradicted by new evidence.

---

## Current Account Memory
{{current_memory}}

---

## New Signals
{{new_signals}}

---

## Vertical Context (for interpreting signals correctly)
{{vertical_context}}

---

## Task

Update the memory document to reflect what we now know. Follow these rules:

1. MERGE, don't replace. Preserve existing knowledge.
2. Update confidence levels upward when new signals confirm existing beliefs.
3. Add new pain points, objections, org changes, or engagement signals as discovered.
4. Update engagement_history with the latest contact dates and response signals.
5. Update buying_readiness.score and level based on the direction signals point.
6. Note any timing signals in buying_readiness.timing_notes.
7. Increment memory_version by 1.
8. Set last_updated to today's date.

Return the full updated memory document in the same JSON structure as the input.
Return valid JSON only. No markdown. No preamble. Start with { and end with }.
