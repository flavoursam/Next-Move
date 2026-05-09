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

Carefully read the lead data, **including `website_signals`**. The `website_signals` field contains live data scraped directly from the company's website — treat this as ground truth, not an assumption.

Key website signals to factor in:
- `detected_software`: booking software actively embedded on their site (e.g. Rezdy, Checkfront) — this is a confirmed fact, not a CRM assumption
- `has_direct_booking`: whether a booking widget is present — if False and `has_book_now_cta` is also False, the business may be taking bookings offline or via phone only
- `no_booking_detected`: a strong signal — if True, the prospect has no online booking capability at all, which is a major pain point
- `ota_review_links`: OTA platforms linked from their site (Viator, GetYourGuide, etc.) — these are review badges or listing links only, **not booking software**. Do not treat them as evidence of a booking system. They do confirm OTA presence/dependency.
- `fetch_error`: if set, the website could not be reached — note this as a gap

Cross-reference website signals against CRM data. If they conflict (e.g. CRM says "uses Rezdy" but website shows FareHarbor), flag it.

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
    "specific, real signals from the CRM data relevant to this vertical — e.g. 'Uses Rezdy, no direct booking channel visible on website'"
  ],
  "likely_pain_points": [
    "ASSUMPTION: pain point inferred from vertical knowledge and signals — label all assumptions"
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
