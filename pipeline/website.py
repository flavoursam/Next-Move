"""
Scrape a company website for booking software signals.
Called during lead normalisation when a website URL is present.
Results are added to the lead dict and passed into Stage 1.

Important distinction:
- BOOKING_SOFTWARE: dedicated reservation systems embedded on the site (Rezdy, Checkfront, etc.)
- OTA_REVIEW_LINKS: OTA platforms linked from the site for reviews/listings only (Viator, GYG, etc.)
  These are NOT booking software — they are review badges. Do not conflate them.
"""

import requests

# Dedicated booking/reservation systems — embedded widgets, iframes, or scripts
BOOKING_SOFTWARE = {
    "FareHarbor": ["fareharbor.com", "fh.mybook.io"],
    "Rezdy": ["rezdy.com"],
    "Checkfront": ["checkfront.com"],
    "Bokun": ["bokun.io"],
    "Peek Pro": ["peekpro.com", "peek.com/tours"],
    "TrekkSoft": ["trekksoft.com"],
    "Xola": ["xola.com"],
    "Bookeo": ["bookeo.com"],
    "Regiondo": ["regiondo.com"],
}

# OTA platforms — links to these are almost always review badges or listing links,
# NOT an indication that the business uses them as booking software
OTA_REVIEW_LINKS = {
    "Viator": ["viator.com"],
    "GetYourGuide": ["getyourguide.com"],
    "Expedia Experiences": ["expedia.com/things-to-do", "activities.expedia"],
    "Klook": ["klook.com"],
    "Airbnb Experiences": ["airbnb.com/experiences"],
}

BOOK_NOW_PHRASES = [
    "book now", "book online", "book a tour", "book a trip",
    "reserve now", "make a reservation", "check availability",
    "buy tickets", "purchase tickets", "book your",
]


def fetch_website_signals(url: str) -> dict:
    """
    Fetch and analyse a company website for booking software signals.

    Returns a dict with:
        detected_software: first booking software found embedded on the site, or None
        all_detected_software: all booking software signatures found
        ota_review_links: OTA platforms linked (review badges only — NOT booking software)
        has_direct_booking: True only if a real booking system is embedded
        has_book_now_cta: True if "book now" style CTA text is present
        no_booking_detected: True if no booking software and no book-now CTA found
        fetch_error: set if the website could not be reached
    """
    if not url:
        return {"fetch_error": "No website URL provided"}

    if not url.startswith("http"):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NextMove/1.0)"},
            allow_redirects=True,
        )
        html = resp.text.lower()
    except requests.exceptions.Timeout:
        return {"fetch_error": f"Website timed out: {url}"}
    except requests.exceptions.ConnectionError:
        return {"fetch_error": f"Could not connect to website: {url}"}
    except Exception as e:
        return {"fetch_error": str(e)[:100]}

    detected_software = []
    for name, signatures in BOOKING_SOFTWARE.items():
        if any(sig in html for sig in signatures):
            detected_software.append(name)

    ota_review_links = []
    for name, signatures in OTA_REVIEW_LINKS.items():
        if any(sig in html for sig in signatures):
            ota_review_links.append(name)

    has_book_now = any(phrase in html for phrase in BOOK_NOW_PHRASES)

    return {
        "detected_software": detected_software[0] if detected_software else None,
        "all_detected_software": detected_software,
        "ota_review_links": ota_review_links,
        "has_direct_booking": len(detected_software) > 0,
        "has_book_now_cta": has_book_now,
        "no_booking_detected": not detected_software and not has_book_now,
    }
