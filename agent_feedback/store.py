"""
Lightweight local storage for human feedback (thumbs up/down + optional
comment) on agent answers, and for the "prompt adjustments" that the AI
feedback loop automatically derives from accumulated negative feedback.

Backed by a small dedicated SQLite database (db/agent_feedback.db --
deliberately separate from db/retail.db and db/agent_execution_log.db),
following the exact connect/init/insert/list pattern established by
agent_monitoring/execution_log.py.

Two tables:
- feedback: one row per (submission, contributing agent_key) pair -- a
  single thumbs up/down can fan out to several agent_keys when the
  underlying answer involved multiple agents (see orchestrator
  responses' `agents_used`). `counted_in_adjustment_id` is set the
  moment a row has been counted toward a triggered prompt adjustment,
  so it can never be double-counted toward a later one.
- prompt_adjustments: one row per automatic (or manually forced) prompt
  adjustment for one agent_key. `get_active_adjustment()` -- consumed by
  every agent's llm_explainer.py -- returns the most recent row's text.

get_active_adjustment() is called from contexts that never ran this
project's FastAPI startup (each agent's own cli.py, pytest, the
evaluation runner), so it defensively ensures the schema exists and
never raises -- a storage hiccup must never block an agent from
answering a question.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "agent_feedback.db"
if os.getenv("AGENT_FEEDBACK_DB_PATH"):
    DB_PATH = Path(os.environ["AGENT_FEEDBACK_DB_PATH"])
elif os.getenv("VERCEL"):
    DB_PATH = Path("/tmp") / "agent_feedback.db"
else:
    DB_PATH = _DEFAULT_DB_PATH

_CREATE_FEEDBACK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_key TEXT NOT NULL,
    query TEXT NOT NULL,
    answer_snippet TEXT,
    rating TEXT NOT NULL,
    comment TEXT,
    submitted_at TEXT NOT NULL,
    counted_in_adjustment_id INTEGER
)
"""

_CREATE_ADJUSTMENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prompt_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_key TEXT NOT NULL,
    adjustment_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    trigger_feedback_count INTEGER NOT NULL
)
"""

_CREATE_FEEDBACK_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_feedback_agent_key_id ON feedback (agent_key, id DESC)"
)
_CREATE_ADJUSTMENTS_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_prompt_adjustments_agent_key_id "
    "ON prompt_adjustments (agent_key, id DESC)"
)

_ANSWER_SNIPPET_MAX_CHARS = 500


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Idempotent: safe to call on every process start, and safe to call
    repeatedly from within a single request (CREATE TABLE IF NOT EXISTS)."""
    with closing(_connect()) as conn:
        conn.execute(_CREATE_FEEDBACK_TABLE_SQL)
        conn.execute(_CREATE_ADJUSTMENTS_TABLE_SQL)
        conn.execute(_CREATE_FEEDBACK_INDEX_SQL)
        conn.execute(_CREATE_ADJUSTMENTS_INDEX_SQL)
        conn.commit()


def submit_feedback(agent_keys, query, answer, rating, comment=None):
    """Record one thumbs up/down submission, fanned out to one row per
    contributing agent_key (deduplicated, order-preserving). `rating` must
    be "up" or "down". Returns the list of inserted row ids, in the same
    order as the deduplicated agent_keys."""
    if rating not in ("up", "down"):
        raise ValueError(f"rating must be 'up' or 'down', got {rating!r}")

    seen = set()
    deduped_keys = []
    for key in agent_keys:
        if key not in seen:
            seen.add(key)
            deduped_keys.append(key)
    if not deduped_keys:
        deduped_keys = ["orchestrator"]

    answer_snippet = (answer or "")[:_ANSWER_SNIPPET_MAX_CHARS]
    submitted_at = datetime.now(timezone.utc).isoformat()

    init_db()
    inserted_ids = []
    with closing(_connect()) as conn:
        for agent_key in deduped_keys:
            cursor = conn.execute(
                "INSERT INTO feedback "
                "(agent_key, query, answer_snippet, rating, comment, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (agent_key, query, answer_snippet, rating, comment, submitted_at),
            )
            inserted_ids.append(cursor.lastrowid)
        conn.commit()
    return deduped_keys, inserted_ids


def get_active_adjustment(agent_key):
    """Return the most recent adjustment_text for this agent_key, or None
    if none exists. Never raises -- called from contexts (agent CLIs,
    pytest, the eval runner) that may not have run init_db() yet, and a
    storage failure here must never prevent an agent from answering."""
    try:
        init_db()
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT adjustment_text FROM prompt_adjustments "
                "WHERE agent_key = ? ORDER BY id DESC LIMIT 1",
                (agent_key,),
            ).fetchone()
        return row["adjustment_text"] if row else None
    except Exception:
        return None


def create_adjustment(agent_key, adjustment_text, trigger_feedback_count, feedback_ids_to_mark):
    """Insert one prompt_adjustments row and mark the given feedback row
    ids as counted toward it, in a single transaction, so those specific
    rows can never trigger a second adjustment. Returns the new
    adjustment's id."""
    created_at = datetime.now(timezone.utc).isoformat()
    init_db()
    with closing(_connect()) as conn:
        cursor = conn.execute(
            "INSERT INTO prompt_adjustments "
            "(agent_key, adjustment_text, created_at, trigger_feedback_count) "
            "VALUES (?, ?, ?, ?)",
            (agent_key, adjustment_text, created_at, trigger_feedback_count),
        )
        adjustment_id = cursor.lastrowid
        if feedback_ids_to_mark:
            placeholders = ",".join("?" for _ in feedback_ids_to_mark)
            conn.execute(
                f"UPDATE feedback SET counted_in_adjustment_id = ? WHERE id IN ({placeholders})",
                (adjustment_id, *feedback_ids_to_mark),
            )
        conn.commit()
    return adjustment_id


def list_uncounted_negative_feedback(agent_key):
    """Most-recent-last list of "down" feedback rows for this agent_key
    that have not yet been counted toward any prompt adjustment."""
    init_db()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE agent_key = ? AND rating = 'down' "
            "AND counted_in_adjustment_id IS NULL ORDER BY id ASC",
            (agent_key,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_feedback(agent_key=None, limit=50):
    """Most-recent-first feedback rows, optionally filtered to one agent."""
    limit = max(1, min(int(limit), 500))
    init_db()
    with closing(_connect()) as conn:
        if agent_key:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE agent_key = ? ORDER BY id DESC LIMIT ?",
                (agent_key, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def list_adjustments(agent_key=None, limit=50):
    """Most-recent-first prompt_adjustments rows, optionally filtered to
    one agent."""
    limit = max(1, min(int(limit), 500))
    init_db()
    with closing(_connect()) as conn:
        if agent_key:
            rows = conn.execute(
                "SELECT * FROM prompt_adjustments WHERE agent_key = ? ORDER BY id DESC LIMIT ?",
                (agent_key, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM prompt_adjustments ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def get_feedback_stats(agent_key):
    """Aggregate up/down counts for one agent, plus its current active
    adjustment (if any)."""
    init_db()
    with closing(_connect()) as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN rating = 'up' THEN 1 ELSE 0 END) AS up_count, "
            "SUM(CASE WHEN rating = 'down' THEN 1 ELSE 0 END) AS down_count "
            "FROM feedback WHERE agent_key = ?",
            (agent_key,),
        ).fetchone()
    return {
        "total": totals["total"] or 0,
        "up_count": totals["up_count"] or 0,
        "down_count": totals["down_count"] or 0,
        "active_adjustment": get_active_adjustment(agent_key),
    }
