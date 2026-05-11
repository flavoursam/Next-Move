"""
Background scheduler.

Two loops:
  check_sequences  — legacy gate check for the old sequence/touchpoint system
  process_accounts — new account intelligence loop: ingest signals, update memory, generate actions
"""

import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import db
from pipeline import gate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Legacy sequence gate ──────────────────────────────────────────────────────

def check_sequences():
    """Gate check for the old sequence/touchpoint system."""
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


# ─── Account intelligence loop ────────────────────────────────────────────────

def process_accounts():
    """
    For each active account: ingest new signals, update memory, generate next best action.
    Runs every hour. Skips accounts with no new signals.
    """
    from signals import ingestor
    from memory import updater as mem_updater
    from actions import engine as action_engine
    from actions import drafter as action_drafter
    from run import build_rep_context
    import json

    accounts = db.get_active_accounts()

    for account in accounts:
        account_id = account["id"]
        vertical = account.get("vertical", "tourism")

        try:
            vertical_context = _load_vertical_context(vertical)
        except FileNotFoundError:
            continue

        try:
            new_signals = ingestor.ingest(account_id)
        except Exception:
            continue

        if not new_signals:
            continue

        current_mem_row = db.get_current_memory(account_id)

        try:
            if current_mem_row:
                updated_memory = mem_updater.update(
                    current_mem_row["memory"], new_signals, vertical_context
                )
            else:
                continue  # account has no memory yet — needs manual init via web UI

            first_signal_id = new_signals[0].get("id")
            mem_id = db.save_memory(account_id, updated_memory, first_signal_id)
            db.mark_signals_processed(account_id)

            action = action_engine.determine(updated_memory, vertical_context)
            rep_context = build_rep_context()
            try:
                draft = action_drafter.generate(updated_memory, action, rep_context)
            except Exception:
                draft = None
            db.expire_pending_actions(account_id)
            db.create_action(
                account_id=account_id,
                memory_id=mem_id,
                type=action["type"],
                priority=action["priority"],
                reasoning=action["reasoning"],
                payload=action,
                draft=draft,
            )

            if action.get("type") != "wait" or not action.get("wait_days"):
                continue
            db.update_account_state(account_id, "active")

        except Exception:
            continue


def _load_vertical_context(vertical: str) -> str:
    path = f"verticals/{vertical}/context.md"
    if not os.path.exists(path):
        raise FileNotFoundError(f"No vertical context for: {vertical}")
    with open(path) as f:
        return f.read()


def start() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_sequences, "interval", hours=12, id="gate_check")
    scheduler.add_job(process_accounts, "interval", hours=1, id="account_intelligence")
    scheduler.start()
    return scheduler
