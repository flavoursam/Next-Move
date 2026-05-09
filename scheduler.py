"""
Background scheduler — polls Close every 15 minutes for active sequences.
Runs the gate classifier and detects demo bookings.
"""

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import db
from pipeline import gate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_sequences():
    """
    Called every 15 minutes.
    For each active sequence: run the gate, detect demos, update sequence state.
    """
    sequences = db.get_active_sequences()

    for seq in sequences:
        since = seq["last_checked_at"] or seq["created_at"]
        lead_id = seq["lead_id"]
        seq_id = seq["id"]

        try:
            result = gate.classify(lead_id, since)
        except Exception:
            db.update_last_checked(seq_id, _now())
            continue

        verdict = result["verdict"]

        if verdict != "continue":
            last_tp_num = db.get_last_approved_touchpoint_number(seq_id) or 0
            db.save_gate_verdict(
                sequence_id=seq_id,
                after_touchpoint_number=last_tp_num,
                verdict=verdict,
                reason=result["reason"],
                key_signals=result.get("key_signals", []),
            )

            if verdict == "pause":
                db.pause_sequence(seq_id)

        if result.get("demo_landed") and not db.has_commission_event(seq_id):
            opp_value = seq.get("opportunity_value_usd") or 0
            db.save_commission_event(
                sequence_id=seq_id,
                lead_id=lead_id,
                company_name=seq["company_name"],
                user_id=seq["user_id"],
                opportunity_value_usd=opp_value,
                commission_amount=round(opp_value * 0.1, 2),
            )

        db.update_last_checked(seq_id, _now())


def start() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_sequences, "interval", hours=12, id="gate_check")
    scheduler.start()
    return scheduler
