"""
Close.io CRM connector.

─── Authentication ───────────────────────────────────────────────────────────
Close uses HTTP Basic Auth. Your API key is the username; the password is empty.
This is standard — the requests library handles the encoding automatically.

The API key is loaded from CLOSE_API_KEY in your .env file.
It is never written in this file or any other code file.

─── How to find your API key ─────────────────────────────────────────────────
app.close.com → Settings (bottom left) → API Keys → Create API Key

─── How to find a lead ID ────────────────────────────────────────────────────
Open any lead in Close. The ID is in the URL:
  app.close.com/lead/lead_abc123XYZetc/
Copy everything after /lead/ and before the trailing slash.
Put it in .env as TEST_LEAD_ID.

─── Close API docs ───────────────────────────────────────────────────────────
developer.close.com
"""

import os
import re
from datetime import datetime, timezone

import requests

from pipeline.website import fetch_website_signals

# os.getenv() reads CLOSE_API_KEY from the environment.
# load_dotenv() in run.py put it there from your .env file.
# If it's None here, it means either .env wasn't loaded or the key wasn't set.
CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")

CLOSE_BASE_URL = "https://api.close.com/api/v1"

# Only keep activity from the last 12 months — older data adds noise without value
ACTIVITY_LOOKBACK_DAYS = 365


def fetch_lead(lead_id: str) -> dict:
    """
    Fetch one lead from Close.io by ID and return a normalized NextMove lead dict.

    Args:
        lead_id: Close lead ID string, e.g. "lead_abc123XYZetc"

    Returns:
        dict matching the NextMove lead schema (see _normalize below)

    Raises:
        ValueError: if the API key is missing, invalid, or the lead is not found
    """
    if not CLOSE_API_KEY:
        raise ValueError(
            "CLOSE_API_KEY is not set.\n"
            "Add it to your .env file. Get your key at: app.close.com → Settings → API Keys"
        )

    # auth=(username, password) — Close uses the API key as the username, password is blank
    response = requests.get(
        f"{CLOSE_BASE_URL}/lead/{lead_id}/",
        auth=(CLOSE_API_KEY, ""),
        timeout=15,
    )

    if response.status_code == 401:
        raise ValueError(
            "Close API key was rejected (401 Unauthorized).\n"
            "Check that CLOSE_API_KEY in .env is correct and hasn't expired."
        )
    if response.status_code == 404:
        raise ValueError(
            f"Lead not found: {lead_id}\n"
            "Check TEST_LEAD_ID in .env. Make sure you copied the full ID from the Close URL."
        )
    if not response.ok:
        raise ValueError(f"Close API error {response.status_code}: {response.text[:300]}")

    return _normalize(response.json())


def _parse_tier(raw) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    try:
        return int(s)
    except ValueError:
        m = re.search(r'\d+', s)
        return int(m.group()) if m else None


