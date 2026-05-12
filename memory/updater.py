"""
Memory agent — creates and updates account memory documents via Claude.

Two entry points:
  init(assessment, lead_snapshot, vertical_context)  → initial memory dict
  update(current_memory, new_signals, vertical_context) → updated memory dict
"""

import json
import os

import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("NEXTMOVE_PLANNING_MODEL", "claude-opus-4-7")


def _load_prompt(filename: str) -> str:
    with open(f"prompts/{filename}") as f:
        return f.read()


def _fill(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        template = template.replace(f"{{{{{key}}}}}", str(value))
    return template


_REQUIRED_KEYS = {
    "pain_points", "engagement_history", "org_intelligence",
    "buying_readiness", "account_context", "summary", "memory_version",
}
_VALID_CONFIDENCE = {"high", "medium", "low"}


def _validate(memory: dict) -> None:
    missing = _REQUIRED_KEYS - memory.keys()
    if missing:
        raise ValueError(f"Memory missing required keys: {missing}")
    if not isinstance(memory["pain_points"], list):
        raise ValueError("pain_points must be a list")
    for pp in memory["pain_points"]:
        conf = pp.get("confidence")
        if conf not in _VALID_CONFIDENCE:
            raise ValueError(f"Invalid confidence value: {conf!r}")
    if not isinstance(memory.get("memory_version"), int):
        raise ValueError("memory_version must be an int")


def _call(prompt: str) -> dict:
    response = _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    memory = json.loads(text.strip())
    _validate(memory)
    return memory


def init(assessment: dict, lead_snapshot: dict, vertical_context: str) -> dict:
    """Build the first memory document from a Stage 1 assessment and lead snapshot."""
    prompt = _fill(
        _load_prompt("memory_init.md"),
        assessment=assessment,
        lead_snapshot=lead_snapshot,
        vertical_context=vertical_context,
    )
    return _call(prompt)


def update(current_memory: dict, new_signals: list[dict], vertical_context: str) -> dict:
    """Merge new signals into existing memory. Raises ValueError if result fails validation."""
    prompt = _fill(
        _load_prompt("memory_update.md"),
        current_memory=current_memory,
        new_signals=new_signals,
        vertical_context=vertical_context,
    )
    return _call(prompt)
