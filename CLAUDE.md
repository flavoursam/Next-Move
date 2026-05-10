# NextMove

AI-powered account intelligence tool for B2B sales reps. Connects to Close CRM, builds persistent memory per account, and surfaces a recommended next action with a ready-to-use outreach asset (email, call script, or voicemail). Reps can also run a stateless fresh pipeline for a second opinion.

## How to run

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env

# Start the web app
uvicorn app:app --reload

# CLI mode (single lead, no web app)
python run.py
python run.py lead_abc123XYZetc
```

## Two systems

**Account intelligence (primary)** — `GET /accounts`
Stateful. Each account has a persistent memory document that accumulates over time. Signals are ingested hourly from Close, memory is updated by Claude Opus, and a next-best-action is generated. Reps approve or reject on the account detail page.

**Legacy sequences** — `GET /`
Stateless. Each touchpoint re-runs the full 5-stage pipeline fresh against Close. Still intact and working.

## The pipeline (5 stages)

```
CRM fetch → Stage 1 (Assess) → Stage 2 (Strategy) → Stage 3 (Angle) → Stage 4 (Action) → Stage 5 (Draft)
```

| Stage | Prompt file | Job |
|---|---|---|
| 1 | `prompts/01_assess.md` | Extract facts, signals, contacts, deal context from CRM + website |
| 2 | `prompts/02_strategy.md` | Score the lead, select strategy (Challenger / Discovery / Mid-Market) |
| 3 | `prompts/03_angle.md` | Identify the single pain point and insight to lead with |
| 4 | `prompts/04_action.md` | Select the right channel and contact |
| 5 | `prompts/05_draft.md` | Write the actual outreach asset (email ≤150 words, call script, voicemail) |

## Key files

| File | Purpose |
|---|---|
| `app.py` | FastAPI web server — all routes |
| `db.py` | SQLite database — all reads and writes |
| `scheduler.py` | APScheduler — hourly account intelligence loop + 12hr gate checks |
| `run.py` | CLI entrypoint — runs pipeline without the web app |
| `pipeline/crm.py` | Close API logic — fetch and normalise a lead, fetch activities since a date |
| `pipeline/website.py` | Scrape company website for booking software signals |
| `pipeline/stages.py` | The 5 stage functions — mechanical runner, intelligence lives in prompts/ |
| `pipeline/gate.py` | Gate classifier — continue / warn / pause for active sequences |
| `memory/updater.py` | Claude Opus agent — init and update account memory documents |
| `actions/engine.py` | Claude Opus agent — determine next-best-action from memory |
| `actions/drafter.py` | Claude Sonnet agent — generate outreach draft from memory + action |
| `signals/ingestor.py` | Poll Close for new activity, save as signals |
| `prompts/` | Claude instructions for each stage and system prompt |
| `prompts/memory_init.md` | Schema + instructions for building initial memory document |
| `prompts/memory_update.md` | Rules for merging new signals into memory (includes confidence decay) |
| `prompts/action_engine.md` | Decision rules for next-best-action reasoning |
| `strategies/` | Challenger, Discovery, Mid-Market playbooks injected into stages 2, 3, 5 |
| `verticals/` | Industry context + structured signals injected into stage 1 |
| `MEMORY_GUIDE.md` | Plain English reference for the memory system — read this if memory seems stale |

## Tuning output quality

Edit prompt files in `prompts/`. Never need to touch `pipeline/stages.py`.

| Change | Edit this |
|---|---|
| What NextMove extracts from CRM | `prompts/01_assess.md` |
| How leads are scored / strategy selected | `prompts/02_strategy.md` |
| What talking point is chosen | `prompts/03_angle.md` |
| Which channel or contact is picked | `prompts/04_action.md` |
| Tone or format of outreach drafts | `prompts/05_draft.md` |
| How memory is built initially | `prompts/memory_init.md` |
| How memory updates (incl. confidence decay thresholds) | `prompts/memory_update.md` |
| How next-best-action is reasoned | `prompts/action_engine.md` |
| Challenger / Discovery / Mid-Market approach | `strategies/*.md` |
| Industry knowledge, pain points, buyer psychology | `verticals/tourism/context.md` |
| Booking software the scraper detects | `pipeline/website.py` lines 15–41 |

## Confidence decay

Pain points in memory decay automatically if not confirmed by new signals:
- 28 days without confirmation → high becomes medium
- 56 days without confirmation → medium becomes low

To change these thresholds: edit the numbers `28` and `56` in `prompts/memory_update.md` rule 9.

## Fresh pipeline (stateless comparison)

On any account detail page, click **"↺ Run"** to run all 5 pipeline stages against live Close data, ignoring account memory. The result appears as a purple card alongside the memory-based recommendation so reps can compare both before approving. Fresh results never update the memory document.

## Adding a new vertical

1. Create `verticals/{name}/context.md` — narrative context for Claude
2. Create `verticals/{name}/signals.json` — pain points, decision maker titles, competitor software
3. Pass the vertical when adding an account via the web app or CLI

## Adding a new strategy

1. Create `strategies/{name}.md` with the strategy logic and draft guidance
2. Add the routing rule in `prompts/02_strategy.md`
