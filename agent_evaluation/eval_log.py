"""
Lightweight local storage for Agent Evaluation runs, backed by a small
dedicated SQLite database (db/agent_evaluation.db -- deliberately separate
from db/retail.db, db/agent_execution_log.db, and db/agent_feedback.db),
following the exact connect/init/insert/list/aggregate pattern established
by agent_monitoring/execution_log.py.

Every row is a REAL evaluation of a real test case against a real agent
answer (never fabricated) -- one row per (run, test_case) pair, grouped by
run_id so one "Run Evaluations" click is one batch.
"""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "agent_evaluation.db"
if os.getenv("AGENT_EVAL_DB_PATH"):
    DB_PATH = Path(os.environ["AGENT_EVAL_DB_PATH"])
elif os.getenv("VERCEL"):
    DB_PATH = Path("/tmp") / "agent_evaluation.db"
else:
    DB_PATH = _DEFAULT_DB_PATH

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS eval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent_key TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_passed INTEGER NOT NULL,
    missing_evidence_keys TEXT,
    keyword_passed INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    judged INTEGER NOT NULL,
    judge_groundedness INTEGER,
    judge_relevance INTEGER,
    judge_clarity INTEGER,
    judge_overall REAL,
    judge_rationale TEXT,
    judge_error TEXT,
    ran_at TEXT NOT NULL
)
"""

_CREATE_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_eval_results_agent_key_id ON eval_results (agent_key, id DESC)"
)
_CREATE_RUN_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_eval_results_run_id ON eval_results (run_id)"
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
        conn.execute(_CREATE_RUN_INDEX_SQL)
        conn.commit()


def insert_result(run_id, agent_key, test_case_id, question, status, evidence_passed,
                   missing_evidence_keys, keyword_passed, passed, judged,
                   judge_scores=None, judge_overall=None, judge_rationale=None, judge_error=None):
    ran_at = datetime.now(timezone.utc).isoformat()
    judge_scores = judge_scores or {}
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO eval_results "
            "(run_id, agent_key, test_case_id, question, status, evidence_passed, "
            "missing_evidence_keys, keyword_passed, passed, judged, judge_groundedness, "
            "judge_relevance, judge_clarity, judge_overall, judge_rationale, judge_error, ran_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, agent_key, test_case_id, question, status,
                1 if evidence_passed else 0, json.dumps(missing_evidence_keys),
                1 if keyword_passed else 0, 1 if passed else 0, 1 if judged else 0,
                judge_scores.get("groundedness"), judge_scores.get("relevance"),
                judge_scores.get("clarity"), judge_overall, judge_rationale, judge_error, ran_at,
            ),
        )
        conn.commit()


def list_results(agent_key=None, limit=100):
    """Most-recent-first eval result rows, optionally filtered to one agent."""
    limit = max(1, min(int(limit), 500))
    with closing(_connect()) as conn:
        if agent_key:
            rows = conn.execute(
                "SELECT * FROM eval_results WHERE agent_key = ? ORDER BY id DESC LIMIT ?",
                (agent_key, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM eval_results ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    results = []
    for row in rows:
        result = dict(row)
        result["missing_evidence_keys"] = json.loads(result["missing_evidence_keys"] or "[]")
        results.append(result)
    return results


def get_summary(agent_key):
    """Aggregate pass/fail/skipped counts and average judge overall score
    for one agent, computed only from real logged rows. Returns None for
    avg_judge_overall when no judged rows exist, so the caller can render
    "not judged" rather than a misleading 0."""
    with closing(_connect()) as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed, "
            "SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) AS failed, "
            "SUM(CASE WHEN status = 'skipped_no_answer' THEN 1 ELSE 0 END) AS skipped_no_answer, "
            "AVG(CASE WHEN judged = 1 THEN judge_overall ELSE NULL END) AS avg_judge_overall "
            "FROM eval_results WHERE agent_key = ?",
            (agent_key,),
        ).fetchone()
        last = conn.execute(
            "SELECT * FROM eval_results WHERE agent_key = ? ORDER BY id DESC LIMIT 1",
            (agent_key,),
        ).fetchone()

    total_runs = totals["total"] or 0
    avg_judge_overall = totals["avg_judge_overall"]
    return {
        "total_runs": total_runs,
        "passed": totals["passed"] or 0,
        "failed": totals["failed"] or 0,
        "skipped_no_answer": totals["skipped_no_answer"] or 0,
        "avg_judge_overall": round(avg_judge_overall, 2) if avg_judge_overall is not None else None,
        "last_run_at": last["ran_at"] if last else None,
    }
