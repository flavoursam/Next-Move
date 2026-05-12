"""NextMove web app."""

import asyncio
import json
import os
import subprocess
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, Cookie, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

import db
import scheduler as sched
from actions import drafter as action_drafter
from actions import engine as action_engine
from memory import updater as mem_updater
from pipeline.close_write import create_email_draft, create_note
from pipeline.context_loader import load_lenses
from pipeline.crm import fetch_lead
from pipeline.stages import run_assess, run_strategy, run_angle, run_action, run_draft, run_discovery
from run import build_rep_context, load_vertical


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler = sched.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_run_store: dict = {}

_CHANNEL_TO_TYPE = {
    "email": "send_email",
    "cold_call": "call",
    "voicemail": "voicemail",
    "linkedin": "monitor",
    "research": "monitor",
}


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


# ─── Next Touchpoint ──────────────────────────────────────────────────────────

def _add_log(run_id: str, message: str):
    if run_id in _run_store:
        _run_store[run_id]["logs"].append({"msg": message, "ts": time.time()})


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


def _run_neglected_pipeline(run_id: str, lead_id: str):
    """Run the full Next Touchpoint pipeline, logging each step to _run_store."""
    vertical = "tourism"
    try:
        _add_log(run_id, "Fetching CRM data from Close...")
        vertical_context, vertical_signals = load_vertical(vertical)
        lead = fetch_lead(lead_id)

        _add_log(run_id, f"Found: {lead.get('company_name', lead_id)}")
        _add_log(run_id, "Stage 1: Assessing lead...")
        assessment = run_assess(lead, vertical_context, vertical_signals)

        _add_log(run_id, "Stage 2: Selecting strategy...")
        strategy_result = run_strategy(assessment)

        _add_log(run_id, "Stage 3: Identifying angle...")
        angle_result = run_angle(assessment, strategy_result)

        _add_log(run_id, "Stage 4: Choosing action & contact...")
        action_result = run_action(assessment, strategy_result, angle_result)

        _add_log(run_id, "Stage 5: Drafting outreach...")
        draft = run_draft(assessment, strategy_result, angle_result, action_result, build_rep_context())

        _add_log(run_id, "Loading operator context...")
        activity_type = assessment.get("activity_type")
        current_software = (
            assessment.get("deal_context", {}).get("current_software")
            or lead.get("current_software")
        )
        activity_ctx, software_ctx = load_lenses(vertical, activity_type, current_software)

        _add_log(run_id, "Generating discovery package...")
        try:
            discovery = run_discovery(assessment, angle_result, activity_ctx, software_ctx)
        except Exception:
            discovery = None

        git_hash = _git_hash()

        _add_log(run_id, "Saving to database...")
        existing = db.get_account_by_lead_id(lead_id)
        if existing:
            account_id = existing["id"]
        else:
            account_id = db.create_account(
                crm_lead_id=lead_id,
                company_name=lead.get("company_name", "..."),
                vertical=vertical,
            )
            threading.Thread(
                target=_init_account, args=(account_id, lead_id, vertical), daemon=True
            ).start()

        action_type = _CHANNEL_TO_TYPE.get(
            action_result.get("recommended_action", "email"), "send_email"
        )
        db.expire_fresh_actions(account_id)
        db.create_action(
            account_id=account_id,
            memory_id=None,
            type=action_type,
            priority="normal",
            reasoning=action_result.get("reasoning", angle_result.get("why_now", "")),
            payload={
                "assessment": assessment,
                "strategy_result": strategy_result,
                "angle_result": angle_result,
                "action_result": action_result,
                "draft": draft,
                "discovery": discovery,
                "contact_name": action_result.get("contact_name"),
                "contact_email": action_result.get("contact_email"),
                "contact_phone": action_result.get("contact_phone"),
                "git_hash": git_hash,
            },
            source="neglected",
        )

        _run_store[run_id]["result"] = {
            "company_name": lead.get("company_name"),
            "lead_id": lead_id,
            "account_id": account_id,
            "assessment": assessment,
            "strategy_result": strategy_result,
            "angle_result": angle_result,
            "action_result": action_result,
            "draft": draft,
            "discovery": discovery,
            "recent_activity": lead.get("recent_activity", []),
            "git_hash": git_hash,
        }
        _add_log(run_id, "Done!")
        _run_store[run_id]["status"] = "done"

    except Exception as e:
        _run_store[run_id]["error"] = str(e)
        _run_store[run_id]["status"] = "error"
        _add_log(run_id, f"Error: {e}")


