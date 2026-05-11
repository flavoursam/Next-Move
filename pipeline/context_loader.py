"""
Load contextual lenses for the discovery package.

Three lenses are supported:
  1. Operator type  — verticals/{vertical}/operator_types/{type}.json
  2. Current software — verticals/{vertical}/software/{name}.json
  3. Website/conversion — stays in signals.json (loaded by load_vertical)

To add a new operator type or software, just add a file. No code changes needed.
"""

import json
import os


def load_operator_type(vertical: str, operator_type: str | None) -> dict | None:
    if not operator_type:
        return None
    key = operator_type.lower().replace(" ", "_").replace("-", "_")
    path = f"verticals/{vertical}/operator_types/{key}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_software(vertical: str, current_software: str | None) -> dict | None:
    if not current_software:
        return None
    # Use first listed software if multiple (e.g. "Rezdy, Checkfront")
    name = current_software.split(",")[0].strip().lower()
    path = f"verticals/{vertical}/software/{name}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_lenses(
    vertical: str,
    operator_type: str | None,
    current_software: str | None,
) -> tuple[dict | None, dict | None]:
    """Returns (operator_type_context, software_context). Either may be None."""
    return (
        load_operator_type(vertical, operator_type),
        load_software(vertical, current_software),
    )
