"""Writes the final NextMove pipeline output to a JSON file in output/."""

import json
import os
import re
from datetime import date


def _slugify(name: str) -> str:
    """'Garden City Helicopters' → 'garden_city_helicopters'"""
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def write_output(
    lead: dict,
    strategy_result: dict,
    action_result: dict,
    draft_result: dict,
) -> str:
    """
    Assemble the final output dict and write it to output/{slug}_{YYYYMMDD}.json.
    Appends _2, _3, etc. if the file already exists to avoid overwriting.
    Returns the path of the file written.
    """
    slug = _slugify(lead.get("company_name", "unknown"))
    today = date.today().strftime("%Y%m%d")
    base = f"output/{slug}_{today}"

    # Find an available filename
    path = f"{base}.json"
    counter = 2
    while os.path.exists(path):
        path = f"{base}_{counter}.json"
        counter += 1

    output = {
        "company": lead.get("company_name"),
        "lead_id": lead.get("lead_id"),
        "date": date.today().isoformat(),
        "priority": strategy_result.get("priority"),
        "strategy": strategy_result.get("selected_strategy"),
        "summary": draft_result.get("summary"),
        "recommended_action": action_result.get("recommended_action"),
        "contact_name": action_result.get("contact_name"),
        "reasoning": action_result.get("reasoning"),
        "why_now": draft_result.get("why_now"),
        # Outreach assets — only the relevant one will be populated
        "email": draft_result.get("email"),    # {"subject": "", "body": ""}
        "call": draft_result.get("call"),      # {"opening": "", "script": "", "voicemail": ""}
        "linkedin": draft_result.get("linkedin"),  # {"message": ""}
        "rep_notes": draft_result.get("rep_notes", []),
    }

    os.makedirs("output", exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    return path
