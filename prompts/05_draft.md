## Stage 5 — Draft

You have everything you need. Your job is to write the actual outreach asset — the real email, call script, or voicemail — ready for the rep to use.

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

### Action result (from Stage 4)
{{action_result}}

---

### Strategy instructions
{{strategy_instructions}}

---

### Sales rep context
{{rep_context}}

---

## Task

Write the outreach asset for the recommended action. For call scripts and voicemails, use the rep's name and company when introducing themselves. For emails, do not include a sign-off or signature block — end after the call to action.

### Drafting rules (all asset types)

- Lead with the single pain point from the angle — nothing else
- Reference a specific fact from the CRM or assessment — make it clear you know this company
- Write in first person as the rep — short sentences, human tone, no corporate language
- Do not stack multiple benefits or propositions
- Do not include statistics unless they appear in the CRM data
- Do not mention competitors by name unless the CRM explicitly references them

### Email rules
- Subject: specific and curiosity-driven — not a question, not a generic opener
- Body: under 150 words
- One call to action — a reply, not a meeting request on first cold touch
- No sign-off or signature block — stop after the call to action

### Cold call script rules
- Opening (first 15 seconds): one sentence hook — what you noticed, why you're calling
- Script body: 60–90 seconds max — pain point, one insight, ask for a conversation
- Natural pauses marked with [pause] where the prospect might respond
- Written to sound like a real conversation, not a pitch

### Voicemail rules
- 20–25 seconds when spoken aloud (roughly 60–70 words)
- Name, company, one specific reason for the call, call to action (call back or email)
- No pitch, no product name unless highly relevant
- End with phone number spoken clearly

### LinkedIn rules
- Under 300 characters for connection request
- Reference something specific — their role, company, or a mutual context
- No pitch in the connection request — save it for after they accept

---

Return this JSON structure. Populate only the fields relevant to the recommended action. Set others to null.

{
  "summary": "2-3 sentence plain-English summary of the situation and recommended action — for the rep to read before acting",
  "why_now": "one sentence on why this is the right moment to reach out",
  "email": {
    "subject": null,
    "body": null
  },
  "call": {
    "opening": null,
    "script": null,
    "voicemail": null
  },
  "linkedin": {
    "message": null
  },
  "rep_notes": [
    "bullet point context the rep should know before acting — tone history, objections, sensitivities"
  ]
}
