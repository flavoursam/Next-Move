# NextMove — System Overview

## What it does

NextMove is an AI-powered account intelligence platform for B2B sales reps. It connects to Close CRM, builds a persistent memory document per account, and surfaces a recommended next action with a ready-to-use outreach asset (email, call script, or voicemail). Reps review and approve each recommendation before anything is sent. Drafts are created directly in Close.

Between approvals, NextMove monitors Close for new activity, updates account memory automatically, and generates a fresh recommendation. Confidence in identified pain points decays over time if not confirmed by new signals, ensuring memory stays honest.

---

## Two parallel systems

### Account intelligence (primary)
Stateful. Persistent memory per account, updated hourly from Close signals. Memory-based and fresh-pipeline recommendations shown side by side on the account detail page.

### Legacy sequences
Stateless. Each touchpoint re-runs the full 5-stage pipeline fresh against Close. Still intact at `/`.

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
│   │  - CRM notes     │              │    stages 1/4/5)               │   │
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
│  │  Account intelligence routes:                                        │ │
│  │    GET  /accounts              Account list                          │ │
│  │    GET  /accounts/new          Add account form                      │ │
│  │    POST /accounts/new          Init account (background)             │ │
│  │    GET  /accounts/{id}         Account detail — memory + actions     │ │
│  │    POST /accounts/{id}/actions/{aid}/approve  Approve → draft Close  │ │
│  │    POST /accounts/{id}/actions/{aid}/reject   Reject action          │ │
│  │    POST /accounts/{id}/refresh  Manual signal ingest + memory update │ │
│  │    POST /accounts/{id}/run-fresh  Run 5-stage pipeline (stateless)   │ │
│  │                                                                      │ │
│  │  Legacy sequence routes:                                             │ │
│  │    GET  /              Dashboard (all sequences)                     │ │
│  │    GET  /sequence/new  New sequence form                             │ │
│  │    POST /sequence/new  Start pipeline (background task)              │ │
│  │    GET  /sequence/{id} Sequence detail + touchpoint review           │ │
│  │    POST /sequence/{id}/approve/{tp}  Approve → draft in Close       │ │
│  │    POST /sequence/{id}/reject/{tp}   Reject + cancel sequence        │ │
│  │    POST /sequence/{id}/next          Generate next touchpoint        │ │
│  │    GET  /commission    Commission dashboard                           │ │
│  └─────────┬───────────────────────┬────────────────────────────────┬──┘ │
│            │                       │                                │    │
│  ┌─────────▼──────┐   ┌────────────▼──────────┐   ┌───────────────▼──┐  │
│  │   pipeline/    │   │    scheduler.py        │   │  templates/      │  │
│  │                │   │                        │   │                  │  │
│  │  crm.py        │   │  process_accounts()    │   │  account.html    │  │
│  │  website.py    │   │  every 1 hour:         │   │  accounts.html   │  │
│  │  stages.py     │   │  - ingest signals      │   │  (+ legacy set)  │  │
│  │  gate.py       │   │  - update memory       │   │                  │  │
│  │  close_write.py│   │  - generate action     │   │  static/         │  │
│  │                │   │                        │   │  style.css       │  │
│  │  memory/       │   │  check_sequences()     │   │                  │  │
│  │  updater.py    │   │  every 12 hours:       │   └──────────────────┘  │
│  │                │   │  - gate classifier     │                         │
│  │  actions/      │   │  - demo detection      │                         │
│  │  engine.py     │   │  - commission events   │                         │
│  │  drafter.py    │   └────────────────────────┘                         │
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
│  │   actions            recommendations — source: memory | fresh       │  │
│  │   sequences          legacy: one per lead                           │  │
│  │   touchpoints        legacy: each pipeline run                      │  │
│  │   gate_verdicts      legacy: continue / warn_continue / pause       │  │
│  │   commission_events  demo detected → 10% of opp value               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow diagrams

### 1. Adding a new account (account intelligence)

```
Rep opens /accounts/new
          │
          ▼
    Enter Close lead ID + vertical
          │
          ▼
    POST /accounts/new
          │
          ├── DB: create account record
          ├── Redirect rep to /accounts/{id} (shows loading)
          └── Background task _init_account():
                    │
                    ▼
              pipeline/crm.py
              ├── Fetch lead from Close API
              └── Scrape website (pipeline/website.py)
                    │
                    ▼
              pipeline/stages.py — Stage 1 (Assess)
              In: lead + website signals + vertical context
              Out: company summary, signals, contacts, gaps
                    │
                    ▼
              memory/updater.py — init()
              Builds initial memory document (Claude Opus)
                    │
                    ▼
              actions/engine.py — determine()
              Generates first action recommendation (Claude Opus)
                    │
                    ▼
              DB: save memory + action
              Page auto-refreshes → rep sees account detail
```

---

### 2. Account detail page (side-by-side view)

