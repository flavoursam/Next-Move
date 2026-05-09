"""SQLite database for NextMove — sequences, touchpoints, gate verdicts, commission."""

import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "nextmove.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT '...',
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'generating',
                vertical TEXT NOT NULL DEFAULT 'tourism',
                opportunity_value_usd INTEGER,
                last_checked_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS touchpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id INTEGER NOT NULL,
                number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                lead_snapshot TEXT NOT NULL,
                assessment TEXT,
                strategy TEXT,
                angle TEXT,
                action TEXT,
                draft TEXT,
                close_activity_id TEXT,
                edited_content TEXT,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                FOREIGN KEY (sequence_id) REFERENCES sequences(id)
            );

            CREATE TABLE IF NOT EXISTS gate_verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id INTEGER NOT NULL,
                after_touchpoint_number INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                reason TEXT NOT NULL,
                key_signals TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (sequence_id) REFERENCES sequences(id)
            );

            CREATE TABLE IF NOT EXISTS commission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id INTEGER NOT NULL,
                lead_id TEXT NOT NULL,
                company_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                opportunity_value_usd INTEGER,
                commission_amount REAL,
                detected_at TEXT NOT NULL,
                FOREIGN KEY (sequence_id) REFERENCES sequences(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)


# ─── Users ────────────────────────────────────────────────────────────────────

def get_or_create_user(name: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
        if row:
            return dict(row)
        conn.execute("INSERT INTO users (name, created_at) VALUES (?, ?)", (name, _now()))
        row = conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
        return dict(row)


def get_all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
        return [dict(r) for r in rows]


# ─── Sequences ────────────────────────────────────────────────────────────────

def create_sequence(lead_id: str, company_name: str, user_id: int, vertical: str) -> int:
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO sequences (lead_id, company_name, user_id, vertical, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lead_id, company_name, user_id, vertical, now, now),
        )
        return cur.lastrowid


def get_sequence(seq_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT s.*, u.name as user_name
               FROM sequences s JOIN users u ON u.id = s.user_id
               WHERE s.id = ?""",
            (seq_id,),
        ).fetchone()
        return dict(row) if row else None


def get_all_sequences() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.*, u.name as user_name
               FROM sequences s JOIN users u ON u.id = s.user_id
               ORDER BY s.updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_sequences() -> list[dict]:
    """Sequences currently being monitored by the gate."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.*, u.name as user_name
               FROM sequences s JOIN users u ON u.id = s.user_id
               WHERE s.status = 'active'"""
        ).fetchall()
        return [dict(r) for r in rows]


def update_sequence_status(seq_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sequences SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), seq_id),
        )


def update_sequence_lead_info(seq_id: int, company_name: str, opp_value: int | None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sequences SET company_name = ?, opportunity_value_usd = ?, updated_at = ? WHERE id = ?",
            (company_name, opp_value, _now(), seq_id),
        )


def update_sequence_error(seq_id: int, error: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sequences SET status = 'error', error_message = ?, updated_at = ? WHERE id = ?",
            (error, _now(), seq_id),
        )


def pause_sequence(seq_id: int):
    update_sequence_status(seq_id, "paused")


def update_last_checked(seq_id: int, timestamp: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sequences SET last_checked_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, _now(), seq_id),
        )


# ─── Touchpoints ──────────────────────────────────────────────────────────────

def create_touchpoint(
    sequence_id: int,
    number: int,
    lead_snapshot: dict,
    assessment: dict,
    strategy: dict,
    angle: dict,
    action: dict,
    draft: dict,
) -> int:
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO touchpoints
               (sequence_id, number, lead_snapshot, assessment, strategy, angle, action, draft, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sequence_id, number,
                json.dumps(lead_snapshot),
                json.dumps(assessment),
                json.dumps(strategy),
                json.dumps(angle),
                json.dumps(action),
                json.dumps(draft),
                now,
            ),
        )
        return cur.lastrowid


def get_touchpoints(sequence_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM touchpoints WHERE sequence_id = ? ORDER BY number",
            (sequence_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_touchpoint(tp_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM touchpoints WHERE id = ?", (tp_id,)).fetchone()
        return dict(row) if row else None


def get_last_touchpoint(sequence_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM touchpoints WHERE sequence_id = ? ORDER BY number DESC LIMIT 1",
            (sequence_id,),
        ).fetchone()
        return dict(row) if row else None


def get_last_approved_touchpoint_number(sequence_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT number FROM touchpoints
               WHERE sequence_id = ? AND status = 'approved'
               ORDER BY number DESC LIMIT 1""",
            (sequence_id,),
        ).fetchone()
        return row["number"] if row else None


