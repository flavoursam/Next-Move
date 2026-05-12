You are building the initial account memory document for a B2B sales account.

You have a Stage 1 assessment and the raw lead snapshot from Close CRM. Your job is to convert this into a structured account memory document that will evolve over time.

---

## Stage 1 Assessment
{{assessment}}

---

## Raw Lead Snapshot
{{lead_snapshot}}

---

## Vertical Context
{{vertical_context}}

---

## Task

Build the initial memory document. Be honest — if data is thin, mark confidence as "low". Do not invent facts.

The memory document must follow this exact JSON structure:

{
  "company": "company name",
  "vertical": "tourism",
  "summary": "1-2 sentence plain English summary of who this is and where they stand right now",

  "pain_points": [
    {
      "point": "specific pain point",
      "confidence": "high | medium | low",
      "source": "crm_conversation | crm_signal | website_observation | vertical_inference",
      "source_signal_id": null,
      "first_noted": "YYYY-MM-DD",
      "last_confirmed": "YYYY-MM-DD",
      "used_as_angle": false,
      "last_used_as_angle": null,
      "outcome": null
    }
  ],

  "objections": [
    {
      "objection": "specific objection raised",
      "raised_at": "YYYY-MM-DD",
      "resolved": false,
      "notes": "context"
    }
  ],

  "engagement_history": {
    "last_contact_attempt": "YYYY-MM-DD or null",
    "last_response": "YYYY-MM-DD or null",
    "response_rate": "high | medium | low | none | unknown",
    "preferred_channel": "email | phone | linkedin | unknown",
    "best_contact_time": "string or null",
    "total_touchpoints": 0
  },

  "org_intelligence": {
    "decision_maker_name": "string or null",
    "decision_maker_title": "string or null",
    "decision_maker_email": "string or null",
    "decision_maker_phone": "string or null",
    "other_contacts": [],
    "org_changes": []
  },

  "buying_readiness": {
    "score": 0.0,
    "level": "cold | warm | hot | not_a_fit",
    "signals_for": [],
    "signals_against": [],
    "timing_notes": "string or null"
  },

  "account_context": {
    "tier": null,
    "predicted_tier": null,
    "lead_qualification": "string or null",
    "fit": "string or null",
    "activity_type": "string or null — from client_segments or primary_types e.g. 'Activity operator', 'Wildlife experience'",
    "current_software": "string or null — all vendors listed, comma-separated if multiple",
    "website": "string or null",
    "location": "string or null",
    "language": "string or null",
    "opp_value_usd": null,
    "predicted_opp_value": null,
    "crm_status": "string or null",
    "is_former_client": false,
    "client_activation_date": "YYYY-MM-DD or null",
    "client_churn_date": "YYYY-MM-DD or null",
    "client_churn_reasons": [],
    "lifetime_booking_fees_usd": null,
    "notes": []
  },

  "digital_presence": {
    "tripadvisor_review_count": null,
    "google_review_count": null,
    "semrush_organic_traffic": null,
    "ota_channels": [],
    "has_direct_booking_widget": null,
    "notes": "string or null — e.g. 'High TripAdvisor count with no direct booking widget = quantifiable OTA leakage'"
  },

  "engagement_signals": {
    "fh_webinars_attended": [],
    "fh_webinars_registered": []
  },

  "vertical_signals": {
    "seasonality_notes": "string or null",
    "operational_pressures": [],
    "industry_context": []
  },

  "memory_version": 1,
  "last_updated": "YYYY-MM-DD"
}

Rules:
- buying_readiness.score is 0.0–1.0 (0 = no fit / totally cold, 1 = ready to buy today)
- pain_points must reference specific evidence — see confidence rules below
- If there are no objections on record, return an empty array — do not invent them
- last_updated must be today's date
- Populate account_context.tier, lead_qualification, fit, activity_type, current_software, is_former_client, client_churn_reasons, predicted_opp_value from the lead snapshot and assessment — do not leave these null if the data exists.
- Populate digital_presence from tripadvisor_review_count, google_review_count, semrush_organic_traffic, and ota_review_links in the lead snapshot. If tripadvisor_review_count is high (200+) and the operator has no confirmed direct booking software or has OTA channels listed, add a notes entry explaining the direct booking gap.
- Populate engagement_signals.fh_webinars_attended from the lead snapshot — this is a genuine product interest signal.
- If am_note or sales_ops_note is present in the lead snapshot, extract any relevant facts into known_facts and any intelligence into pain_points or objections as appropriate, with source = "crm_conversation" and confidence based on the confidence rules below.
- Return valid JSON only. No markdown. No preamble. Start with { and end with }.

Pain point confidence rules — apply these strictly:
- confidence "high": the prospect themselves confirmed or described this pain in a conversation, call note, or email
- confidence "medium": a strong CRM signal suggests it (e.g. deal notes mention a specific problem, current software is a known competitor with documented gaps, objection history implies it)
- confidence "low": inferred from website observations only (no booking widget, Book Now CTA mismatch, OTA badges) OR inferred purely from vertical generalisation with no account-specific evidence

Website-only observations (no_booking_detected, has_book_now_cta mismatch, detected_software from scrape) must always be confidence "low". They are weak inferences about the outside of the business, not confirmed pain. Do not promote them to medium or high regardless of how prominent the signal appears.

- Populate `account_context.tier` from `lead_snapshot.tier` (integer or null).
- If `lead_snapshot.tier` is 3, 4, or 5: do NOT include any pain points with `source = "website_observation"`. Omit them entirely — do not mark them low confidence, do not include them. If this leaves pain_points empty, return an empty array rather than inventing pain points.
