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

9. CONFIDENCE DECAY: For each pain_point, check the gap between last_confirmed and today's date (the value of last_updated you are about to write).
   - If gap > 28 days AND no signal in this update directly confirms the pain point: reduce confidence one level (high → medium, medium → low).
   - If gap > 56 days AND no signal confirms it: apply the reduction again if it hasn't already decayed (after 56 days unconfirmed, a high becomes low; a medium becomes low).
   - Never reduce below "low" automatically.
   - If a new signal in this update confirms a pain point: set last_confirmed to today and you may increase confidence if the evidence warrants it — this resets the decay clock.
   - Apply similar decay to buying_readiness: if all entries in signals_for are older than 56 days and no new confirming signal exists in this update, reduce score by 0.1 (floor 0.0) and step the level down if the new score falls below thresholds (hot: ≥ 0.7, warm: 0.4–0.69, cold: < 0.4).
   - To change the decay thresholds, edit the numbers 28 and 56 in this rule.

10. OUTREACH SIGNAL: If any signal has type "outreach_sent" (source: "nextmove"), the rep just approved and sent outreach to this account. Update engagement_history.last_contact_attempt to the signal's date and increment total_touchpoints by 1. This is NOT a response — do not update last_response or change buying_readiness on this signal alone.

Return the full updated memory document in the same JSON structure as the input.
Return valid JSON only. No markdown. No preamble. Start with { and end with }.
