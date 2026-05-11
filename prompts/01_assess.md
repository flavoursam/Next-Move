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

---

## Reading the structured CRM fields

The lead data contains structured fields populated directly from Close CRM. Read and interpret each one that is present:

**Account classification:**
- `tier` — FareHarbor's internal account tier (1 = highest value / most strategic, 5 = smallest). Tier 1–2 accounts are enterprise relationships; tier 3–4 are mid-market; tier 5 are small operators. If tier is null, it has not been assessed yet.
- `predicted_tier` — BI model estimate of where this account should tier. If lower than current tier, it may be declining.
- `lead_qualification` — sales team's qualification verdict (e.g. Qualified, Unqualified, In Progress). Pull this into deal_context directly.
- `fit` — sales team's fit assessment for FareHarbor. A poor fit score is a risk flag.
- `lead_type` / `client_segments` / `primary_types` — the type of operator this is (e.g. activity, accommodation, attraction, tour). Use this to contextualise pain points and seasonality.

**Current software:**
- `current_software` — the booking platform(s) they currently use, confirmed from CRM records. This is one of the most important fields. If it lists Rezdy, Checkfront, Bookeo, or Bokun, note it prominently as a direct competitor signal. Multiple vendors may be listed — list all of them.

**Online presence and reputation (critical for tourism):**
- `tripadvisor_review_count` — number of TripAdvisor reviews. A high count (200+) with a strong rating indicates established demand and significant organic traffic — this operator is likely undermonetising their direct booking channel. Cross-reference against whether they have direct booking software.
- `google_review_count` — number of Google reviews. High count suggests walk-in and local traffic. Compare against TripAdvisor count to understand channel mix.
- `semrush_organic_traffic` — estimated monthly organic search visitors (from Semrush). High organic traffic combined with no direct booking widget = a strong, quantifiable direct booking gap. Include the actual number in your assessment.

**Note: OTA ranking** is not a structured CRM field — look for it in CRM notes, call logs, or website signals (`ota_review_links`). If you see Viator, GetYourGuide, or TripAdvisor booking links in website_signals, flag the operator's OTA dependency explicitly.

**Opportunity and revenue signals:**
- `predicted_opp_value` — model estimate of the deal value. Note this in deal_context.
- `lifetime_booking_fees` — total booking fees this account has generated if they are or were a client. Relevant for winback conversations.
- `opportunities` — active deal records in Close. Pull value and status.

**Human intelligence notes (read these carefully — they contain rep knowledge):**
- `am_note` — account manager's notes. Free text written by a human who knows this account. Treat as high-signal intelligence. Extract any relevant facts, objections, history, or context into key_signals.
- `sales_ops_note` — sales ops notes. May contain qualification context, routing decisions, or flags.

**Client lifecycle:**
- `client_activation_date` — if set, this was a client. Note this — winback conversations are different from new logo outreach.
- `client_churn_date` + `client_churn_reasons` — why they left. Critical context for re-engagement. List the specific churn reasons if present.

**Engagement signals:**
- `sales_latest_call` — date of the most recent logged call. Compare against `days_since_activity` to understand recency.
- `fh_webinars_attended` — FareHarbor webinars this contact has attended. Signals genuine product interest beyond just a CRM conversation.

---

## How to treat CRM notes and activity (primary)

CRM notes, call history, email threads, objections raised, deal context, and contact details are ground truth. Any signal that comes from an actual interaction with the prospect outweighs anything observed on their website.

Place CRM-derived signals in `key_signals`. These are the signals that will drive strategy and angle selection downstream.

---

## How to treat website signals (supplementary)

Website signals (`website_signals` in the lead data) are automated scrape observations — useful background context, not confirmed facts.

- `detected_software`: booking software found on the site — note it, but do not treat it as definitive (plugins can be inactive or miscategorised). Cross-reference against `current_software` from CRM — if they conflict, flag it.
- `has_direct_booking` / `no_booking_detected`: absence of a booking widget is an observation, not a confirmed pain point
- `ota_review_links`: OTA badges or listing links — confirms OTA presence; note which OTAs
- `fetch_error`: website could not be reached — note as a gap

**Website observations belong in `likely_pain_points` as assumptions** (labelled ASSUMPTION), not in `key_signals`. Exception: if `detected_software` conflicts with `current_software` from CRM — flag that in `key_signals`.

---

## Output format

Return this JSON structure:

```json
{
  "company_summary": "2-3 sentence description of the business, their current situation, and where they are in the sales process. Include their operator type, location, and one key distinguishing fact.",
  "operator_type": "one of: scuba_diving | helicopter | general_admission | boat_tour | walking_tour | wildlife | multi_day | null — infer from primary_types, client_segments, lead_type, and company_summary. Use null if the operator type is unclear or does not match any of the known types.",
  "deal_context": {
    "opportunity_value_usd": null,
    "predicted_opp_value": null,
    "days_since_last_activity": null,
    "current_software": null,
    "lead_status": null,
    "lead_qualification": null,
    "fit": null,
    "tier": null,
    "tripadvisor_review_count": null,
    "google_review_count": null,
    "semrush_organic_traffic": null,
    "is_former_client": false,
    "client_churn_reasons": [],
    "last_activity_summary": "one sentence describing what the last interaction was"
  },
  "key_signals": [
    "CRM-sourced signals only — things learned from actual interactions, notes, deal history, confirmed software, review counts, rep notes, or confirmed facts. Include review counts with their actual numbers. Include current software vendor(s). Include am_note and sales_ops_note content verbatim if present."
  ],
  "likely_pain_points": [
    "ASSUMPTION: pain point inferred from vertical knowledge, CRM signals, or website observations — label all assumptions and note the source (e.g. 'ASSUMPTION (website): no booking widget visible on site', 'ASSUMPTION (vertical): high TripAdvisor review count suggests significant OTA commission leakage')"
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
    "facts explicitly stated in the CRM or structured fields — not inferences. Include: current software, tier, review counts, organic traffic, webinars attended, churn reasons if present."
  ],
  "gaps": [
    "important things we do not know that would help — e.g. 'No decision maker confirmed', 'TripAdvisor rating not in CRM (only count)', 'OTA commission rate unknown'"
  ]
}
```

Return valid JSON only. No markdown. No preamble. Start with { and end with }.
