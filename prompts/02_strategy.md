## Stage 2 — Strategy

You have an assessment of a CRM lead. Your job is to score the lead and select the right sales strategy.

---

### Assessment (from Stage 1)
{{assessment}}

---

## Task

Score the lead and select a strategy. Be honest — if the evidence is weak, score it low.

### Scoring rules

**Priority:**
- high — clear pain, decision maker identified or reachable, deal size justifies effort
- medium — some pain signals, unclear urgency or stakeholder access
- low — weak signals, poor fit, or significant blockers (DNC, stale, wrong contact)

**Urgency:**
- high — active conversation, event-driven trigger, or competitor pressure visible
- medium — some recent activity or a soft buying signal
- low — no recent engagement, no clear trigger

**Confidence:**
- high — multiple corroborating signals, clear pain, known contact
- medium — one or two signals, some gaps
- low — thin CRM data, mostly assumptions

### Strategy routing rules

- Challenger → priority is high or medium-high, confidence is medium or high, deal size justifies a bold approach. Use when the prospect needs their thinking reframed.
- Discovery → confidence is low, first meaningful contact, or CRM data is too thin to make a strong claim. Use when we need to learn more before pitching.
- Mid-Market → multiple contacts or stakeholders present, deal size is mid-range, decision involves more than one person. Use when ROI justification and proof points will matter.

Return this JSON structure:

{
  "priority": "high | medium | low",
  "urgency": "high | medium | low",
  "confidence": "high | medium | low",
  "deal_size": "small | mid | large",
  "selected_strategy": "challenger | discovery | mid_market",
  "strategy_reasoning": "2-3 sentences explaining why this strategy fits this lead right now",
  "risk_flags": [
    "anything that could derail outreach — DNC contacts, bouncing emails, unclear status, etc."
  ]
}