def approve_touchpoint(tp_id: int, close_activity_id: str | None, edited_content: str | None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE touchpoints
               SET status = 'approved', approved_at = ?, close_activity_id = ?, edited_content = ?
               WHERE id = ?""",
            (_now(), close_activity_id, edited_content, tp_id),
        )


def reject_touchpoint(tp_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE touchpoints SET status = 'rejected' WHERE id = ?",
            (tp_id,),
        )


# ─── Gate verdicts ────────────────────────────────────────────────────────────

def save_gate_verdict(
    sequence_id: int,
    after_touchpoint_number: int,
    verdict: str,
    reason: str,
    key_signals: list,
):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO gate_verdicts
               (sequence_id, after_touchpoint_number, verdict, reason, key_signals, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sequence_id, after_touchpoint_number, verdict, reason, json.dumps(key_signals), _now()),
        )


def get_gate_verdicts(sequence_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM gate_verdicts WHERE sequence_id = ? ORDER BY created_at",
            (sequence_id,),
        ).fetchall()
        result = []
        for r in rows:
            v = dict(r)
            if v.get("key_signals"):
                try:
                    v["key_signals"] = json.loads(v["key_signals"])
                except Exception:
                    v["key_signals"] = []
            result.append(v)
        return result


def get_latest_gate_verdict(sequence_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gate_verdicts WHERE sequence_id = ? ORDER BY created_at DESC LIMIT 1",
            (sequence_id,),
        ).fetchone()
        if not row:
            return None
        v = dict(row)
        if v.get("key_signals"):
            try:
                v["key_signals"] = json.loads(v["key_signals"])
            except Exception:
                v["key_signals"] = []
        return v


# ─── Commission ───────────────────────────────────────────────────────────────

def has_commission_event(sequence_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM commission_events WHERE sequence_id = ?",
            (sequence_id,),
        ).fetchone()
        return row is not None


def save_commission_event(
    sequence_id: int,
    lead_id: str,
    company_name: str,
    user_id: int,
    opportunity_value_usd: int | None,
    commission_amount: float,
):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO commission_events
               (sequence_id, lead_id, company_name, user_id, opportunity_value_usd, commission_amount, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sequence_id, lead_id, company_name, user_id, opportunity_value_usd, commission_amount, _now()),
        )


def get_manager_stats() -> dict:
    """Aggregate stats for the manager dashboard."""
    with get_conn() as conn:
        total_sequences = conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0]

        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) as n FROM sequences GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["n"]

        by_rep = conn.execute("""
            SELECT u.name, COUNT(s.id) as sequences,
                   SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN s.status = 'paused' THEN 1 ELSE 0 END) as paused,
                   SUM(CASE WHEN s.status IN ('cancelled','completed') THEN 1 ELSE 0 END) as closed
            FROM sequences s JOIN users u ON u.id = s.user_id
            GROUP BY u.id ORDER BY sequences DESC
        """).fetchall()

        total_touchpoints = conn.execute("SELECT COUNT(*) FROM touchpoints").fetchone()[0]
        approved_touchpoints = conn.execute(
            "SELECT COUNT(*) FROM touchpoints WHERE status = 'approved'"
        ).fetchone()[0]

        total_commission = conn.execute(
            "SELECT COALESCE(SUM(commission_amount), 0) FROM commission_events"
        ).fetchone()[0]

        recent_sequences = conn.execute("""
            SELECT s.company_name, s.status, s.created_at, u.name as user_name
            FROM sequences s JOIN users u ON u.id = s.user_id
            ORDER BY s.created_at DESC LIMIT 10
        """).fetchall()

        return {
            "total_sequences": total_sequences,
            "by_status": by_status,
            "by_rep": [dict(r) for r in by_rep],
            "total_touchpoints": total_touchpoints,
            "approved_touchpoints": approved_touchpoints,
            "total_commission": total_commission,
            "recent_sequences": [dict(r) for r in recent_sequences],
        }


def get_commission_events() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*, u.name as user_name
               FROM commission_events c JOIN users u ON u.id = c.user_id
               ORDER BY c.detected_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