```
Rep opens /accounts/{id}
          │
          ├── Left column: Account Memory
          │   pain points (with confidence), objections, engagement,
          │   buying readiness, org intelligence, vertical signals,
          │   action history, recent signals
          │
          ├── Middle column: Memory-based Recommendation
          │   Current action from account memory
          │   Approve + Draft  |  Reject
          │
          └── Right column: Fresh Pipeline
              If not run: "Run Fresh Pipeline" button
              If running: spinner + stage list + auto-refresh (6s)
              If done: full 5-stage result independent of memory
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
          │   memory/updater → action_drafter.generate()
          │   → pipeline/close_write.py → Close API (email draft or note)
          │
          └── Background: _log_outreach_to_memory()
              Directly updates engagement_history.last_contact_attempt
              Increments total_touchpoints
              Saves outreach_sent signal (no Claude call — direct DB update)
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
              pipeline/crm.py — fetch live lead from Close
                    │
                    ▼
              pipeline/stages.py — all 5 stages (Claude Sonnet/Opus)
              Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5
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
    ├── Calls (with notes, truncated to 500 chars)
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

### 6. Manual refresh (rep-triggered)

```
Rep clicks "Refresh Signals"
          │
          ▼
POST /accounts/{id}/refresh
          │
          └── Same as hourly loop, PLUS:
              pipeline/website.py — re-scrape company website
              If booking software changed → save website_update signal
              → included in this memory update
```

---

### 7. Gate check — legacy sequences (runs every 12 hours)

```
scheduler.py fires (every 12 hours)
          │
          ▼
    For each sequence with status = "active":
          │
          ▼
    pipeline/crm.py → fetch_activities_since(lead_id, last_checked_at)
          │
          ▼
    pipeline/gate.py — Claude classifies activity:
    ├── CONTINUE       No meaningful activity
    ├── WARN_CONTINUE  Minor activity (short call, generic reply)
    └── PAUSE          Real conversation detected
          │
          ▼
    Also checks: was a demo booked?
    └── Yes → DB: commission_event (opp_value × 10%)
```

---

## File reference

| File | Purpose |
|---|---|
| `app.py` | FastAPI web server — all routes and request handling |
| `db.py` | SQLite database — all reads and writes |
| `scheduler.py` | APScheduler — hourly account loop + 12hr gate checks |
| `run.py` | CLI entrypoint — runs pipeline without web app |
| `pipeline/crm.py` | Fetch and normalise a Close lead; fetch activities since a date |
| `pipeline/website.py` | Scrape company website for booking software signals |
| `pipeline/stages.py` | The 5 stage functions — mechanical runner |
| `pipeline/gate.py` | Gate classifier for legacy sequences |
| `pipeline/close_write.py` | Write email drafts and CRM notes to Close |
| `pipeline/writer.py` | Write CLI output to output/*.json |
| `memory/updater.py` | Init and update account memory documents (Claude Opus) |
| `actions/engine.py` | Determine next-best-action from memory (Claude Opus) |
| `actions/drafter.py` | Generate outreach draft from memory + action (Claude Sonnet) |
| `signals/ingestor.py` | Poll Close for new activity, save as signals |
| `prompts/system.md` | Shared Claude system prompt |
| `prompts/01_assess.md` – `05_draft.md` | The 5 pipeline stage prompts |
| `prompts/memory_init.md` | Initial memory document schema + instructions |
| `prompts/memory_update.md` | Memory update rules, confidence decay (edit 28/56 thresholds here) |
| `prompts/action_engine.md` | Next-best-action decision rules |
| `prompts/gate.md` | Gate classifier prompt for legacy sequences |
| `strategies/challenger.md` | Challenger sales playbook |
| `strategies/discovery.md` | Discovery playbook |
| `strategies/mid_market.md` | Mid-Market playbook |
| `verticals/tourism/context.md` | Tourism narrative — buyer psychology, seasonality |
| `verticals/tourism/signals.json` | Tourism structured data — pain points, competitor software |
| `templates/` | Jinja2 HTML templates |
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
| `NEXTMOVE_MODEL` | Claude model override for stages 1/4/5 (default: `claude-sonnet-4-6`) | Optional |
| `NEXTMOVE_PLANNING_MODEL` | Model for stages 2/3 + memory/action (default: `claude-opus-4-7`) | Optional |

---

## Where to edit things

| If you want to change... | Edit this |
|---|---|
| What NextMove extracts from CRM | `prompts/01_assess.md` |
| How leads are scored or strategy selected | `prompts/02_strategy.md` |
| What talking point is chosen | `prompts/03_angle.md` |
| Which channel or contact is picked | `prompts/04_action.md` |
| Tone or format of outreach drafts | `prompts/05_draft.md` |
| How initial memory is built | `prompts/memory_init.md` |
| How memory updates + confidence decay thresholds | `prompts/memory_update.md` (numbers 28 and 56) |
| How next-best-action is reasoned | `prompts/action_engine.md` |
| Challenger / Discovery / Mid-Market approach | `strategies/*.md` |
| Industry knowledge, pain points, buyer psychology | `verticals/tourism/context.md` |
| Booking software the scraper detects | `pipeline/website.py` lines 15–41 |
| What the gate considers meaningful (legacy) | `prompts/gate.md` |
| How often the hourly loop runs | `scheduler.py` |

---

## Sequence status reference (legacy)

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
- Demos are detected automatically by the gate classifier every 12 hours
- Commission events appear on `/commission`
- Admin view at `/admin` shows aggregate stats (direct URL only)
