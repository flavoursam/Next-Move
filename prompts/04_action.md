## Stage 4 — Action

You have an assessment, a strategy, and a sales angle. Your job is to decide the best way to reach this prospect — which channel, which contact, and why.

---

### Assessment (from Stage 1)
{{assessment}}

---

### Strategy result (from Stage 2)
{{strategy_result}}

---

### Angle result (from Stage 3)
{{angle_result}}

---

## Task

Select the right channel and identify the right contact. One action only — not a sequence, not options.

### Channel selection rules

- email → the angle needs a sentence or two of explanation, or the contact is not easily reached by phone
- cold_call → urgency is high, decision maker has a phone number, or the angle benefits from a live conversation
- voicemail → cold_call is right but decision maker is unlikely to pick up (inferred from CRM history or contact type)
- linkedin → no direct contact details, or the contact needs to be identified before outreach

### Contact selection rules

- Always pick ONE contact — the most relevant, most reachable person
- If a contact has dnc: true, do not select them under any circumstances
- If no safe contact exists, set recommended_action to "research" and explain why

Return this JSON structure:

{
  "recommended_action": "email | cold_call | voicemail | linkedin | research",
  "contact_name": "full name of the contact to reach",
  "contact_email": "email address or null",
  "contact_phone": "phone number or null",
  "reasoning": "why this channel and this contact — reference specific signals",
  "fallback_action": "what to do if this contact does not respond within 5 business days"
}
