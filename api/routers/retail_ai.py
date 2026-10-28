"""
Ask Retail AI route. Routes every question through the existing
RetailIntelligenceOrchestrator.handle_query() -- deterministic keyword/
pattern-based routing that works fully without an OpenAI API key. When
OPENAI_API_KEY is configured, the already-computed structured result is
additionally narrated in natural language (see
orchestration/llm_explainer.py::narrate_orchestrator_result) and attached
as `ai_narration` -- a non-blocking enrichment, never a dependency: the
deterministic `result` is always returned even if narration is disabled or
fails.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_orchestrator
from openai_config import is_configured
from orchestration.llm_explainer import narrate_orchestrator_result

router = APIRouter(prefix="/retail-ai", tags=["retail-ai"])


class RetailAIQuery(BaseModel):
    query: str
    sku: str | None = None
    order_id: str | None = None
    store_id: str | None = None
    horizon_days: int = 7
    limit: int = 10


@router.get("/status")
def get_retail_ai_status():
    """Whether natural-language narration is available -- never exposes the
    API key itself, only whether one is configured."""
    return {"openai_narration_configured": is_configured()}


@router.post("/query")
def post_retail_ai_query(body: RetailAIQuery, orchestrator=Depends(get_orchestrator)):
    result = orchestrator.handle_query(
        body.query,
        sku=body.sku,
        order_id=body.order_id,
        store_id=body.store_id,
        horizon_days=body.horizon_days,
        limit=body.limit,
    )
    result["ai_narration"] = narrate_orchestrator_result(body.query, result)
    return result
