from typing import Optional
"""Write email drafts and CRM notes to Close.io."""

import os

import requests

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
CLOSE_BASE_URL = "https://api.close.com/api/v1"


def create_email_draft(
    lead_id: str,
    contact_email: Optional[str],
    subject: str,
    body: str,
) -> Optional[str]:
    """Create an email draft on a Close lead. Returns the Close activity ID."""
    payload: dict = {
        "lead_id": lead_id,
        "status": "draft",
        "subject": subject,
        "body_text": body,
    }
    if contact_email:
        payload["to"] = [{"email": contact_email}]

    resp = requests.post(
        f"{CLOSE_BASE_URL}/activity/email/",
        auth=(CLOSE_API_KEY, ""),
        json=payload,
        timeout=15,
    )
    if resp.ok:
        return resp.json().get("id")
    return None


def create_note(lead_id: str, note_text: str) -> Optional[str]:
    """Create a CRM note on a Close lead. Returns the Close activity ID."""
    resp = requests.post(
        f"{CLOSE_BASE_URL}/activity/note/",
        auth=(CLOSE_API_KEY, ""),
        json={"lead_id": lead_id, "note": note_text},
        timeout=15,
    )
    if resp.ok:
        return resp.json().get("id")
    return None
