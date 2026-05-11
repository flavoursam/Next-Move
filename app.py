"""NextMove web app."""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, Cookie, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

import db
import scheduler as sched
from actions import drafter as action_drafter
from actions import engine as action_engine
from memory import updater as mem_updater
from pipeline.close_write import create_email_draft, create_note
from pipeline.crm import fetch_lead
from pipeline.stages import run_assess, run_strategy, run_angle, run_action, run_draft
from run import build_rep_context, load_vertical


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler = sched.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _get_user(user_name: str | None) -> dict | None:
    if not user_name:
        return None
    return db.get_or_create_user(user_name)


# ─── Identity ─────────────────────────────────────────────────────────────────

@app.get("/identity", response_class=HTMLResponse)
def identity_page(request: Request):
    users = db.get_all_users()
    return templates.TemplateResponse(request, "identity.html", {"users": users})


@app.post("/identity")
def set_identity(name: str = Form(...)):
    name = name.strip()
    if name:
        db.get_or_create_user(name)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("user_name", name, max_age=60 * 60 * 24 * 365)
    return response


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")

    user = _get_user(user_name)
    all_seqs = db.get_all_sequences()

    for seq in all_seqs:
        seq["latest_gate"] = db.get_latest_gate_verdict(seq["id"])
        tps = db.get_touchpoints(seq["id"])
        seq["touchpoint_count"] = len(tps)

    paused = [s for s in all_seqs if s["status"] == "paused"]
    active = [s for s in all_seqs if s["status"] != "paused"]

    return templates.TemplateResponse(request, "index.html", {
        "user": user,
        "paused": paused,
        "active": active,
    })


# ─── New sequence ──────────────────────────────────────────────────────────────