@app.get("/", response_class=HTMLResponse)
def next_touchpoint_page(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")
    return templates.TemplateResponse(request, "neglected.html", {
        "user": _get_user(user_name),
        "result": None,
        "error": None,
        "lead_id": "",
    })


@app.post("/", response_class=HTMLResponse)
def start_next_touchpoint(
    background_tasks: BackgroundTasks,
    request: Request,
    lead_id: str = Form(...),
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")

    run_id = str(uuid.uuid4())[:8]
    _run_store[run_id] = {"status": "running", "logs": [], "result": None, "error": None}
    background_tasks.add_task(_run_neglected_pipeline, run_id, lead_id.strip())
    return RedirectResponse(f"/run/{run_id}", status_code=303)


@app.get("/run/{run_id}", response_class=HTMLResponse)
def run_loading_page(
    request: Request,
    run_id: str,
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")
    store = _run_store.get(run_id)
    if not store:
        return HTMLResponse("Run not found", status_code=404)
    if store["status"] == "done":
        return templates.TemplateResponse(request, "neglected.html", {
            "user": _get_user(user_name),
            "result": store["result"],
            "error": None,
            "lead_id": store["result"]["lead_id"],
        })
    if store["status"] == "error":
        return templates.TemplateResponse(request, "neglected.html", {
            "user": _get_user(user_name),
            "result": None,
            "error": store["error"],
            "lead_id": "",
        })
    return templates.TemplateResponse(request, "run_loading.html", {
        "user": _get_user(user_name),
        "run_id": run_id,
    })


@app.get("/run/{run_id}/stream")
async def run_stream(run_id: str):
    async def generate():
        last_idx = 0
        while True:
            store = _run_store.get(run_id)
            if not store:
                yield 'data: {"error": "not found"}\n\n'
                return
            logs = store["logs"]
            while last_idx < len(logs):
                yield f"data: {json.dumps(logs[last_idx])}\n\n"
                last_idx += 1
            if store["status"] in ("done", "error"):
                yield f"event: done\ndata: /run/{run_id}\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Runs list ────────────────────────────────────────────────────────────────

@app.get("/runs", response_class=HTMLResponse)
def runs_list(request: Request, user_name: Optional[str] = Cookie(default=None)):
    if not user_name:
        return RedirectResponse("/identity")
    runs = db.get_runs_list()
    return templates.TemplateResponse(request, "runs.html", {
        "user": _get_user(user_name),
        "runs": runs,
    })


@app.get("/runs/{action_id}", response_class=HTMLResponse)
def run_detail(
    request: Request,
    action_id: int,
    user_name: Optional[str] = Cookie(default=None),
):
    if not user_name:
        return RedirectResponse("/identity")
    action = db.get_action(action_id)
    if not action or action.get("source") not in ("neglected", "fresh"):
        return HTMLResponse("Run not found", status_code=404)
    account = db.get_account(action["account_id"])
    if not account:
        return HTMLResponse("Account not found", status_code=404)
    p = action["payload"]
    result = {
        "company_name": account["company_name"],
        "lead_id": account["crm_lead_id"],
        "account_id": account["id"],
        "assessment": p.get("assessment", {}),
        "strategy_result": p.get("strategy_result", {}),
        "angle_result": p.get("angle_result", {}),
        "action_result": p.get("action_result", {}),
        "draft": p.get("draft"),
        "discovery": p.get("discovery"),
        "recent_activity": [],
        "git_hash": p.get("git_hash", ""),
    }
    return templates.TemplateResponse(request, "neglected.html", {
        "user": _get_user(user_name),
        "result": result,
        "error": None,
        "lead_id": account["crm_lead_id"],
    })


# ─── Accounts ─────────────────────────────────────────────────────────────────

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

        if os.getenv("CLOSE_WRITEBACK_ENABLED", "false").lower() == "true":
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
    account = db.get_account(account_id)
    if not account:
        return HTMLResponse("Account not found", status_code=404)
    db.set_account_fresh_running(account_id, True)
    background_tasks.add_task(_run_fresh_account, account_id)
    return RedirectResponse(f"/accounts/{account_id}", status_code=303)


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

        activity_type = assessment.get("activity_type")
        current_software = (
            assessment.get("deal_context", {}).get("current_software")
            or lead.get("current_software")
        )
        activity_ctx, software_ctx = load_lenses(vertical, activity_type, current_software)
        try:
            discovery = run_discovery(assessment, angle_result, activity_ctx, software_ctx)
        except Exception:
            discovery = None

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
                "discovery": discovery,
                "contact_name": action_result.get("contact_name"),
                "contact_email": action_result.get("contact_email"),
                "contact_phone": action_result.get("contact_phone"),
            },
            source="fresh",
        )

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
