"""
The 5 NextMove pipeline stages.

Each stage function:
  1. Reads its prompt template from prompts/
  2. Fills {{placeholders}} with real data
  3. Sends to the Claude API with the shared system prompt
  4. Parses and returns the JSON response

─── Editing output quality ───────────────────────────────────────────────────
To improve what NextMove produces, edit the files in prompts/ — not this file.
This file is just the mechanical runner. The intelligence lives in the prompts.

─── Adding a stage ───────────────────────────────────────────────────────────
1. Create prompts/0N_name.md
2. Add a function here following the same pattern as existing stages
3. Call it from run.py
"""

import json
import os

import anthropic

# Anthropic client — api_key is loaded from ANTHROPIC_API_KEY in your .env file
# load_dotenv() in run.py put it in os.environ before this module is imported
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# System prompt is shared across all 5 stages — defines Claude's role and constraints
_SYSTEM_PROMPT = open("prompts/system.md").read()

# Default model for extraction/drafting stages — override with NEXTMOVE_MODEL in .env
# Use claude-haiku-4-5-20251001 for cheap/fast testing
MODEL = os.getenv("NEXTMOVE_MODEL", "claude-sonnet-4-6")

# Planning stages (2 — Strategy, 3 — Angle) use Opus for better reasoning
# Override with NEXTMOVE_PLANNING_MODEL in .env
PLANNING_MODEL = os.getenv("NEXTMOVE_PLANNING_MODEL", "claude-opus-4-7")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_prompt(filename: str) -> str:
    """Read a prompt template from the prompts/ directory."""
    with open(f"prompts/{filename}") as f:
        return f.read()


def _load_strategy(strategy_name: str) -> str:
    """
    Load the strategy instructions file for the given strategy name.
    Strategy files live in strategies/ and are injected into stages 3 and 5.
    """
    path = f"strategies/{strategy_name}.md"
    if not os.path.exists(path):
        return f"[No strategy file found for '{strategy_name}' — using judgment only]"
    with open(path) as f:
        return f.read()


def _fill(template: str, **kwargs) -> str:
    """Replace {{key}} placeholders in a prompt template with real values."""
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


def _call_claude(prompt: str, model: str = None, max_tokens: int = 2048) -> dict:
    """
    Send a filled prompt to Claude and return the parsed JSON response.
    Claude is instructed (via system.md) to return only valid JSON.
    """
    response = _client.messages.create(
        model=model or MODEL,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the output in ```json ... ```
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"\n--- Claude returned unparseable output ---\n{text}\n---")
        raise ValueError(f"Stage returned invalid JSON: {e}") from e


# ─── Pipeline stages ──────────────────────────────────────────────────────────

def run_assess(lead: dict, vertical_context: str, vertical_signals: dict) -> dict:
    """
    Stage 1 — Assess.
    Input:  normalized lead dict + vertical context + vertical signals
    Output: company summary, key signals, contacts, deal context, gaps
    Prompt: prompts/01_assess.md
    """
    prompt = _fill(
        _load_prompt("01_assess.md"),
        lead_data=lead,
        vertical_context=vertical_context,
        vertical_signals=vertical_signals,
    )
    return _call_claude(prompt, max_tokens=4096)


def run_strategy(assessment: dict) -> dict:
    """
    Stage 2 — Strategy.
    Input:  Stage 1 assessment
    Output: priority score, urgency, confidence, selected strategy, reasoning
    Prompt: prompts/02_strategy.md
    """
    prompt = _fill(
        _load_prompt("02_strategy.md"),
        assessment=assessment,
    )
    return _call_claude(prompt, model=PLANNING_MODEL)


def run_angle(assessment: dict, strategy_result: dict) -> dict:
    """
    Stage 3 — Angle.
    Input:  Stage 1 assessment + Stage 2 strategy result + strategy instructions file
    Output: primary pain point, sales angle, supporting signal, why now, claim strength
    Prompt: prompts/03_angle.md
    """
    strategy_name = strategy_result.get("selected_strategy", "challenger")
    prompt = _fill(
        _load_prompt("03_angle.md"),
        assessment=assessment,
        strategy_result=strategy_result,
        strategy_instructions=_load_strategy(strategy_name),
    )
    return _call_claude(prompt, model=PLANNING_MODEL)


def run_action(assessment: dict, strategy_result: dict, angle_result: dict) -> dict:
    """
    Stage 4 — Action.
    Input:  Stages 1–3 results
    Output: recommended channel (email/cold_call/voicemail/linkedin), contact details, reasoning
    Prompt: prompts/04_action.md
    """
    prompt = _fill(
        _load_prompt("04_action.md"),
        assessment=assessment,
        strategy_result=strategy_result,
        angle_result=angle_result,
    )
    return _call_claude(prompt)


def run_draft(
    assessment: dict,
    strategy_result: dict,
    angle_result: dict,
    action_result: dict,
    rep_context: dict,
) -> dict:
    """
    Stage 5 — Draft.
    Input:  All prior stage results + strategy instructions + rep context (name, company, phone)
    Output: summary, the actual outreach asset (email / call script / voicemail), rep notes
    Prompt: prompts/05_draft.md
    """
    strategy_name = strategy_result.get("selected_strategy", "challenger")
    prompt = _fill(
        _load_prompt("05_draft.md"),
        assessment=assessment,
        strategy_result=strategy_result,
        angle_result=angle_result,
        action_result=action_result,
        strategy_instructions=_load_strategy(strategy_name),
        rep_context=rep_context,
    )
    return _call_claude(prompt)


def run_discovery(
    assessment: dict,
    angle_result: dict,
    activity_type_context: dict | None,
    software_context: dict | None,
) -> dict:
    """
    Stage 6 — Discovery Package (used for neglected account runs).
    Input:  Stage 1 assessment + Stage 3 angle + activity type context + software context
    Output: discovery_questions, rep_tips, competitor_context
    Prompt: prompts/06_discovery.md
    """
    prompt = _fill(
        _load_prompt("06_discovery.md"),
        assessment=assessment,
        angle_result=angle_result,
        activity_type_context=activity_type_context or {},
        software_context=software_context or {},
    )
    return _call_claude(prompt)
