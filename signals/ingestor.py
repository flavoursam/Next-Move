"""
Poll Close.io for new activity on an account and store it as signals.
Deduplicates by checking last_signal_at on the account.
"""

import db
from pipeline.crm import fetch_activities_since


def ingest(account_id: int) -> list[dict]:
    """
    Fetch Close activities since last known signal, store each as a signal row.
    Returns the list of newly stored signals (may be empty).
    """
    account = db.get_account(account_id)
    if not account:
        return []

    since = account.get("last_signal_at") or account["created_at"]
    lead_id = account["crm_lead_id"]

    try:
        activities = fetch_activities_since(lead_id, since)
    except Exception:
        return []

    if not activities:
        return []

    new_signals = []
    for activity in activities:
        signal_id = db.save_signal(
            account_id=account_id,
            source="close",
            type=activity.get("type", "unknown"),
            content=activity,
        )
        new_signals.append({"id": signal_id, **activity})

    # Track the most recent signal time for next poll
    if new_signals and new_signals[0].get("date"):
        db.update_account_last_signal(account_id, new_signals[0]["date"] + "T00:00:00+00:00")

    return new_signals
