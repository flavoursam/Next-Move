"""
NextMove — AI sales prioritisation pipeline.

Usage:
    python run.py                          # uses TEST_LEAD_ID from .env
    python run.py lead_abc123              # pass any Close lead ID directly
    python run.py lead_abc123 --vertical hospitality  # override vertical (default: tourism)

Flow:
    CRM fetch
      → Stage 1: Assess   (what do we know?)
      → Stage 2: Strategy (score + select Challenger / Discovery / Mid-Market)
      → Stage 3: Angle    (single pain point + insight)
      → Stage 4: Action   (channel + contact)
      → Stage 5: Draft    (write the actual email / call script / voicemail)
      → Write output file
"""

import json
import os
import sys
from dotenv import load_dotenv  # reads .env into os.environ — must run before any os.getenv()

# Load .env first so all API keys are available before we import pipeline modules
load_dotenv()

from pipeline.crm import fetch_lead
from pipeline.stages import run_assess, run_strategy, run_angle, run_action, run_draft
from pipeline.writer import write_output


def load_vertical(name: str = "tourism") -> tuple[str, dict]:
    """Load narrative context (for Claude) and structured signals (for code) for a vertical."""
    base = f"verticals/{name}"

    context_path = f"{base}/context.md"
    signals_path = f"{base}/signals.json"

    if not os.path.exists(context_path):
        raise FileNotFoundError(
            f"No vertical found: {name}\n"
            f"Expected: {context_path}\n"
            f"To add a vertical, create verticals/{name}/context.md and signals.json"
        )

    with open(context_path) as f:
        context = f.read()

    with open(signals_path) as f:
        signals = json.load(f)

    return context, signals


def parse_args() -> tuple[str, str]:
    """Parse CLI args: optional lead_id and optional --vertical flag."""
    args = sys.argv[1:]
    lead_id = None
    vertical = "tourism"

    i = 0
    while i < len(args):
        if args[i] == "--vertical" and i + 1 < len(args):
            vertical = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            lead_id = args[i]
            i += 1
        else:
            i += 1

    if not lead_id:
        # Fall back to TEST_LEAD_ID from .env
        lead_id = os.getenv("TEST_LEAD_ID")

    if not lead_id:
        print(
            "Error: no lead ID provided.\n"
            "Either pass one as an argument: python run.py lead_abc123\n"
            "Or set TEST_LEAD_ID in your .env file."
        )
        sys.exit(1)

    return lead_id, vertical


def build_rep_context() -> dict:
    """
    Load sales rep details from .env.
    These are injected into Stage 5 to personalise drafted outreach assets.
    Set REP_NAME, REP_COMPANY, REP_PHONE in your .env file.
    """
    return {
        "name": os.getenv("REP_NAME", "Sam"),
        "company": os.getenv("REP_COMPANY", "FareHarbor"),
        "phone": os.getenv("REP_PHONE", ""),
    }


def main():
    lead_id, vertical_name = parse_args()
    rep_context = build_rep_context()

    print(f"\nNextMove — fetching lead: {lead_id}")
    lead = fetch_lead(lead_id)
    print(f"Lead: {lead['company_name']} | Status: {lead['status']} | Vertical: {vertical_name}")

    print(f"\nLoading vertical: {vertical_name}")
    vertical_context, vertical_signals = load_vertical(vertical_name)

    print("\nStage 1 — Assessing lead...")
    assessment = run_assess(lead, vertical_context, vertical_signals)

    print("Stage 2 — Scoring and selecting strategy...")
    strategy_result = run_strategy(assessment)
    print(f"         Priority: {strategy_result.get('priority')} | Strategy: {strategy_result.get('selected_strategy')}")

    print("Stage 3 — Identifying angle...")
    angle_result = run_angle(assessment, strategy_result)

    print("Stage 4 — Selecting action channel...")
    action_result = run_action(assessment, strategy_result, angle_result)
    print(f"         Action: {action_result.get('recommended_action')} → {action_result.get('contact_name')}")

    print("Stage 5 — Drafting outreach asset...")
    draft_result = run_draft(assessment, strategy_result, angle_result, action_result, rep_context)

    output_path = write_output(lead, strategy_result, action_result, draft_result)
    print(f"\nDone. Output: {output_path}\n")


if __name__ == "__main__":
    main()
