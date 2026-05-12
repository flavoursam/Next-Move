# NextMove Memory Guide

A reference for understanding and managing the account memory system. Keep this up to date as the system evolves.

---

## What is account memory?

Every account in NextMove has a persistent memory document — a structured JSON file that accumulates what the system knows about the account over time. The memory system builds an evolving picture of each account, updated every hour from Close activity.

Memory is created once when you add the account, then updated incrementally every hour as new signals arrive from Close.

---

## What's in the memory document?

| Field | What it captures |
|---|---|
| `summary` | 1–2 sentence plain English description of where the account stands |
| `pain_points[]` | Specific pain points identified, each with confidence and date tracking |
| `objections[]` | Objections raised by the prospect, whether resolved, and context |
| `engagement_history` | Last contact attempt, last response, response rate, preferred channel, total touchpoints |
| `org_intelligence` | Decision maker name/title/email/phone, other contacts, org changes |
| `buying_readiness` | Score (0–1), level (cold/warm/hot/not_a_fit), signals for and against |
| `account_context` | Current booking software, website, location, CRM opportunity value |
| `vertical_signals` | Seasonality notes, operational pressures, industry context |
| `memory_version` | Increments on every update — how many times memory has been updated |
| `last_updated` | Date of most recent update |

### Pain point confidence levels

Each pain point carries:
- `confidence`: **high** / **medium** / **low** — how certain we are this is a real pain
- `first_noted`: when first identified
- `last_confirmed`: when last confirmed by a new signal

Confidence goes UP when new CRM signals confirm a point. It decays DOWN automatically over time — see Confidence Decay below.

### Pain point source attribution

Each pain point also carries a `source_signal_id` — the ID of the specific Close activity (call note, email, CRM note) that created or last confirmed it. This is the receipt behind every claim in memory.

**Example — without source attribution:**
```json
{
  "point": "Losing 30% of bookings to Booking.com commission",
  "confidence": "high",
  "source": "crm_conversation",
  "last_confirmed": "2026-04-10"
}
```
You can see it's high confidence but can't verify *which* conversation established it.

**With source attribution:**
```json
{
  "point": "Losing 30% of bookings to Booking.com commission",
  "confidence": "high",
  "source": "crm_conversation",
  "source_signal_id": 47,
  "last_confirmed": "2026-04-10"
}
```
Signal ID 47 is a row in the `signals` table. That row holds the full raw Close activity — the actual call note or email Claude read when it created this pain point. You can look it up and show the source.

**Why this matters:**
- A colleague asks "how do you know they care about OTA commission?" → look up signal 47, pull the Close activity, show the call note where the operator said it
- A high-confidence pain point feels wrong → trace it to the signal and see if Claude over-interpreted something weak
- Expanding to new teams or verticals → people can audit why the system recommends a particular angle. Trust comes from traceability, not "the AI said so"
- If `source_signal_id` is **null**: the pain point came from the initial Stage 1 assessment (CRM data at account creation), before the signal ingestion loop started. That's expected and fine.

---

## How memory is created and updated

### Init (one time per account)
When you add an account:
1. Fetches the lead from Close (including website scrape)
2. Runs Stage 1 assessment
3. Claude Opus builds the initial memory document from the assessment
4. First action recommendation is generated

### Updates (every hour, automatically)
The background scheduler runs every hour. For each active account it:
1. Polls Close for new activity since the last check (calls, emails, notes)
2. If new signals exist → Claude Opus merges them into the memory document
3. New action recommendation generated from updated memory
4. Previous pending action expired

### Manual refresh
Click **"Refresh Signals"** on the account page to trigger the cycle immediately, outside the hourly schedule. This also re-scrapes the company website to catch booking software changes.

---

## What causes memory drift?

Memory drift is when the memory document diverges from reality.

### 1. Poor CRM hygiene (biggest risk)
If reps make calls or send emails outside of Close without logging them, those interactions never become signals. Memory doesn't update. Confidence stays stale.

**Rule:** CRM accuracy = signal quality = memory accuracy. If it's not in Close, the memory doesn't know it happened.

### 2. Time passing without contact
Even with perfect CRM hygiene, pain points identified months ago may no longer be accurate. The prospect may have changed situation, signed with a competitor, or the contact may have left.

**Mitigation:** Confidence decay automatically reduces confidence on old unconfirmed pain points (see below).

