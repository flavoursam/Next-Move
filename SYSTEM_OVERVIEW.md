# NextMove — System Overview

## What it does

NextMove is an AI-powered account intelligence platform for B2B sales reps. It connects to Close CRM, builds a persistent memory document per account, and surfaces a recommended next action with a ready-to-use outreach asset (email, call script, or voicemail). Reps review and approve each recommendation before anything is sent. Drafts are created directly in Close.

Between approvals, NextMove monitors Close for new activity, updates account memory automatically, and generates a fresh recommendation. Confidence in identified pain points decays over time if not confirmed by new signals, ensuring memory stays honest.

---

## Architecture map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                              │
│                                                                             │
│   ┌──────────────────┐              ┌──────────────────────────────────┐   │
│   │   Close.io CRM   │              │         Claude API (Anthropic)   │   │
│   │                  │              │                                  │   │
│   │  - Lead data     │              │  - claude-opus-4-7 (memory +    │   │
│   │  - Activities    │              │    action engine)               │   │
│   │  - Email drafts  │              │  - claude-sonnet-4-6 (drafts,  │   │
│   │  - CRM notes     │              │    stages 1/4/5/6)             │   │
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
│  │  Next Touchpoint:                                                    │ │
│  │    GET  /                  Form — enter Close lead ID                │ │
│  │    POST /      → redirect  Start run (background task)              │ │
│  │    GET  /run/{id}          Loading page (SSE log stream)            │ │
│  │    GET  /run/{id}/stream   SSE — live log lines → redirect on done  │ │
│  │    GET  /runs              All runs — company, last run, angle, etc  │ │
│  │                                                                      │ │
│  │  Account intelligence:                                               │ │
│  │    GET  /accounts/{id}     Memory + pending action + fresh card      │ │
│  │    POST /accounts/{id}/actions/{aid}/approve  → draft in Close      │ │
│  │    POST /accounts/{id}/actions/{aid}/reject   Reject action         │ │
│  │    POST /accounts/{id}/actions/{aid}/rethink  New action (excl used)│ │
│  │    POST /accounts/{id}/refresh   Manual signal ingest + rescrape    │ │
│  │    POST /accounts/{id}/run-fresh  Run 6-stage pipeline (stateless)  │ │
│  │    POST /accounts/{id}/reinit-memory  Rebuild memory from scratch   │ │
│  │    GET  /accounts/new      Add account form (direct memory tracking)│ │
│  │    POST /accounts/new                                                │ │
│  └─────────┬───────────────────────┬────────────────────────────────┬──┘ │
│            │                       │                                │    │
│  ┌─────────▼──────┐   ┌────────────▼──────────┐   ┌───────────────▼──┐  │
│  │   pipeline/    │   │    scheduler.py        │   │  templates/      │  │
│  │                │   │                        │   │                  │  │
│  │  crm.py        │   │  process_accounts()    │   │  neglected.html  │  │
│  │  website.py    │   │  every 1 hour:         │   │  run_loading.html│  │
│  │  stages.py     │   │  - ingest signals      │   │  runs.html       │  │
│  │  close_write.py│   │  - update memory       │   │  account.html    │  │
│  │  context_loader│   │  - generate action     │   │  (+ shared)      │  │
│  │                │   └────────────────────────┘   │                  │  │
│  │  memory/       │                                │  static/         │  │
│  │  updater.py    │                                │  style.css       │  │
│  │                │                                └──────────────────┘  │
│  │  actions/      │                                                       │
│  │  engine.py     │                                                       │
│  │  drafter.py    │                                                       │
│  │                │                                                       │
│  │  signals/      │                                                       │
│  │  ingestor.py   │                                                       │
│  └─────────┬──────┘                                                       │
│            │                                                               │
│  ┌─────────▼───────────────────────────────────────────────────────────┐  │
│  │   db.py  —  SQLite (nextmove.db)                                    │  │
│  │                                                                     │  │
│  │   users              identity (name + cookie, no passwords)         │  │
│  │   accounts           one per tracked account — state, vertical      │  │
│  │   account_memory     versioned memory documents (JSON)              │  │
│  │   signals            raw activity from Close + synthetic signals    │  │
│  │   actions            recommendations — source: memory | fresh |     │  │
│  │                       neglected                                     │  │
│  │   commission_events  demo detected → 10% of opp value               │  │
│  │                                                                     │  │
│  │   (legacy — not the primary data path)                              │  │
│  │   sequences          multi-lead sequence tracking                   │  │
│  │   touchpoints        per-sequence touchpoint records                │  │
│  │   gate_verdicts      after-touchpoint gate classifier results       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow diagrams

