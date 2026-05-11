## Stage 1 — Assess

You have been given a CRM lead and vertical context. Your only job here is to extract and organise what we know. Do not score, do not recommend, do not suggest actions yet.

---

### Lead data (from CRM)
{{lead_data}}

---

### Vertical context
{{vertical_context}}

---

### Vertical signals reference
{{vertical_signals}}

---

## Task

Carefully read the lead data. **CRM data is always the primary source.** Website signals are a supplementary check — useful when CRM data is thin, but never a substitute for what the rep has actually learned from the relationship.

### How to treat CRM data (primary)

CRM notes, call history, email threads, objections raised, deal context, and contact details are ground truth. Any signal that comes from an actual interaction with the prospect outweighs anything observed on their website.

Place CRM-derived signals in `key_signals`. These are the signals that will drive strategy and angle selection downstream.

### How to treat website signals (supplementary)

Website signals (`website_signals` in the lead data) are automated scrape observations — useful background context, not confirmed facts about the business's situation or intent.

- `detected_software`: booking software found on the site — note it, but do not treat it as definitive (plugins can be inactive or miscategorised)
- `has_direct_booking` / `no_booking_detected`: absence of a booking widget is an observation, not a confirmed pain point — the operator may take bookings by phone, via OTA, or through a channel not visible on the public site
- `ota_review_links`: OTA badges or listing links — confirms OTA presence, not booking software
- `fetch_error`: website could not be reached — note as a gap

**Website observations belong in `likely_pain_points` as assumptions** (labelled ASSUMPTION), not in `key_signals`. The only exception: if `detected_software` matches or conflicts with something already mentioned in the CRM — flag that conflict in `key_signals` as it is genuinely informative.

Cross-reference website signals against CRM data. If they conflict, flag it. If the CRM is silent and the website shows something notable, note it as a weak assumption only.

Extract facts, identify signals, and note gaps. Label anything that is an assumption rather than a stated fact.

Return this JSON structure:

{
  "company_summary": "2-3 sentence description of the business, their current situation, and where they are in the sales process",
  "deal_context": {
    "opportunity_value_usd": null,
    "days_since_last_activity": null,
    "current_software": null,
    "lead_status": null,
    "last_activity_summary": "one sentence describing what the last interaction was"
  },
  "key_signals": [
    "CRM-sourced signals only — things learned from actual interactions, notes, deal history, or confirmed facts about the account"
  ],
  "likely_pain_points": [
    "ASSUMPTION: pain point inferred from vertical knowledge, CRM signals, or website observations — label all assumptions and note the source (e.g. 'ASSUMPTION (website): no booking widget visible on site')"
  ],
  "contacts": [
    {
      "name": null,
      "title": null,
      "email": null,
      "phone": null,
      "dnc": false,
      "notes": "relevant context about this contact from CRM notes — tone, history, preferences"
    }
  ],
  "known_facts": [
    "facts explicitly stated in the CRM — not inferences"
  ],
  "gaps": [
    "important things we do not know that would help — e.g. 'No decision maker confirmed'"
  ]
}
