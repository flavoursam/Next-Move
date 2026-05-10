"""
Generates the actual outreach draft when a rep approves an action recommendation.
Uses the account memory as context instead of re-running the full pipeline.
Reuses Stage 5 prompt logic, adapted to take memory + action payload as inputs.
"""

import json
import os

import anthropic

from pipeline.stages import _load_prompt, _fill, _SYSTEM_PROMPT, _load_strategy

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("NEXTMOVE_MODEL", "claude-sonnet-4-6")


def generate(account_memory: dict, action: dict, rep_context: dict) -> dict:
    """
    Generate the outreach draft for an approved action.

    Feeds account memory + action brief into Stage 5 prompt.
    Returns the same draft structure Stage 5 produces.
    """
    strategy_name = action.get("strategy", "discovery")

    # Build a synthetic assessment and strategy from the memory — Stage 5 needs these shapes
    synthetic_assessment = {
        "company_summary": account_memory.get("summary", ""),
        "key_signals": account_memory.get("pain_points", []),
        "contacts": [
            {
                "name": account_memory.get("org_intelligence", {}).get("decision_maker_name"),
                "title": account_memory.get("org_intelligence", {}).get("decision_maker_title"),
                "email": account_memory.get("org_intelligence", {}).get("decision_maker_email"),
                "phone": account_memory.get("org_intelligence", {}).get("decision_maker_phone"),
                "dnc": False,
            }
        ],
        "deal_context": account_memory.get("account_context", {}),
        "gaps": [],
    }

    synthetic_strategy = {
        "selected_strategy": strategy_name,
        "priority": action.get("priority", "normal"),
        "strategy_reasoning": action.get("reasoning", ""),
        "risk_flags": [],
    }

    synthetic_angle = {
        "primary_pain_point": (account_memory.get("pain_points") or [{"point": ""}])[0].get("point", ""),
        "sales_angle": action.get("brief", ""),
        "why_now": action.get("reasoning", ""),
    }

    synthetic_action = {
        "recommended_action": action.get("type", "email"),
        "contact_name": action.get("contact_name"),
        "contact_email": action.get("contact_email"),
        "contact_phone": action.get("contact_phone"),
    }

    prompt = _fill(
        _load_prompt("05_draft.md"),
        assessment=synthetic_assessment,
        strategy_result=synthetic_strategy,
        angle_result=synthetic_angle,
        action_result=synthetic_action,
        strategy_instructions=_load_strategy(strategy_name),
        rep_context=rep_context,
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Draft generator returned invalid JSON: {e}") from e