### 1. Running Next Touchpoint (home page)

```
Rep opens /
          │
          ▼
    Enters Close lead ID → clicks Run
          │
          ▼
    POST / → redirects to /run/{run_id}
          │
          ├── Loading page with live SSE log stream
          └── Background task _run_neglected_pipeline():
                    │
                    ├── Fetch lead from Close API (crm.py)
                    ├── Stage 1: Assess
                    ├── Stage 2: Strategy
                    ├── Stage 3: Angle
                    ├── Stage 4: Action
                    ├── Stage 5: Draft
                    ├── Stage 6: Discovery package
                    ├── Auto-register account (if new)
                    └── Save action with source='neglected'
                    │
                    ▼
              SSE sends "done" event → page redirects to result
              Result shown on /run/{run_id} (same neglected.html template)
```

---

### 2. Account detail page (memory + fresh pipeline)

```
Rep opens /accounts/{id}
          │
          ├── Left: Account Memory
          │   pain points (with confidence), objections, engagement,
          │   buying readiness, org intelligence, vertical signals,
          │   action history, recent signals
          │
          ├── Middle: Memory-based Recommendation
          │   Current action from account memory
          │   Approve + Draft  |  Reject  |  Rethink (up to 3×)
          │
          └── Right: Fresh Pipeline
              If not run: "↺ Run" button
              If running: spinner + auto-refresh (6s)
              If done: full 6-stage result independent of memory
                       Use This + Draft  |  Dismiss
```

---

### 3. Approving a memory-based action

```
Rep clicks "Approve + Draft"
          │
          ▼
POST /accounts/{id}/actions/{aid}/approve
          │
          ├── DB: mark action as approved
          │
          ├── Background: _generate_and_log_draft()
          │   action_drafter.generate() → close_write.py → Close API
          │   (email draft or note depending on action type)
          │
          └── Background: _log_outreach_to_memory()
              Updates engagement_history.last_contact_attempt
              Increments total_touchpoints
              Marks pain point as used_as_angle
              Saves outreach_sent signal (no Claude call — direct DB write)
```

---

### 4. Running fresh pipeline (stateless comparison)

```
Rep clicks "↺ Run"
          │
          ▼
POST /accounts/{id}/run-fresh
          │
          ├── DB: accounts.fresh_running = 1
          ├── Redirect → page shows spinner + auto-refresh
          └── Background: _run_fresh_account()
                    │
                    ▼
              Fetch live lead from Close
              Stages 1–5 + Stage 6 (Claude Sonnet/Opus)
                    │
                    ▼
              DB: create action with source='fresh'
              DB: accounts.fresh_running = 0
                    │
                    ▼
              Page auto-refreshes → purple card appears
              Memory is NOT updated
```

---

### 5. Hourly account intelligence loop

```
scheduler.py fires (every 1 hour)
          │
          ▼
    For each account with state = 'active':
          │
          ▼
    signals/ingestor.py
    fetch_activities_since(lead_id, last_signal_at)
    ├── Calls (notes, truncated to 500 chars)
    ├── Text notes (truncated to 500 chars)
    └── Emails (subject + body, truncated to 1500 chars)
          │
          ▼
    If new signals:
          │
          ▼
    memory/updater.py — update()
    Claude Opus merges signals into memory document
    Applies confidence decay:
    ├── 28 days unconfirmed → high becomes medium
    └── 56 days unconfirmed → medium becomes low
          │
          ▼
    actions/engine.py — determine()
    New action recommendation from updated memory
          │
          ▼
    DB: save new memory version + new action
    DB: expire previous pending action
```

