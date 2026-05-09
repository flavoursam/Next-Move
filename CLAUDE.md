# NextMove

AI-powered sales prioritisation tool for B2B sales reps. Takes one CRM lead, runs it through a 5-stage pipeline, and returns one recommended next action with a ready-to-use outreach asset (email, call script, or voicemail).

## How to run

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env

# Run on your test lead (uses TEST_LEAD_ID from .env)
python run.py

# Or pass a lead ID directly
python run.py lead_abc123XYZetc
```

## The pipeline

```
CRM fetch → Stage 1 (Assess) → Stage 2 (Strategy) → Stage 3 (Angle) → Stage 4 (Action) → Stage 5 (Draft) → Output file
```

| Stage | File | Job |
|---|---|---|
| 1 | `prompts/01_assess.md` | Extract what we know from CRM — facts, signals, contacts, deal context |
| 2 | `prompts/02_strategy.md` | Score the lead and select a strategy: Challenger, Discovery, or Mid-Market |
| 3 | `prompts/03_angle.md` | Identify the single pain point and insight to lead with |
| 4 | `prompts/04_action.md` | Select the right channel and contact |
| 5 | `prompts/05_draft.md` | Write the actual asset — email, call script, or voicemail |

## Key files

| File | Purpose |
|---|---|
| `run.py` | Entrypoint — orchestrates the pipeline end to end |
| `pipeline/crm.py` | All Close.io API logic — fetch and normalize a lead |
| `pipeline/stages.py` | The 5 stage functions — each loads a prompt, fills variables, calls Claude API |
| `pipeline/writer.py` | Writes the output JSON file |
| `prompts/` | Claude's instructions for each stage — edit these to tune output quality |
| `strategies/` | Strategy-specific logic injected into stages 2, 3, and 5 |
| `verticals/` | Vertical context injected into stage 1 |

## Tuning output quality

To improve what NextMove produces, edit the prompt files in `prompts/`. You never need to touch `pipeline/stages.py` for quality changes — that file is just the mechanical runner.

To improve a specific stage, open its prompt file and adjust the instructions or output schema.

## Adding a new vertical

1. Create `verticals/{name}/context.md` — narrative context for Claude (who these businesses are, what they care about, how to talk to them)
2. Create `verticals/{name}/signals.json` — structured signals: pain points, decision maker titles, competitor software
3. Pass the vertical name when running: `python run.py lead_abc123 --vertical hospitality`

## Adding a new strategy

1. Create `strategies/{name}.md` with the strategy logic and draft guidance
2. Add the routing rule in `prompts/02_strategy.md` under the strategy selection rules

## Current constraints (v1)

- One lead at a time
- Tourism vertical only (add more via `verticals/`)
- No write-back to CRM
- No frontend
- No batch processing

## Future stages (enterprise)

When this tool grows to enterprise use cases, two additional stages slot in after Stage 5:

- **Stage 6 — Stakeholder Map**: multi-contact accounts, different angles per role
- **Stage 7 — Sequence Plan**: multi-touch campaign planning across channels and time
