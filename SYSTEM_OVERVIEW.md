# NextMove — System Overview

## What it does

NextMove is an AI-powered sales sequencing tool for B2B reps. It connects to a Close CRM lead, runs it through a 5-stage AI reasoning pipeline, and returns a single recommended next action with a ready-to-use outreach asset (email, call script, or voicemail). The rep reviews and approves each touchpoint before anything is sent. Drafts are created directly in Close.

Between touchpoints, NextMove monitors the CRM for meaningful activity and pauses the sequence automatically if a real conversation has occurred — so the rep always acts on current information, not a stale plan.

---

## Architecture map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                              │
│                                                                             │
│   ┌──────────────────┐              ┌──────────────────────────────────┐   │
│   │   Close.io CRM   │              │         Claude API (Anthropic)   │   │
│   │                  │              │                                  │   │
│   │  - Lead data     │              │  - claude-sonnet-4-6 (default)  │   │
│   │  - Activities    │              │  - claude-haiku-4-5 (testing)   │   │
│   │  - Email drafts  │              │  - 5 calls per pipeline run      │   │
│   │  - CRM notes     │              │  - 1 call per gate check         │   │
│   └────────┬─────────┘              └──────────────┬───────────────────┘   │
│            │  REST API                             │  Python SDK           │
└────────────│───────────────────────────────────────│─────────────────────-─┘
             │                                       │
┌────────────▼───────────────────────────────────────▼──────────────────────┐
│                            NEXTMOVE APPLICATION                            │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  app.py  —  FastAPI web server                                       │ │
│  │                                                                      │ │
│  │  Routes:                                                             │ │
│  │    GET  /              Dashboard (all sequences)                     │ │
│  │    GET  /sequence/new  New sequence form                             │ │
│  │    POST /sequence/new  Start pipeline (background task)              │ │
│  │    GET  /sequence/{id} Sequence detail + touchpoint review           │ │
│  │    POST /sequence/{id}/approve/{tp}  Approve → draft in Close       │ │
│  │    POST /sequence/{id}/reject/{tp}   Reject + cancel sequence        │ │
│  │    POST /sequence/{id}/next          Generate next touchpoint        │ │
│  │    GET  /commission    Commission dashboard                           │ │
│  │    GET  /admin         Admin stats (direct URL only)                 │ │
│  │    GET  /identity      Identity picker (cookie-based auth)           │ │
│  └─────────┬───────────────────────┬────────────────────────────────┬──┘ │
│            │                       │                                │    │
│  ┌─────────▼──────┐   ┌────────────▼──────────┐   ┌───────────────▼──┐  │
│  │   pipeline/    │   │    scheduler.py        │   │  templates/      │  │
│  │                │   │                        │   │                  │  │
│  │  crm.py        │   │  APScheduler           │   │  Jinja2 HTML     │  │
│  │  website.py    │   │  Runs every 12 hours   │   │  served by       │  │
│  │  stages.py     │   │  for active sequences: │   │  FastAPI         │  │
│  │  gate.py       │   │  - gate classifier     │   │                  │  │
│  │  close_write.py│   │  - demo detection      │   │  static/         │  │
│  │                │   │  - commission events   │   │  style.css       │  │
│  └─────────┬──────┘   └────────────┬──────────┘   └──────────────────┘  │
│            │                       │                                      │
│  ┌─────────▼───────────────────────▼───────────────────────────────────┐ │
│  │   db.py  —  SQLite (nextmove.db)                                    │ │
│  │                                                                     │ │
│  │   users              identity (name + cookie, no passwords)         │ │
│  │   sequences          one per lead — status, vertical, opp value     │ │
│  │   touchpoints        each pipeline run — all 5 stage outputs stored │ │
│  │   gate_verdicts      continue / warn_continue / pause + reason      │ │
│  │   commission_events  demo detected → 10% of opp value               │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │   prompts/         Claude instructions for each stage               │  │
│  │   strategies/      Challenger, Discovery, Mid-Market playbooks      │  │
│  │   verticals/       Industry context + structured signals per sector │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow diagrams

### 1. Starting a new sequence