def _normalize(raw: dict) -> dict:
    """
    Convert the raw Close API response into the NextMove lead schema.

    Only extracts fields the pipeline actually uses.
    Does not invent data — uses None or [] for missing fields.
    """
    contacts = _extract_contacts(raw)
    activities = _extract_recent_activities(raw, contacts)
    opportunities = _extract_opportunities(raw)
    custom = _map_custom_fields(raw)
    tier = _parse_tier(custom.get("tier"))

    last_activity_date = activities[0]["date"] if activities else None
    days_since_activity = _days_since(last_activity_date)
    website = raw.get("url")

    current_software = custom.get("current_software")
    if isinstance(current_software, list):
        current_software = ", ".join(current_software) if current_software else None

    return {
        "lead_id": raw.get("id"),
        "company_name": raw.get("display_name"),
        "website": website,
        "tier": tier,
        "predicted_tier": custom.get("predicted_tier"),
        "lead_qualification": custom.get("lead_qualification"),
        "fit": custom.get("fit"),
        "lead_type": custom.get("lead_type"),
        "client_segments": custom.get("client_segments"),
        "primary_types": custom.get("primary_types"),
        "industry": custom.get("lead_type"),  # best available proxy for industry
        "location": _extract_location(raw, custom),
        "language": custom.get("language_primary"),
        "contacts": contacts,
        "crm_notes": [a["note"] for a in activities if a.get("note")],
        "recent_activity": activities,
        "opportunities": opportunities,
        "status": raw.get("status_label"),
        "current_software": current_software,
        "tripadvisor_review_count": custom.get("tripadvisor_review_count"),
        "google_review_count": custom.get("google_review_count"),
        "semrush_organic_traffic": custom.get("semrush_organic_traffic"),
        "predicted_opp_value": custom.get("predicted_opp_value"),
        "lifetime_booking_fees": custom.get("lifetime_booking_fees"),
        "am_note": custom.get("am_note"),
        "sales_ops_note": custom.get("sales_ops_note"),
        "sales_latest_call": custom.get("sales_latest_call"),
        "sales_closed_date": custom.get("sales_closed_date"),
        "client_activation_date": custom.get("client_activation_date"),
        "client_churn_date": custom.get("client_churn_date"),
        "client_churn_reasons": custom.get("client_churn_reasons"),
        "fh_webinars_attended": custom.get("fh_webinars_attended"),
        "fh_webinars_registered": custom.get("fh_webinars_registered"),
        "last_activity_date": last_activity_date,
        "days_since_activity": days_since_activity,
        "known_facts": [],
        "website_signals": fetch_website_signals(website) if website and (tier is None or tier < 3) else {},
    }


def _extract_contacts(raw: dict) -> list[dict]:
    """Extract contacts and flag any with DNC signals in their name or title."""
    contacts = []
    for c in raw.get("contacts", []):
        emails = [e["email"] for e in c.get("emails", []) if e.get("email")]
        phones = [p["phone"] for p in c.get("phones", []) if p.get("phone")]
        contacts.append({
            "name": c.get("display_name"),
            "title": c.get("title"),
            "email": emails[0] if emails else None,
            "phone": phones[0] if phones else None,
            "dnc": False,  # updated by _extract_recent_activities if a DNC note is found
        })
    return contacts


def _extract_recent_activities(raw: dict, contacts: list[dict]) -> list[dict]:
    """
    Extract activities from the last ACTIVITY_LOOKBACK_DAYS days.
    Also scans note text for DNC signals and marks the relevant contact.
    Returns activities sorted newest first, capped at 20 entries.
    """
    cutoff = datetime.now(timezone.utc).replace(
        year=datetime.now(timezone.utc).year - 1
    )

    activities = []
    for a in raw.get("activity", []):
        date_str = a.get("date_created") or a.get("date")
        if not date_str:
            continue

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if date < cutoff:
            continue

        note_text = (
            a.get("note")
            or a.get("subject")
            or a.get("body_text", "")
        )[:300]  # cap length to avoid huge email bodies clogging context

        # Flag DNC contacts based on note content
        note_lower = note_text.lower()
        dnc_phrases = ["do not contact", "dnc", "asked off", "remove from database", "don't call", "not to be contacted"]
        if any(phrase in note_lower for phrase in dnc_phrases):
            # Try to match the DNC to a specific contact name mentioned in the note
            for contact in contacts:
                if contact["name"] and contact["name"].lower() in note_lower:
                    contact["dnc"] = True

        activities.append({
            "type": a.get("_type", "").lower(),
            "date": date_str[:10],
            "note": note_text,
        })

    activities.sort(key=lambda x: x["date"], reverse=True)
    return activities[:20]


def _extract_opportunities(raw: dict) -> list[dict]:
    """Extract opportunity records with value, status, and confidence."""
    opportunities = []
    for o in raw.get("opportunities", []):
        opportunities.append({
            "name": o.get("note") or o.get("lead_name"),
            "value_usd": o.get("value"),
            "status": o.get("status_label"),
            "confidence": o.get("confidence"),
        })
    return opportunities


