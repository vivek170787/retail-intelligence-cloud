"""
Retail Intelligence Cloud -- FastAPI backend.

Thin HTTP proxy over the existing Python retail intelligence agents and
RetailIntelligenceOrchestrator (orchestration/query_orchestrator.py). No
business logic, calculation, or routing is reimplemented here -- every
route calls one existing engine/orchestrator function directly and
returns its already-JSON-safe result.

Run with:
    uvicorn api.main:app --reload
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from agent_monitoring.execution_log import init_db, record_execution
from agent_monitoring.registry import agent_key_for_path
from api.errors import install_error_handlers
from api.routers import (
    agent_monitoring,
    customer_experience,
    dashboard,
    data_quality,
    data_sources,
    demand,
    fulfillment,
    health,
    inventory,
    promotions,
    retail_ai,
)

app = FastAPI(title="Retail Intelligence Cloud API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_agent_executions(request: Request, call_next):
    """Logs every real request to a monitored agent's routes to the local
    execution log (agent_monitoring/execution_log.py) -- the "lightweight
    local logging" backing the Agent Monitoring workspace. Requests to
    unmonitored paths (health, dashboard aggregation, etc.) are not logged.
    Never blocks or fails the actual response: a logging failure is
    swallowed inside record_execution(), and if the request itself raises
    an exception that reaches this middleware, it is logged as a failed
    execution and then re-raised unchanged."""
    agent_key = agent_key_for_path(request.url.path)
    if agent_key is None:
        return await call_next(request)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        record_execution(
            agent_key, request.method, request.url.path, 500, duration_ms,
            error_message=f"{type(exc).__name__}: {exc}",
            summary=f"{request.method} {request.url.path}",
        )
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    record_execution(
        agent_key, request.method, request.url.path, response.status_code, duration_ms,
        error_message=None if response.status_code < 400 else f"HTTP {response.status_code}",
        summary=f"{request.method} {request.url.path}",
    )
    return response


install_error_handlers(app)
init_db()

app.include_router(health.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(demand.router, prefix="/api/v1")
app.include_router(promotions.router, prefix="/api/v1")
app.include_router(fulfillment.router, prefix="/api/v1")
app.include_router(customer_experience.router, prefix="/api/v1")
app.include_router(retail_ai.router, prefix="/api/v1")
app.include_router(agent_monitoring.router, prefix="/api/v1")
app.include_router(data_quality.router, prefix="/api/v1")
app.include_router(data_sources.router, prefix="/api/v1")