### 3. Website not re-scraped
The website is only scraped at account init and on manual refresh. If an operator switches booking software between refreshes, the memory won't reflect this until the next manual refresh.

---

## Confidence decay

Pain point confidence decays automatically when no new signals confirm the point:

| Days since `last_confirmed` | Effect |
|---|---|
| 0–27 days | No change |
| 28–55 days | high → medium |
| 56+ days | medium → low (or high → low if not already decayed) |

- Confidence never decays below **low** automatically.
- When a new signal confirms a pain point, `last_confirmed` resets to today and confidence can increase.
- `buying_readiness` also decays: if all `signals_for` entries are >56 days old with no new confirming signal, score drops by 0.1 and the level may step down.

**To change the decay thresholds:** Open `prompts/memory_update.md` and find the numbers `28` and `56` in rule 9. Update both.

---

## Website signals

`pipeline/website.py` scrapes the company website and detects:

| Signal | What it means |
|---|---|
| **Booking software** | Embedded reservation system (Rezdy, FareHarbor, Checkfront, Bokun, etc.) — strong talking point |
| **OTA review links** | Viator, GetYourGuide, Klook, etc. — review badges only, NOT booking software |
| **Book Now CTA** | "Book Now" / "Reserve Now" / "Check Availability" button present |
| **No booking detected** | No booking system or CTA — high relevance if they should have one |

Website signals are especially valuable when CRM data is thin — they provide grounding facts even with no call notes or emails on record.

### Where to edit
| Change | File | Lines |
|---|---|---|
| Add booking software | `pipeline/website.py` | 15–25 (`BOOKING_SOFTWARE` dict) |
| Add OTA platforms | `pipeline/website.py` | 29–35 (`OTA_REVIEW_LINKS` dict) |
| Add booking phrases | `pipeline/website.py` | 37–41 (`BOOK_NOW_PHRASES` list) |

---

## Email signal quality

When Close emails are ingested as signals, each email body is read up to **1,500 characters** (≈250 words). This covers most outreach and reply emails.

- The 1500-character limit lives at `pipeline/crm.py:292`. Increase it if you need to capture longer threads, noting that higher values increase Claude token cost per memory update.
- Call notes are read up to 500 characters (`pipeline/crm.py:258`).
- CRM text notes are read up to 500 characters (`pipeline/crm.py:275`).
- The **outgoing email draft** limit (150 words) is in `prompts/05_draft.md` — this is separate and unrelated.

---

## Stateful vs fresh pipeline

On each account page you have two options:

**Memory-based (stateful):** Uses the accumulated account memory. Fast, context-aware, incorporates everything ever learned. This is the default recommendation.

**Fresh pipeline:** Runs all 6 pipeline stages against current Close data, ignoring the memory document entirely. Slower (5 Claude API calls), but useful when you suspect memory is stale or want an independent second opinion. The fresh result appears as a purple card alongside the memory-based recommendation.

**Important:** Fresh pipeline results do NOT update account memory even if approved. Memory only updates through signal ingestion. The fresh pipeline is a read-only view of what the pipeline would say today.

---

## Warning signs that memory is stale

| Signal | What it suggests |
|---|---|
| `memory_version` = 1 | Memory was never updated after init — no new Close signals have arrived |
| `last_updated` > 2 weeks ago | Scheduler may not be running, or no activity logged in Close |
| All pain point confidence = "low" | Decay has run; CRM hygiene issue or pain points were never confirmed |
| `last_contact_attempt` = null | No outreach has been approved yet |
| `total_touchpoints` = 0 | Same as above — nothing sent |

---

## The full loop

```
1. Account added
   → Init memory from Close + website scrape
   → First action recommendation generated

2. Rep reviews action on /accounts/{id}
   → Sees memory-based recommendation (left)
   → Optionally runs fresh pipeline for comparison (right)
   → Approves → draft created in Close
   → Memory immediately records outreach (last_contact_attempt updated, touchpoints +1)

3. Background scheduler (every hour)
   → Polls Close for new signals
   → If signals: update memory (decay also applied here)
   → Generate new action from updated memory

4. Confidence decay (inside every memory update)
   → 28 days unconfirmed: high → medium
   → 56 days unconfirmed: medium → low

5. Manual refresh (rep-triggered)
   → Same as step 3, plus website re-scrape
   → Useful when you know something changed in Close

6. Rep can always override
   → Manual refresh: trigger update now
   → Fresh pipeline: ignore memory, re-run from scratch
```