def _extract_custom_fields(raw: dict) -> dict:
    """Pull out Close custom fields — stored as 'custom.FIELD_ID' keys in the raw response."""
    return {
        k.replace("custom.", ""): v
        for k, v in raw.items()
        if k.startswith("custom.") and v
    }


# Maps Close custom field IDs to human-readable keys used throughout the pipeline.
# To find a field ID: Close Settings → Custom Fields → click the field → copy ID from URL.
_FIELD_MAP = {
    # Account classification
    "lcf_wuks3IkYJ93mM0S2kpxldL7iwmXcXKe4DiQdHArvxWu": "tier",
    "cf_y8Ba8Pl8FsUkc7sXm0DkkHLM1Ae1OGOW4Ulkx3AliBf": "predicted_tier",
    "cf_FjcMH2YLAo6p8xen2g65YZwfwR7nXXcEQp3YfmWeD3o": "lead_qualification",
    "cf_DZ35PHMzwNol3NE01jCk406BaW1VzmWDAMiyhAzeSGH": "fit",
    "cf_0LTUb5ADPCh1ZG6RD1VRpdN1BDOf37hFJxTAA98826o": "client_segments",
    "cf_fpbxs9J81lOu406v6wGV2VS2dbLYoZDkqeEcYfvBWRA": "primary_types",
    "lcf_wOt970m1weoTzm2QxeTODqEsPwx3aIRoQqvlLUxKIcH": "lead_type",
    # Current software
    "cf_HPlNoc99E3H49Sf4Z9otFijESKcBmCz5go0pS1gJq0R": "current_software",
    # Location
    "cf_DUfHlJrrYZUDfY4EVJllUFrL0etyn4B895Ns6Kvwo5J": "countries",
    "cf_Ne8hPmZ9BOM6uA3uqVLvlHw81YDFHeZviavEbo5PhCH": "cities",
    "lcf_NunprVZs6cFtUB2PgnWd18l910RXnPt3JM2auLoJJOI": "language_primary",
    # Online presence / review signals
    "cf_gkeWmW7X5sy8KYLxEDsoKHsfKWtYVzWM79tOu4lgcTK": "tripadvisor_review_count",
    "cf_9WMIE0niFBaWcK7HvjRzF59b8YgJ5Tqd2XdSCPfHEiM": "google_review_count",
    "cf_A3sQ09JKt3siKWoyVklrsVSf6TbHuQ2RqIIGlhoptB4": "semrush_organic_traffic",
    # Opportunity / revenue
    "cf_nSWiMSI2ee5JP22MXvBzRMk3rDtO6i5WoXn6oGj0pei": "predicted_opp_value",
    "cf_gN7QeruBVYkb1nsVSYOyCqd23I9mJhrw6rRNEBxq6bh": "lifetime_booking_fees",
    # Sales notes
    "lcf_BmjhB6SUmI3xhA8g2zjJSz1xV4XoRN9g3r0eSxodN13": "am_note",
    "cf_0lLiKi6vAAfHHmSN4JUWJrd3qD34KEopHgaxLLVOudh": "sales_ops_note",
    # Sales activity dates
    "lcf_EFUPZ1xOII3rmM4IJMaTEDdKuk1R9ep9DeHd1U1F1wI": "sales_latest_call",
    "lcf_T0VHuPDQdbfzSSqaP1om4zv9oIIQ5dNVq4HvKvghqW2": "sales_closed_date",
    # Client lifecycle
    "cf_FsPT90QCTlivqgwL0l36M3F7mc5TkNbqj5f9LXOy7HZ": "client_activation_date",
    "lcf_ozjQoa5K6WByWQeWmHjUkKhRxVQUv4XX4dOd46CZaI8": "client_churn_date",
    "cf_QRTa0RKVSqbDhbxCbBbQLTWEMzjefccNoBEGOhhDsYB": "client_churn_reasons",
    # Engagement signals
    "lcf_DMZPOaIr9VPteLOC2xe9ZFfYZSiUvYBP6ElEn8Mf3IN": "fh_webinars_attended",
    "lcf_aiQBUZukIWBJdapOq2SZ5bhn0xtIQgllGomZfyGuhZt": "fh_webinars_registered",
}