```
AE opens /sequence/new
          │
          ▼
    Enter Close lead ID
          │
          ▼
    POST /sequence/new
          │
          ├── DB: create sequence record (status = "generating")
          │
          ├── Redirect AE to /sequence/{id}  ← shows loading spinner
          │
          └── Background task starts:
                    │
                    ▼
              pipeline/crm.py
              ├── Fetch lead from Close API
              └── Scrape website (pipeline/website.py)
                  ├── Detect booking software (Rezdy, Checkfront, etc.)
                  ├── Detect OTA review links
                  └── Detect "Book Now" CTA presence
                    │
                    ▼
              pipeline/stages.py  (5 Claude API calls)
              │
              ├── Stage 1 — Assess
              │   In:  lead data + website signals + vertical context
              │   Out: company summary, signals, contacts, gaps
              │
              ├── Stage 2 — Strategy
              │   In:  Stage 1 output
              │   Out: priority, confidence, selected strategy
              │         (Challenger / Discovery / Mid-Market)
              │
              ├── Stage 3 — Angle
              │   In:  Stages 1–2 + strategy playbook
              │   Out: one pain point, one angle, why now
              │         (website mismatch used as talking point if strong)
              │
              ├── Stage 4 — Action
              │   In:  Stages 1–3
              │   Out: channel (email/call/voicemail/linkedin), contact
              │
              └── Stage 5 — Draft
                  In:  Stages 1–4 + strategy playbook + rep context
                  Out: ready-to-use outreach asset + rep notes
                    │
                    ▼
              DB: store touchpoint (all 5 stage outputs as JSON)
              DB: update sequence status → "pending"
                    │
                    ▼
              Page auto-refreshes → AE sees Touchpoint 1 draft
```

---

### 2. Reviewing and approving a touchpoint

```
AE sees touchpoint draft on /sequence/{id}
          │
          ├── Reads: summary, strategy, angle, contact
          ├── Reads: drafted email / call script / voicemail
          ├── Reads: rep notes (sensitivities, objections, follow-up plan)
          │
          ├── Optionally edits the draft in the text area
          │
          └── Clicks "Approve & Create Draft in Close"
                    │
                    ▼
              pipeline/close_write.py
              │
              ├── Email action    → POST /activity/email/ (status: draft)
              ├── Call/voicemail  → POST /activity/note/ (labelled script)
              └── LinkedIn        → POST /activity/note/ (labelled message)
                    │
                    ▼
              DB: touchpoint status → "approved"
              DB: sequence status   → "active"
              DB: last_checked_at   → now (gate monitoring starts)
```

---

### 3. Gate check (runs every 12 hours)

```
scheduler.py fires (every 12 hours)
          │
          ▼
    For each sequence with status = "active":
          │
          ▼
    pipeline/crm.py
    fetch_activities_since(lead_id, last_checked_at)
    ├── Calls since last check (with duration)
    ├── Notes since last check
    └── Emails since last check (non-draft)
          │
          ▼
    pipeline/gate.py
    Claude classifies the activity:
    │
    ├── CONTINUE       No meaningful activity
    │                  → DB: update last_checked_at
    │
    ├── WARN_CONTINUE  Minor activity (short call, generic reply)
    │                  → DB: save gate verdict
    │                  → Sequence stays active
    │                  → AE sees amber banner on next visit
    │
    └── PAUSE          Real conversation detected:
                       call > 2.5 min OR pain points mentioned
                       → DB: save gate verdict
                       → DB: sequence status → "paused"
                       → AE sees paused alert on dashboard
          │
          ▼
    Also checks: was a demo booked?
    ├── No  → continue
    └── Yes → DB: commission_event (opp_value × 10%)
                  Appears on /commission dashboard
```

---

### 4. Generating the next touchpoint (after gate clears)

```
Sequence is "active" (or AE overrides a "paused" sequence)
          │
          ▼
AE clicks "Generate Touchpoint N"
          │
          ▼
POST /sequence/{id}/next
├── DB: sequence status → "generating"
└── Background task: re-run full pipeline against current CRM state
          │
          ▼
    Same as "Starting a new sequence" from Stage 1 onward
    (lead is re-fetched fresh — CRM notes, calls, emails all updated)
          │
          ▼
    New touchpoint stored, sequence → "pending"
    AE reviews and approves again
```

---

## File reference