@app.get("/sequence/new", response_class=HTMLResponse)
def new_sequence_page(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")
    return templates.TemplateResponse(request, "new_sequence.html", {
        "user": _get_user(user_name),
        "owner_name": os.getenv("REP_NAME", "the app owner"),
    })


@app.post("/sequence/new")
def create_sequence(
    background_tasks: BackgroundTasks,
    lead_id: str = Form(...),
    vertical: str = Form(default="tourism"),
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")

    user = db.get_or_create_user(user_name)
    seq_id = db.create_sequence(
        lead_id=lead_id.strip(),
        company_name="...",
        user_id=user["id"],
        vertical=vertical,
    )

    background_tasks.add_task(_run_pipeline, seq_id, lead_id.strip(), vertical)
    return RedirectResponse(f"/sequence/{seq_id}", status_code=303)


def _run_pipeline(seq_id: int, lead_id: str, vertical: str):
    """Run the 5-stage pipeline and store Touchpoint 1 in the DB."""
    try:
        lead = fetch_lead(lead_id)

        opp_value = None
        if lead.get("opportunities"):
            opp_value = lead["opportunities"][0].get("value_usd")

        db.update_sequence_lead_info(seq_id, lead["company_name"], opp_value)

        vertical_context, vertical_signals = load_vertical(vertical)
        rep_context = build_rep_context()

        assessment = run_assess(lead, vertical_context, vertical_signals)
        strategy = run_strategy(assessment)
        angle = run_angle(assessment, strategy)
        action = run_action(assessment, strategy, angle)
        draft = run_draft(assessment, strategy, angle, action, rep_context)

        db.create_touchpoint(
            sequence_id=seq_id,
            number=1,
            lead_snapshot=lead,
            assessment=assessment,
            strategy=strategy,
            angle=angle,
            action=action,
            draft=draft,
        )

        db.update_sequence_status(seq_id, "pending")

    except Exception as e:
        db.update_sequence_error(seq_id, str(e))


# ─── Sequence detail ──────────────────────────────────────────────────────────

@app.get("/sequence/{seq_id}", response_class=HTMLResponse)
def sequence_detail(
    request: Request,
    seq_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")

    seq = db.get_sequence(seq_id)
    if not seq:
        return HTMLResponse("Sequence not found", status_code=404)

    raw_touchpoints = db.get_touchpoints(seq_id)
    gate_verdicts = db.get_gate_verdicts(seq_id)

    touchpoints = []
    for tp in raw_touchpoints:
        t = dict(tp)
        for field in ["lead_snapshot", "assessment", "strategy", "angle", "action", "draft"]:
            if t.get(field):
                try:
                    t[field] = json.loads(t[field])
                except Exception:
                    pass
        touchpoints.append(t)

    last_tp = touchpoints[-1] if touchpoints else None

    return templates.TemplateResponse(request, "sequence.html", {
        "user": _get_user(user_name),
        "seq": seq,
        "touchpoints": touchpoints,
        "gate_verdicts": gate_verdicts,
        "last_tp": last_tp,
    })


@app.post("/sequence/{seq_id}/approve/{tp_id}")
def approve_touchpoint(
    seq_id: int,
    tp_id: int,
    edited_content: Optional[str] = Form(default=None),
    user_name: Optional[str] = Cookie(default=None),
):
    tp = db.get_touchpoint(tp_id)
    if not tp:
        return HTMLResponse("Touchpoint not found", status_code=404)

    tp = dict(tp)
    draft = json.loads(tp["draft"]) if tp.get("draft") else {}
    action = json.loads(tp["action"]) if tp.get("action") else {}
    lead_snapshot = json.loads(tp["lead_snapshot"]) if tp.get("lead_snapshot") else {}

    lead_id = lead_snapshot.get("lead_id", "")
    action_type = action.get("recommended_action", "email")
    content = (edited_content or "").strip() or None
    close_activity_id = None

    if action_type == "email":
        email_data = draft.get("email") or {}
        subject = email_data.get("subject", "")
        body = content or email_data.get("body", "")
        close_activity_id = create_email_draft(
            lead_id,
            action.get("contact_email"),
            subject,
            body,
        )

    elif action_type in ("cold_call", "voicemail"):
        call_data = draft.get("call") or {}
        script = content or call_data.get("script") or call_data.get("voicemail") or ""
        tp_num = tp["number"]
        label = "Call Script" if action_type == "cold_call" else "Voicemail Script"
        close_activity_id = create_note(
            lead_id,
            f"[NextMove {label} — Touchpoint {tp_num}]\n\n{script}",
        )

    elif action_type == "linkedin":
        li_data = draft.get("linkedin") or {}
        message = content or li_data.get("message", "")
        close_activity_id = create_note(
            lead_id,
            f"[NextMove LinkedIn — Touchpoint {tp['number']}]\n\n{message}",
        )

    db.approve_touchpoint(tp_id, close_activity_id, edited_content)
    db.update_sequence_status(seq_id, "active")
    db.update_last_checked(seq_id, _now())

    return RedirectResponse(f"/sequence/{seq_id}", status_code=303)


@app.post("/sequence/{seq_id}/reject/{tp_id}")
def reject_touchpoint(seq_id: int, tp_id: int):
    db.reject_touchpoint(tp_id)
    db.update_sequence_status(seq_id, "cancelled")
    return RedirectResponse(f"/sequence/{seq_id}", status_code=303)


@app.post("/sequence/{seq_id}/next")
def generate_next_touchpoint(
    background_tasks: BackgroundTasks,
    seq_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    seq = db.get_sequence(seq_id)
    if not seq:
        return HTMLResponse("Not found", status_code=404)

    last_tp = db.get_last_touchpoint(seq_id)
    next_number = (last_tp["number"] + 1) if last_tp else 1

    db.update_sequence_status(seq_id, "generating")
    background_tasks.add_task(
        _run_pipeline_touchpoint,
        seq_id,
        seq["lead_id"],
        seq["vertical"],
        next_number,
    )

    return RedirectResponse(f"/sequence/{seq_id}", status_code=303)


def _run_pipeline_touchpoint(seq_id: int, lead_id: str, vertical: str, number: int):
    """Generate a subsequent touchpoint for an existing sequence."""
    try:
        lead = fetch_lead(lead_id)
        vertical_context, vertical_signals = load_vertical(vertical)
        rep_context = build_rep_context()

        assessment = run_assess(lead, vertical_context, vertical_signals)
        strategy = run_strategy(assessment)
        angle = run_angle(assessment, strategy)
        action = run_action(assessment, strategy, angle)
        draft = run_draft(assessment, strategy, angle, action, rep_context)

        db.create_touchpoint(
            sequence_id=seq_id,
            number=number,
            lead_snapshot=lead,
            assessment=assessment,
            strategy=strategy,
            angle=angle,
            action=action,
            draft=draft,
        )

        db.update_sequence_status(seq_id, "pending")
    except Exception as e:
        db.update_sequence_error(seq_id, str(e))


# ─── Accounts (new intelligence system) ──────────────────────────────────────

@app.get("/accounts", response_class=HTMLResponse)
def accounts_list(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")

    accounts = db.get_all_accounts()
    for acc in accounts:
        acc["pending_action"] = db.get_pending_action(acc["id"])
        mem = db.get_current_memory(acc["id"])
        acc["memory_summary"] = mem["memory"].get("summary", "") if mem else None
        acc["memory_version"] = mem["memory"].get("memory_version", 0) if mem else 0

    return templates.TemplateResponse(request, "accounts.html", {
        "user": _get_user(user_name),
        "accounts": accounts,
    })


@app.get("/accounts/new", response_class=HTMLResponse)
def new_account_page(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")
    return templates.TemplateResponse(request, "new_account.html", {
        "user": _get_user(user_name),
    })


@app.post("/accounts/new")
def create_account(
    background_tasks: BackgroundTasks,
    lead_id: str = Form(...),
    vertical: str = Form(default="tourism"),
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")

    lead_id = lead_id.strip()

    existing = db.get_account_by_lead_id(lead_id)
    if existing:
        return RedirectResponse(f"/accounts/{existing['id']}", status_code=303)

    account_id = db.create_account(
        crm_lead_id=lead_id,
        company_name="...",
        vertical=vertical,
    )

    background_tasks.add_task(_init_account, account_id, lead_id, vertical)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


def _init_account(account_id: int, lead_id: str, vertical: str):
    """Build the initial memory and first action for a new account."""
    try:
        lead = fetch_lead(lead_id)
        vertical_context, vertical_signals = load_vertical(vertical)

        with db.get_conn() as conn:
            conn.execute(
                "UPDATE accounts SET company_name = ? WHERE id = ?",
                (lead["company_name"], account_id),
            )

        assessment = run_assess(lead, vertical_context, vertical_signals)
        initial_memory = mem_updater.init(assessment, lead, vertical_context)
        mem_id = db.save_memory(account_id, initial_memory)

        action = action_engine.determine(initial_memory, vertical_context)
        db.create_action(
            account_id=account_id,
            memory_id=mem_id,
            type=action["type"],
            priority=action["priority"],
            reasoning=action["reasoning"],
            payload=action,
        )

    except Exception as e:
        db.set_account_error(account_id, str(e))


@app.get("/accounts/{account_id}", response_class=HTMLResponse)
def account_detail(
    request: Request,
    account_id: int,
    user_name: Optional[str] = Cookie(default=None),
    approved: Optional[str] = None,
    angle: Optional[str] = None,
    rethink_exhausted: Optional[str] = None,
):
    if not user_name:
        return RedirectResponse("/identity")

    account = db.get_account(account_id)
    if not account:
        return HTMLResponse("Account not found", status_code=404)

    mem_row = db.get_current_memory(account_id)
    memory = mem_row["memory"] if mem_row else None
    pending_action = db.get_pending_action(account_id)

    if pending_action and not pending_action.get("draft") and mem_row:
        try:
            draft = action_drafter.generate(mem_row["memory"], pending_action["payload"], build_rep_context())
            with db.get_conn() as conn:
                conn.execute("UPDATE actions SET draft = ? WHERE id = ?",
                             (json.dumps(draft), pending_action["id"]))
            pending_action["draft"] = draft
        except Exception:
            pass

    fresh_action = db.get_fresh_action(account_id)
    action_history = db.get_action_history(account_id)
    signals = db.get_all_signals(account_id)[:20]
    rethink_count = db.get_rethink_count(account_id)

    return templates.TemplateResponse(request, "account.html", {
        "user": _get_user(user_name),
        "account": account,
        "memory": memory,
        "pending_action": pending_action,
        "fresh_action": fresh_action,
        "action_history": action_history,
        "signals": signals,
        "rethink_count": rethink_count,
        "max_rethinks": MAX_RETHINKS,
        "just_approved": approved == "1",
        "approved_angle": angle or "",
        "rethink_exhausted": rethink_exhausted == "1",
    })


@app.post("/accounts/{account_id}/actions/{action_id}/approve")
def approve_account_action(
    background_tasks: BackgroundTasks,
    account_id: int,
    action_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    action = db.get_action(action_id)
    if not action or action["account_id"] != account_id:
        return HTMLResponse("Action not found", status_code=404)

    action_type = action["type"]
    is_fresh = action.get("source", "memory") == "fresh"

    if action_type in ("send_email", "call", "voicemail"):
        background_tasks.add_task(_generate_and_log_draft, account_id, action_id)
        db.approve_action(action_id)
        if not is_fresh:
            contact = action["payload"].get("contact_name")
            pain_point = action["payload"].get("primary_pain_point")
            background_tasks.add_task(_log_outreach_to_memory, account_id, action_type, contact, pain_point)
    else:
        db.approve_action(action_id)

    angle_label = action["payload"].get("primary_pain_point", "")
    redirect_url = f"/accounts/{account_id}?approved=1"
    if angle_label:
        redirect_url += f"&angle={angle_label[:80]}"
    return RedirectResponse(redirect_url, status_code=303)


def _log_outreach_to_memory(account_id: int, action_type: str, contact_name: str | None, pain_point: str | None = None):
    """Directly update memory to record that outreach was sent, without a Claude call."""
    try:
        mem_row = db.get_current_memory(account_id)
        if not mem_row:
            return

        memory = dict(mem_row["memory"])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        engagement = dict(memory.get("engagement_history", {}))
        engagement["last_contact_attempt"] = today
        engagement["total_touchpoints"] = engagement.get("total_touchpoints", 0) + 1
        memory["engagement_history"] = engagement

        # Mark the used angle on the matching pain point
        if pain_point:
            for pp in memory.get("pain_points", []):
                if pp.get("point") == pain_point:
                    pp["used_as_angle"] = True
                    pp["last_used_as_angle"] = today
                    pp["outcome"] = "sent"
                    break

        memory["last_updated"] = today

        db.save_memory(account_id, memory)
        db.save_signal(account_id, "nextmove", "outreach_sent", {
            "date": today,
            "action_type": action_type,
            "note": f"Outreach approved via NextMove ({action_type})" + (f" to {contact_name}" if contact_name else ""),
        })
        if pain_point:
            db.save_signal(account_id, "nextmove", "angle_used", {
                "date": today,
                "pain_point": pain_point,
                "action_type": action_type,
            })
    except Exception:
        pass


def _generate_and_log_draft(account_id: int, action_id: int):
    """Generate the outreach draft and log it to Close CRM."""
    try:
        action = db.get_action(action_id)
        if not action:
            return

        payload = action["payload"]
        rep_context = build_rep_context()
        is_fresh = action.get("source", "memory") == "fresh"

        # Fresh actions already have a complete draft in the payload
        if is_fresh:
            draft = payload.get("draft", {})
        else:
            mem_row = db.get_current_memory(account_id)
            if not mem_row:
                return
            draft = action_drafter.generate(mem_row["memory"], payload, rep_context)

        with db.get_conn() as conn:
            conn.execute(
                "UPDATE actions SET draft = ? WHERE id = ?",
                (json.dumps(draft), action_id),
            )

        lead_id = db.get_account(account_id)["crm_lead_id"]
        action_type = action["type"]

        if action_type == "send_email":
            email = draft.get("email") or {}
            create_email_draft(
                lead_id,
                payload.get("contact_email"),
                email.get("subject", ""),
                email.get("body", ""),
            )
        elif action_type in ("call", "voicemail"):
            call = draft.get("call") or {}
            script = call.get("script") or call.get("voicemail") or ""
            label = "Call Script" if action_type == "call" else "Voicemail Script"
            create_note(lead_id, f"[NextMove {label}]\n\n{script}")

    except Exception:
        pass


@app.post("/accounts/{account_id}/actions/{action_id}/reject")
def reject_account_action(account_id: int, action_id: int):
    action = db.get_action(action_id)
    if action and action["account_id"] == account_id:
        db.reject_action(action_id)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


MAX_RETHINKS = 3

@app.post("/accounts/{account_id}/actions/{action_id}/rethink")
def rethink_account_action(
    background_tasks: BackgroundTasks,
    account_id: int,
    action_id: int,
):
    action = db.get_action(action_id)
    if not action or action["account_id"] != account_id:
        return HTMLResponse("Action not found", status_code=404)

    rethink_count = db.get_rethink_count(account_id)
    if rethink_count >= MAX_RETHINKS:
        return RedirectResponse(f"/accounts/{account_id}?rethink_exhausted=1", status_code=303)

    db.mark_action_rethink(action_id)
    db.set_account_rethinking(account_id, True)
    background_tasks.add_task(_run_rethink, account_id)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


def _run_rethink(account_id: int):
    """Generate a new action+draft for an account, excluding previously tried angles."""
    try:
        account = db.get_account(account_id)
        if not account:
            return

        mem_row = db.get_current_memory(account_id)
        if not mem_row:
            db.set_account_rethinking(account_id, False)
            return

        vertical = account.get("vertical", "tourism")
        try:
            vertical_context, _ = load_vertical(vertical)
        except FileNotFoundError:
            db.set_account_rethinking(account_id, False)
            return

        excluded = db.get_excluded_angles(account_id)
        action = action_engine.determine(mem_row["memory"], vertical_context, excluded_angles=excluded)

        try:
            draft = action_drafter.generate(mem_row["memory"], action, build_rep_context())
        except Exception:
            draft = None

        mem_id = mem_row["id"]
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
    except Exception:
        pass
    finally:
        db.set_account_rethinking(account_id, False)


@app.post("/accounts/{account_id}/reinit-memory")
def reinit_account_memory(background_tasks: BackgroundTasks, account_id: int):
    """Re-fetch lead from Close, re-run Stage 1, and rebuild memory from scratch."""
    account = db.get_account(account_id)
    if not account:
        return HTMLResponse("Account not found", status_code=404)
    background_tasks.add_task(_reinit_memory, account_id)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


def _reinit_memory(account_id: int):
    try:
        account = db.get_account(account_id)
        if not account:
            return
        db.clear_memory(account_id)
        db.expire_pending_actions(account_id)
        lead = fetch_lead(account["crm_lead_id"])
        vertical = account.get("vertical", "tourism")
        vertical_context, vertical_signals = load_vertical(vertical)
        assessment = run_assess(lead, vertical_context, vertical_signals)
        initial_memory = mem_updater.init(assessment, lead, vertical_context)
        mem_id = db.save_memory(account_id, initial_memory)
        excluded = db.get_excluded_angles(account_id)
        action = action_engine.determine(initial_memory, vertical_context, excluded_angles=excluded)
        try:
            draft = action_drafter.generate(initial_memory, action, build_rep_context())
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
    except Exception as e:
        db.set_account_error(account_id, str(e))


@app.post("/accounts/{account_id}/refresh")
def refresh_account(
    background_tasks: BackgroundTasks,
    account_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    """Manually trigger signal ingestion + memory update + website re-scrape."""
    account = db.get_account(account_id)
    if not account:
        return HTMLResponse("Account not found", status_code=404)

    background_tasks.add_task(_refresh_account_intelligence, account_id, rescrape_website=True)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


@app.post("/accounts/{account_id}/run-fresh")
def run_fresh_pipeline(
    background_tasks: BackgroundTasks,
    account_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    """Run the full 5-stage pipeline against current CRM data, independent of account memory."""
    account = db.get_account(account_id)
    if not account:
        return HTMLResponse("Account not found", status_code=404)

    db.set_account_fresh_running(account_id, True)
    background_tasks.add_task(_run_fresh_account, account_id)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


_CHANNEL_TO_TYPE = {
    "email": "send_email",
    "cold_call": "call",
    "voicemail": "voicemail",
    "linkedin": "monitor",
    "research": "monitor",
}


def _run_fresh_account(account_id: int):
    """Run all 5 pipeline stages against live CRM data. Does not touch account memory."""
    account = db.get_account(account_id)
    if not account:
        return

    lead_id = account["crm_lead_id"]
    vertical = account.get("vertical", "tourism")

    try:
        vertical_context, vertical_signals = load_vertical(vertical)
        lead = fetch_lead(lead_id)

        assessment = run_assess(lead, vertical_context, vertical_signals)
        strategy_result = run_strategy(assessment)
        angle_result = run_angle(assessment, strategy_result)
        action_result = run_action(assessment, strategy_result, angle_result)
        draft = run_draft(assessment, strategy_result, angle_result, action_result, build_rep_context())

        action_type = _CHANNEL_TO_TYPE.get(
            action_result.get("recommended_action", "email"), "send_email"
        )
        reasoning = action_result.get("reasoning", angle_result.get("why_now", ""))

        db.expire_fresh_actions(account_id)
        db.create_action(
            account_id=account_id,
            memory_id=None,
            type=action_type,
            priority="normal",
            reasoning=reasoning,
            payload={
                "assessment": assessment,
                "strategy_result": strategy_result,
                "angle_result": angle_result,
                "action_result": action_result,
                "draft": draft,
                "contact_name": action_result.get("contact_name"),
                "contact_email": action_result.get("contact_email"),
                "contact_phone": action_result.get("contact_phone"),
            },
            source="fresh",
        )

        # Pre-generate the memory-based draft so both sides are ready for comparison
        pending = db.get_pending_action(account_id)
        if pending and not pending.get("draft"):
            mem_row = db.get_current_memory(account_id)
            if mem_row:
                try:
                    mem_draft = action_drafter.generate(
                        mem_row["memory"], pending["payload"], build_rep_context()
                    )
                    with db.get_conn() as conn:
                        conn.execute(
                            "UPDATE actions SET draft = ? WHERE id = ?",
                            (json.dumps(mem_draft), pending["id"]),
                        )
                except Exception:
                    pass

    except Exception:
        pass
    finally:
        db.set_account_fresh_running(account_id, False)


def _refresh_account_intelligence(account_id: int, rescrape_website: bool = False):
    """Ingest new signals, optionally re-scrape website, update memory, generate new action."""
    from signals import ingestor
    from pipeline.website import fetch_website_signals

    account = db.get_account(account_id)
    if not account:
        return

    vertical = account.get("vertical", "tourism")
    try:
        vertical_context, _ = load_vertical(vertical)
    except FileNotFoundError:
        return

    try:
        new_signals = ingestor.ingest(account_id)

        # Re-scrape website on manual refresh and add a signal if booking software changed
        if rescrape_website:
            current_mem = db.get_current_memory(account_id)
            if current_mem:
                website_url = current_mem["memory"].get("account_context", {}).get("website")
                if website_url:
                    ws = fetch_website_signals(website_url)
                    if not ws.get("fetch_error"):
                        mem_software = current_mem["memory"].get("account_context", {}).get("current_software")
                        detected = ws.get("detected_software")
                        if detected and detected != mem_software:
                            db.save_signal(account_id, "website", "website_update", {
                                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                "note": f"Website now shows {detected} as booking software (was: {mem_software or 'unknown'})",
                            })
                            new_signals = db.get_unprocessed_signals(account_id)

        if not new_signals:
            return

        current_mem = db.get_current_memory(account_id)
        if not current_mem:
            return

        updated_memory = mem_updater.update(current_mem["memory"], new_signals, vertical_context)
        first_signal_id = new_signals[0].get("id")
        mem_id = db.save_memory(account_id, updated_memory, first_signal_id)
        db.mark_signals_processed(account_id)

        action = action_engine.determine(updated_memory, vertical_context)
        db.expire_pending_actions(account_id)
        db.create_action(
            account_id=account_id,
            memory_id=mem_id,
            type=action["type"],
            priority=action["priority"],
            reasoning=action["reasoning"],
            payload=action,
        )
    except Exception:
        pass


# ─── Commission ───────────────────────────────────────────────────────────────

@app.get("/commission", response_class=HTMLResponse)
def commission_page(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")

    user = _get_user(user_name)
    events = db.get_commission_events()
    my_events = [e for e in events if e.get("user_name") == user_name]
    total = sum(e["commission_amount"] or 0 for e in events)
    my_total = sum(e["commission_amount"] or 0 for e in my_events)

    return templates.TemplateResponse(request, "commission.html", {
        "user": user,
        "owner_name": os.getenv("REP_NAME", "the app owner"),
        "events": events,
        "my_events": my_events,
        "total": total,
        "my_total": my_total,
    })


# ─── Admin ────────────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")

    stats = db.get_manager_stats()
    return templates.TemplateResponse(request, "admin.html", {
        "user": _get_user(user_name),
        "stats": stats,
    })


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
