"""
Neglected account detection.

An account is neglected when no meaningful activity has occurred within the
configured threshold. Edit MEANINGFUL_ACTIVITY_RULES to adjust the definition.

Meaningful activity rules:
- Calls must be >= min_call_duration_seconds (short dials don't count)
- Emails only count if inbound (outbound with no reply = not meaningful)
- Notes containing any ignored_call_note_keywords are skipped (e.g. "cnm", "clm")
"""

from datetime import datetime, timedelta, timezone

from pipeline.crm import fetch_activities_since

MEANINGFUL_ACTIVITY_RULES = {
    "inactivity_days": 45,
    "min_call_duration_seconds": 90,
    "ignored_call_note_keywords": ["cnm", "clm"],
    "count_outbound_email_no_reply": False,
}


def is_meaningful(activity: dict, rules: dict = None) -> bool:
    """Return True if this activity counts as meaningful contact."""
    if rules is None:
        rules = MEANINGFUL_ACTIVITY_RULES

    kind = activity.get("type", "")
    note = (activity.get("note") or "").lower()
    keywords = [k.lower() for k in rules.get("ignored_call_note_keywords", [])]

    if kind == "call":
        duration = activity.get("duration_seconds") or 0
        if duration < rules["min_call_duration_seconds"]:
            return False
        if any(kw in note for kw in keywords):
            return False
        return True

    if kind == "email":
        if not rules.get("count_outbound_email_no_reply", False):
            return activity.get("direction") == "inbound"
        return True

    if kind == "note":
        if any(kw in note for kw in keywords):
            return False
        return True

    return True


def check_neglected(lead_id: str, rules: dict = None) -> tuple[bool, int | None]:
    """
    Returns (is_neglected, days_since_any_activity).

    is_neglected is True if no meaningful activity exists within rules["inactivity_days"].
    days_since_any_activity is days since the most recent activity of any type (for sorting),
    or inactivity_days if no activity found in the window.
    """
    if rules is None:
        rules = MEANINGFUL_ACTIVITY_RULES

    threshold = rules["inactivity_days"]
    since = (datetime.now(timezone.utc) - timedelta(days=threshold)).isoformat()

    try:
        activities = fetch_activities_since(lead_id, since)
    except Exception:
        return False, None  # fail safe — don't surface if we can't check

    for activity in activities:
        if is_meaningful(activity, rules):
            return False, None

    # No meaningful activity found — calculate days since most recent activity for sorting
    days_since = threshold
    if activities:
        most_recent = activities[0].get("date")
        if most_recent:
            try:
                past = datetime.fromisoformat(most_recent + "T00:00:00+00:00")
                days_since = (datetime.now(timezone.utc) - past).days
            except ValueError:
                pass

    return True, days_since