| File | Purpose |
|---|---|
| `app.py` | FastAPI web server — all routes and request handling |
| `db.py` | SQLite database — all reads and writes |
| `scheduler.py` | APScheduler — gate checks every 12 hours |
| `run.py` | CLI entrypoint — runs the pipeline without the web app |
| `pipeline/crm.py` | Fetch and normalise a Close lead + fetch activities since a date |
| `pipeline/website.py` | Scrape a company website for booking software signals |
| `pipeline/stages.py` | The 5 stage functions — loads prompts, fills variables, calls Claude |
| `pipeline/gate.py` | Gate classifier — Claude decides continue/warn/pause + demo detection |
| `pipeline/close_write.py` | Write email drafts and CRM notes back to Close |
| `pipeline/writer.py` | Write CLI output to output/*.json (CLI mode only) |
| `prompts/system.md` | Shared Claude system prompt — role, constraints, output rules |
| `prompts/01_assess.md` | Stage 1 — extract what we know from CRM and website |
| `prompts/02_strategy.md` | Stage 2 — score lead and select strategy |
| `prompts/03_angle.md` | Stage 3 — identify the single talking point and why now |
| `prompts/04_action.md` | Stage 4 — select channel and contact |
| `prompts/05_draft.md` | Stage 5 — write the actual outreach asset |
| `prompts/gate.md` | Gate classifier prompt — rules for pause/warn/continue + demo detection |
| `strategies/challenger.md` | Challenger playbook — reframe, create tension, control the process |
| `strategies/discovery.md` | Discovery playbook — ask before claiming, low-confidence leads |
| `strategies/mid_market.md` | Mid-Market playbook — ROI case, multi-stakeholder, proof points |
| `verticals/tourism/context.md` | Tourism narrative — who operators are, how they buy, website signals |
| `verticals/tourism/signals.json` | Tourism structured data — pain points, mismatches, competitor software |
| `templates/` | Jinja2 HTML templates for the web UI |
| `static/style.css` | UI styles |
| `nextmove.db` | SQLite database file (auto-created on first run, gitignored) |
| `.env` | Secrets and config — never committed to git |
| `.env.example` | Template with placeholder values — safe to share with teammates |

---

## Environment variables

| Variable | What it is | Required |
|---|---|---|
| `CLOSE_API_KEY` | Close.io API key | Yes |
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `TEST_LEAD_ID` | Default lead for CLI runs | Optional |
| `REP_NAME` | Rep name used in call scripts and voicemails | Optional |
| `REP_COMPANY` | Company name used in call scripts | Optional |
| `REP_PHONE` | Phone number used in voicemails | Optional |
| `NEXTMOVE_MODEL` | Claude model override (default: `claude-sonnet-4-6`) | Optional |

---

## Where to edit things

| If you want to change... | Edit this |
|---|---|
| What NextMove extracts from the CRM | `prompts/01_assess.md` |
| How leads are scored or strategy selected | `prompts/02_strategy.md` |
| What talking point is chosen | `prompts/03_angle.md` |
| Which channel or contact is picked | `prompts/04_action.md` |
| The tone or format of drafted assets | `prompts/05_draft.md` |
| The Challenger/Discovery/Mid-Market approach | `strategies/*.md` |
| Industry knowledge, pain points, buyer psychology | `verticals/tourism/context.md` |
| Structured signals, competitor software, deal sizes | `verticals/tourism/signals.json` |
| What the gate considers meaningful | `prompts/gate.md` |
| What booking software the scraper detects | `pipeline/website.py` |
| How often the gate runs | `scheduler.py` |

You never need to touch Python to change what NextMove produces. The intelligence lives in the prompts and vertical files.

---

## Sequence status reference

| Status | Meaning |
|---|---|
| `generating` | Pipeline is running — page shows loading spinner |
| `pending` | Touchpoint ready — waiting for AE to review and approve |
| `active` | Touchpoint approved, CRM monitoring is running |
| `paused` | Gate detected meaningful activity — AE must review before next touch |
| `cancelled` | AE rejected a touchpoint |
| `error` | Pipeline failed — error message stored in DB |

---

## Commission tracking

- 10% of opportunity value is owed to the app owner on any demo booked from a lead run through NextMove
- All users acknowledge this when starting a sequence (checkbox on the new sequence form)
- Demos are detected automatically: the gate classifier checks every 12 hours for signals like "demo booked", "meeting scheduled", "send me a Calendly", etc. in call notes and CRM activity
- Commission events appear on `/commission` — visible to all users
- The admin view at `/admin` shows aggregate stats across all reps (direct URL only)
