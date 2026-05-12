# NextMove

AI-powered account intelligence tool for B2B sales reps. Connects to Close CRM, builds persistent memory per account, and surfaces a recommended next action with a ready-to-use outreach asset (email, call script, or voicemail).

## How to run

```bash
pip3 install -r requirements.txt

# Create .env with your keys (no .env.example — create from scratch):
# ANTHROPIC_API_KEY=...
# CLOSE_API_KEY=...
# CLOSE_WRITEBACK_ENABLED=false
# REP_NAME=Sam

python3 -m uvicorn app:app --reload   # web app at localhost:8000

python3 run.py               # CLI mode (single lead)
python3 run.py lead_abc123
```

### Quick-start (after first setup)

Add to `~/.zshrc` for a single command launch from any terminal:

```bash
alias nextmove='cd ~/Documents/Claude/Projects/Next-Move && python3 -m uvicorn app:app --reload'
```

Then just type `nextmove` to start.

## Pages

| URL | What it is |
|---|---|
| `/` | Next Touchpoint — enter a Close lead ID, run the 6-stage pipeline, get immediate outreach + discovery |
| `/runs` | All leads run through Next Touchpoint — company, last run time, software, angle, action |
| `/accounts/{id}` | Account detail — persistent memory + memory-based recommendation + fresh-pipeline card |
| `/commission` | Commission tracking — 10% of opp value owed to app owner on each demo booked |
| `/admin` | Aggregate stats |
| `/identity` | User identity setup (cookie-based, no passwords) |

## The pipeline (6 stages)

```
CRM fetch → Stage 1 (Assess) → Stage 2 (Strategy) → Stage 3 (Angle) → Stage 4 (Action) → Stage 5 (Draft) → Stage 6 (Discovery)
```

| Stage | Prompt file | Job |
|---|---|---|
| 1 | `prompts/01_assess.md` | Extract facts, signals, contacts, deal context from CRM + website |
| 2 | `prompts/02_strategy.md` | Score the lead, select strategy (Challenger / Discovery / Mid-Market) |
| 3 | `prompts/03_angle.md` | Identify the single pain point and insight to lead with |
| 4 | `prompts/04_action.md` | Select the right channel and contact |
| 5 | `prompts/05_draft.md` | Write the actual outreach asset (email ≤150 words, call script, voicemail) |
| 6 | `prompts/06_discovery.md` | Discovery questions, rep tips, competitor context |

## Key files

| File | Purpose |
|---|---|
| `app.py` | FastAPI web server — all routes |
| `db.py` | SQLite database — all reads and writes |
| `scheduler.py` | APScheduler — hourly account intelligence loop |
| `run.py` | CLI entrypoint — runs pipeline without the web app |
| `pipeline/crm.py` | Close API logic — fetch and normalise a lead, fetch activities since a date |
| `pipeline/website.py` | Scrape company website for booking software signals |
| `pipeline/stages.py` | The 6 stage functions — mechanical runner, intelligence lives in prompts/ |
| `pipeline/close_write.py` | Write email drafts and CRM notes to Close (gated by `CLOSE_WRITEBACK_ENABLED`) |
| `pipeline/writer.py` | Write CLI pipeline output to `output/*.json` |
| `pipeline/context_loader.py` | Load operator-type and software-specific context lenses |
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

## Model selection

Stages 2 and 3 (strategy + angle) and memory/action engine use `claude-opus-4-7` by default — they require deeper reasoning. All other stages use `claude-sonnet-4-6`.

Override via env vars:
- `NEXTMOVE_PLANNING_MODEL` — stages 2/3, memory updater, action engine (default: `claude-opus-4-7`)
- `NEXTMOVE_MODEL` — all other stages (default: `claude-sonnet-4-6`)

## Tuning output quality

Edit prompt files in `prompts/`. Never need to touch `pipeline/stages.py`.

| Change | Edit this |
|---|---|
| What NextMove extracts from CRM | `prompts/01_assess.md` |
| How leads are scored / strategy selected | `prompts/02_strategy.md` |
| What talking point is chosen | `prompts/03_angle.md` |
| Which channel or contact is picked | `prompts/04_action.md` |
| Tone or format of outreach drafts | `prompts/05_draft.md` |
| Discovery questions and rep tips | `prompts/06_discovery.md` |
| How memory is built initially | `prompts/memory_init.md` |
| How memory updates (incl. confidence decay thresholds) | `prompts/memory_update.md` |
| How next-best-action is reasoned | `prompts/action_engine.md` |
| Challenger / Discovery / Mid-Market approach | `strategies/*.md` |
| Industry knowledge, pain points, buyer psychology | `verticals/tourism/context.md` |
| Booking software the scraper detects | `pipeline/website.py` lines 15–41 |
| Enable/disable pushing drafts to Close on approval | `CLOSE_WRITEBACK_ENABLED` in `.env` (default: `false`) |

## Confidence decay

Pain points in memory decay automatically if not confirmed by new signals:
- 28 days without confirmation → high becomes medium
- 56 days without confirmation → medium becomes low

To change these thresholds: edit the numbers `28` and `56` in `prompts/memory_update.md` rule 9.

## Fresh pipeline (stateless comparison)

On any account detail page, click **"↺ Run"** to run all 6 pipeline stages against live Close data, ignoring account memory. The result appears as a purple card alongside the memory-based recommendation so reps can compare both before approving. Fresh results never update the memory document.

## How Next Touchpoint and Account Intelligence connect

Running a lead through Next Touchpoint (`/`) automatically creates an account record. The account then gets a memory document built in the background (Stage 1 + Claude Opus), and is picked up by the hourly scheduler for ongoing signal ingestion. So every Next Touchpoint run double-registers the lead for long-term tracking at `/accounts/{id}`.

## Adding a new vertical

1. Create `verticals/{name}/context.md` — narrative context for Claude
2. Create `verticals/{name}/signals.json` — pain points, decision maker titles, competitor software
3. Pass the vertical when adding an account via the web app or CLI

## Adding a new strategy

1. Create `strategies/{name}.md` with the strategy logic and draft guidance
2. Add the routing rule in `prompts/02_strategy.md`