---

## File reference

| File | Purpose |
|---|---|
| `app.py` | FastAPI web server — all routes and request handling |
| `db.py` | SQLite database — all reads and writes |
| `scheduler.py` | APScheduler — hourly account intelligence loop |
| `run.py` | CLI entrypoint — runs pipeline without web app |
| `pipeline/crm.py` | Fetch and normalise a Close lead; fetch activities since a date |
| `pipeline/website.py` | Scrape company website for booking software signals |
| `pipeline/stages.py` | The 5+1 stage functions — mechanical runner |
| `pipeline/close_write.py` | Write email drafts and CRM notes to Close |
| `pipeline/context_loader.py` | Load operator-type and software-specific context lenses |
| `pipeline/writer.py` | Write CLI output to output/*.json |
| `memory/updater.py` | Init and update account memory documents (Claude Opus) |
| `actions/engine.py` | Determine next-best-action from memory (Claude Opus) |
| `actions/drafter.py` | Generate outreach draft from memory + action (Claude Sonnet) |
| `signals/ingestor.py` | Poll Close for new activity, save as signals |
| `prompts/system.md` | Shared Claude system prompt |
| `prompts/01_assess.md` – `06_discovery.md` | The 6 pipeline stage prompts |
| `prompts/memory_init.md` | Initial memory document schema + instructions |
| `prompts/memory_update.md` | Memory update rules + confidence decay (edit 28/56 thresholds here) |
| `prompts/action_engine.md` | Next-best-action decision rules |
| `strategies/challenger.md` | Challenger sales playbook |
| `strategies/discovery.md` | Discovery playbook |
| `strategies/mid_market.md` | Mid-Market playbook |
| `verticals/tourism/context.md` | Tourism narrative — buyer psychology, seasonality |
| `verticals/tourism/signals.json` | Tourism structured data — pain points, competitor software |
| `templates/neglected.html` | Next Touchpoint form + result display |
| `templates/run_loading.html` | Live log stream loading page |
| `templates/runs.html` | All runs list |
| `templates/account.html` | Account detail — memory + actions |
| `static/style.css` | UI styles |
| `MEMORY_GUIDE.md` | Plain English reference for the memory system |
| `nextmove.db` | SQLite database file (auto-created, gitignored) |
| `.env` | Secrets and config — never committed |
| `.env.example` | Template with placeholder values |

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
| `NEXTMOVE_MODEL` | Claude model override for stages 1/4/5/6 (default: `claude-sonnet-4-6`) | Optional |
| `NEXTMOVE_PLANNING_MODEL` | Model for stages 2/3 + memory/action (default: `claude-opus-4-7`) | Optional |
| `CLOSE_WRITEBACK_ENABLED` | Push approved drafts into Close as email drafts/notes (default: `false`) | Optional |

---

## Where to edit things

| If you want to change... | Edit this |
|---|---|
| What NextMove extracts from CRM | `prompts/01_assess.md` |
| How leads are scored or strategy selected | `prompts/02_strategy.md` |
| What talking point is chosen | `prompts/03_angle.md` |
| Which channel or contact is picked | `prompts/04_action.md` |
| Tone or format of outreach drafts | `prompts/05_draft.md` |
| Discovery questions and rep tips | `prompts/06_discovery.md` |
| How initial memory is built | `prompts/memory_init.md` |
| How memory updates + confidence decay thresholds | `prompts/memory_update.md` (numbers 28 and 56) |
| How next-best-action is reasoned | `prompts/action_engine.md` |
| Challenger / Discovery / Mid-Market approach | `strategies/*.md` |
| Industry knowledge, pain points, buyer psychology | `verticals/tourism/context.md` |
| Booking software the scraper detects | `pipeline/website.py` lines 15–41 |
| How often the hourly loop runs | `scheduler.py` |

---

## Commission tracking

- 10% of opportunity value is owed to the app owner on any demo booked from a lead run through NextMove
- Commission events appear on `/commission`
- Admin stats at `/admin`
