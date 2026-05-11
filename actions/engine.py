"""
Action engine — given an account memory, determine the next best action.
Returns a structured action dict ready to be stored and shown to the rep.
"""

import json
import os
from datetime import date

import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("NEXTMOVE_PLANNING_MODEL", "claude-opus-4-7")


def _load_prompt() -> str:
    with open("prompts/action_engine.md") as f:
        return f.read()


def _fill(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


def determine(account_memory: dict, vertical_context: str, excluded_angles: list[str] | None = None) -> dict:
    """
    Given the current account memory, return a next-best-action recommendation.

    Returns dict with keys: type, priority, reasoning, contact_name, contact_email,
    contact_phone, brief, primary_pain_point, strategy, wait_days
    """
    excluded = excluded_angles or []
    excluded_text = (
        "\n".join(f"- {a}" for a in excluded) if excluded else "None — no restrictions apply."
    )
    prompt = _fill(
        _load_prompt(),
        account_memory=account_memory,
        vertical_context=vertical_context,
        today=date.today().isoformat(),
        excluded_angles=excluded_text,
    )

    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Action engine returned invalid JSON: {e}\n\nRaw output:\n{text}") from e

    return {
        "type": result.get("type", "monitor"),
        "priority": result.get("priority", "normal"),
        "reasoning": result.get("reasoning", ""),
        "contact_name": result.get("contact_name"),
        "contact_email": result.get("contact_email"),
        "contact_phone": result.get("contact_phone"),
        "brief": result.get("brief", ""),
        "primary_pain_point": result.get("primary_pain_point"),
        "strategy": result.get("strategy", "discovery"),
        "wait_days": result.get("wait_days"),
    }