def _map_custom_fields(raw: dict) -> dict:
    """
    Translate raw Close custom field IDs to human-readable keys.
    Multi-value fields (lists) are preserved as lists.
    Unknown field IDs are kept under their raw ID so no data is silently dropped.
    """
    raw_custom = _extract_custom_fields(raw)
    result = {}
    for field_id, value in raw_custom.items():
        key = _FIELD_MAP.get(field_id, field_id)
        result[key] = value
    return result


def _extract_location(raw: dict, custom: dict) -> str | None:
    """Best-effort location from addresses or custom fields."""
    addresses = raw.get("addresses", [])
    if addresses:
        parts = [
            addresses[0].get("city"),
            addresses[0].get("state"),
            addresses[0].get("country"),
        ]
        location = ", ".join(p for p in parts if p)
        if location:
            return location
    # Fall back to Close custom location fields
    cities = custom.get("cities")
    countries = custom.get("countries")
    city_str = ", ".join(cities) if isinstance(cities, list) else cities
    country_str = ", ".join(countries) if isinstance(countries, list) else countries
    parts = [p for p in [city_str, country_str] if p]
    return ", ".join(parts) if parts else None


def _days_since(date_str: str | None) -> int | None:
    """Calculate how many days ago a date string (YYYY-MM-DD) was."""
    if not date_str:
        return None
    try:
        past = datetime.fromisoformat(date_str + "T00:00:00+00:00")
        return (datetime.now(timezone.utc) - past).days
    except ValueError:
        return None


def fetch_activities_since(lead_id: str, since_iso: str) -> list[dict]:
    """
    Fetch calls and notes for a lead since a given ISO datetime string.
    Used by the gate classifier to check for meaningful activity between touchpoints.
    Calls include duration; notes include text.
    Returns activities sorted newest first.
    """
    if not CLOSE_API_KEY:
        return []

    activities = []

    call_resp = requests.get(
        f"{CLOSE_BASE_URL}/activity/call/",
        auth=(CLOSE_API_KEY, ""),
        params={"lead_id": lead_id, "date_created__gte": since_iso},
        timeout=15,
    )
    if call_resp.ok:
        for c in call_resp.json().get("data", []):
            activities.append({
                "type": "call",
                "date": (c.get("date_created") or "")[:10],
                "duration_seconds": c.get("duration"),
                "note": (c.get("note") or "")[:500],
                "direction": c.get("direction"),
                "status": c.get("status"),
            })

    note_resp = requests.get(
        f"{CLOSE_BASE_URL}/activity/note/",
        auth=(CLOSE_API_KEY, ""),
        params={"lead_id": lead_id, "date_created__gte": since_iso},
        timeout=15,
    )
    if note_resp.ok:
        for n in note_resp.json().get("data", []):
            activities.append({
                "type": "note",
                "date": (n.get("date_created") or "")[:10],
                "duration_seconds": None,
                "note": (n.get("note") or "")[:500],
            })

    email_resp = requests.get(
        f"{CLOSE_BASE_URL}/activity/email/",
        auth=(CLOSE_API_KEY, ""),
        params={"lead_id": lead_id, "date_created__gte": since_iso},
        timeout=15,
    )
    if email_resp.ok:
        for e in email_resp.json().get("data", []):
            if e.get("status") == "draft":
                continue
            activities.append({
                "type": "email",
                "date": (e.get("date_created") or "")[:10],
                "duration_seconds": None,
                "note": f"Subject: {e.get('subject', '')} | {(e.get('body_text') or '')[:1500]}",
                "direction": e.get("direction"),
            })

    activities.sort(key=lambda x: x["date"], reverse=True)
    return activities
