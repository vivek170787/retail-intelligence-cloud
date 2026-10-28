"""
Lightweight local execution logging for the five retail agents and the
orchestrator, backed by a small dedicated SQLite database
(db/agent_execution_log.db -- deliberately separate from db/retail.db,
which build_sqlite_db.py drops and recreates from the source CSVs and so
is unsafe to also use for an append-only log).

Every row inserted here corresponds to a REAL HTTP request this backend
actually served (see api/main.py's logging middleware, the only writer to
this table) -- never a fabricated or simulated entry. No execution history
existed anywhere in this project before this module; this is the "if
execution history is not currently stored, implement lightweight local
logging" piece.

What is logged, and what is deliberately NOT logged: the HTTP method,
path (the "input" -- which endpoint, with its query string), status code,
success flag, duration, and timestamp for every call to a known agent's
routes. Request/response BODIES are never captured -- that would mean
buffering and persisting full payloads (including, for POST
/retail-ai/query, free-text user questions) for comparatively little
monitoring value, so each row's "summary" is a short structural
description (endpoint + outcome), not a dump of the payload.

A single sqlite3 connection is opened and closed per call rather than
held open/shared across requests -- simplest way to stay correct under
FastAPI's threadpool without adding a connection-pooling dependency, and
inserts are small enough (one row) that the overhead is negligible for
this "lightweight" use case.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "agent_execution_log.db"
# On Vercel the deployment filesystem is read-only; only /tmp is writable.
# AGENT_LOG_DB_PATH overrides the location explicitly when set.
if os.getenv("AGENT_LOG_DB_PATH"):
    DB_PATH = Path(os.environ["AGENT_LOG_DB_PATH"])
elif os.getenv("VERCEL"):
    DB_PATH = Path("/tmp") / "agent_execution_log.db"
else:
    DB_PATH = _DEFAULT_DB_PATH

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_key TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    success INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    started_at TEXT NOT NULL,
    error_message TEXT,
    summary TEXT
)
"""

_CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_key_id "
    "ON agent_executions (agent_key, id DESC)"
)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Idempotent: safe to call on every process start."""
    with closing(_connect()) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_SQL)
        conn.commit()


def record_execution(agent_key, method, path, status_code, duration_ms, error_message=None, summary=None):
    """Insert one real execution record. Never raises -- a logging failure
    (e.g. a locked/unwritable database file) must never break the actual
    API response it's trying to log, so any exception here is swallowed
    after being attempted once."""
    success = 1 if 200 <= status_code < 400 else 0
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        with closing(_connect()) as conn:
            conn.execute(
                "INSERT INTO agent_executions "
                "(agent_key, method, path, status_code, success, duration_ms, started_at, error_message, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (agent_key, method, path, status_code, success, duration_ms, started_at, error_message, summary),
            )
            conn.commit()
    except Exception:
        pass


def list_executions(agent_key=None, limit=50):
    """Most-recent-first raw execution rows, optionally filtered to one
    agent. Every row returned is a real logged HTTP call -- see module
    docstring."""
    limit = max(1, min(int(limit), 500))
    with closing(_connect()) as conn:
        if agent_key:
            rows = conn.execute(
                "SELECT * FROM agent_executions WHERE agent_key = ? ORDER BY id DESC LIMIT ?",
                (agent_key, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_executions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def get_agent_stats(agent_key):
    """Aggregate stats for one agent, computed only from real logged rows.
    Returns None fields (not zeros) when there is no execution history yet,
    so the caller can render "no data" rather than a misleading 0."""
    with closing(_connect()) as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successful, "
            "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed "
            "FROM agent_executions WHERE agent_key = ?",
            (agent_key,),
        ).fetchone()
        last = conn.execute(
            "SELECT * FROM agent_executions WHERE agent_key = ? ORDER BY id DESC LIMIT 1",
            (agent_key,),
        ).fetchone()

    total_runs = totals["total"] or 0
    return {
        "total_runs": total_runs,
        "successful_runs": totals["successful"] or 0,
        "failed_runs": totals["failed"] or 0,
        "last_execution": dict(last) if last else None,
    }
