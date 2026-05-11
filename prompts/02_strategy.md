## Stage 2 — Strategy

You have an assessment of a CRM lead. Your job is to score the lead and select the right sales strategy.

---

### Assessment (from Stage 1)
{{assessment}}

---

## Task

Score the lead and select a strategy. Be honest — if the evidence is weak, score it low. Use the structured CRM fields from the assessment to anchor your scoring — do not ignore pre-assessed data from the sales team.

---

### Scoring rules

**Priority:**
- high — clear pain, decision maker identified or reachable, deal size justifies effort. Tier 1–2 accounts, high review counts with weak direct booking setup, or active CRM conversations.
- medium — some pain signals, unclear urgency or stakeholder access. Tier 3 accounts or thin CRM data with reasonable vertical fit.
- low — weak signals, poor fit, or significant blockers (DNC, stale, wrong contact). Tier 4–5 with no clear pain.

When `lead_qualification` or `fit` is present in the deal_context, weight it heavily:
- If `fit` is "Poor" or `lead_qualification` is "Unqualified" → default to low priority unless there is strong overriding evidence.
- If `fit` is "Good" or `lead_qualification` is "Qualified" → start at medium and adjust up based on other signals.

**Urgency:**
- high — active conversation, event-driven trigger, competitor pressure visible, or the account is a former client with a known churn reason that can be addressed
- medium — some recent activity or a soft buying signal
- low — no recent engagement, no clear trigger

**Confidence:**
- high — multiple corroborating signals, clear pain, known contact, high review counts with no direct booking = quantifiable gap
- medium — one or two signals, some gaps
- low — thin CRM data, mostly assumptions, no rep notes, no structured CRM data

**Deal size:**
- Use `predicted_opp_value` from deal_context if present — this is the most reliable input.
- If absent, use `tier` as a proxy: tier 1–2 → large; tier 3 → mid; tier 4–5 → small.
- If neither is available, reason from review counts, organic traffic, and activity type.

---

### Strategy routing rules

- **Challenger** → priority is high or medium-high, confidence is medium or high, deal size justifies a bold approach. Best when: operator has high TripAdvisor/Google reviews but weak direct booking, is on a known competitor (Rezdy, Checkfront), or has visible OTA dependency. The insight to challenge with is always the delta between their reputation/traffic and what they're capturing directly.
- **Discovery** → confidence is low, first meaningful contact, CRM data is thin, or fit/qualification is unclear. Use when we need to learn more before pitching. Also use when the activity type is ambiguous — do not make claims you cannot back with evidence.
- **Mid-Market** → multiple contacts or stakeholders present, deal size is mid-range (tier 3 or predicted_opp_value in mid range), decision involves more than one person. Use when ROI justification and proof points will matter more than a single reframe.

---

Return this JSON structure:

```json
{
  "priority": "high | medium | low",
  "urgency": "high | medium | low",
  "confidence": "high | medium | low",
  "deal_size": "small | mid | large",
  "selected_strategy": "challenger | discovery | mid_market",
  "strategy_reasoning": "2-3 sentences explaining why this strategy fits this lead right now, referencing specific signals from the assessment (review counts, tier, current software, qualification status, etc.)",
  "risk_flags": [
    "anything that could derail outreach — DNC contacts, poor fit score, unqualified status, stale account, churn history that is unresolved, etc."
  ]
}
```

Return valid JSON only. No markdown. No preamble. Start with { and end with }.
