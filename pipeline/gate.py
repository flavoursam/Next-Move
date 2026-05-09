"""
Gate classifier — decides whether a sequence should continue, warn, or pause.
Also detects demo bookings for commission tracking.
Called between touchpoints to check for meaningful CRM activity.
"""

import json
import os

import anthropic

from pipeline.crm import fetch_activities_since

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _load_prompt() -> str:
    with open("prompts/gate.md") as f:
        return f.read()


def classify(lead_id: str, since_iso: str) -> dict:
    """
    Fetch recent CRM activity and classify it.

    Returns:
        {
            "verdict": "continue | warn_continue | pause",
            "reason": str,
            "key_signals": list[str],
            "demo_landed": bool,
        }
    """
    activities = fetch_activities_since(lead_id, since_iso)

    if not activities:
        return {
            "verdict": "continue",
            "reason": "No new CRM activity since last touchpoint.",
            "key_signals": [],
            "demo_landed": False,
        }

    prompt = _load_prompt().replace("{{activities}}", json.dumps(activities, indent=2))

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
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
    except json.JSONDecodeError:
        return {
            "verdict": "continue",
            "reason": "Gate classification failed — defaulting to continue.",
            "key_signals": [],
            "demo_landed": False,
        }

    return {
        "verdict": result.get("verdict", "continue"),
        "reason": result.get("reason", ""),
        "key_signals": result.get("key_signals", []),
        "demo_landed": bool(result.get("demo_landed", False)),
    }
