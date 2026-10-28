"use client";

/**
 * Ask Retail AI -- a conversational workspace over the existing
 * RetailIntelligenceOrchestrator.handle_query() (POST /retail-ai/query).
 * Routing is fully deterministic (keyword + SKU/order/store-ID pattern
 * matching in orchestration/query_orchestrator.py) and works without an
 * OpenAI API key -- this page never depends on the LLM for anything
 * structural (suggested questions, findings, evidence, badges, actions all
 * render regardless of whether OPENAI_API_KEY is configured).
 *
 * When OPENAI_API_KEY IS configured, the backend additionally narrates the
 * already-computed structured result in natural language (see
 * orchestration/llm_explainer.py::narrate_orchestrator_result) and attaches
 * it as `ai_narration` -- shown as a clearly-labeled enrichment, never a
 * replacement for the structured findings beneath it. No computation of
 * any kind happens in this frontend; every number comes from the
 * orchestrator's response.
 *
 * Conversation history is session-only (component state, not persisted) --
 * each turn keeps its own loading/error state so an in-flight question
 * never clears a previous answer.
 */

import { useRef, useState } from "react";
import { MessageSquareText, Send, Trash2 } from "lucide-react";

import { ApiError, getDashboardSummary, getRetailAiStatus, postRetailAiQuery } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { RetailAiQueryResponse } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataFreshnessNote } from "@/components/retail/DataFreshnessNote";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { RetailAiAnswerCard } from "@/components/retail/RetailAiAnswerCard";

const EXAMPLE_QUESTIONS = [
  "Which stores are at risk of stockouts this week?",
  "Which products need replenishment?",
  "Which promotions are not ready for launch?",
  "Which orders require immediate attention?",
  "What is causing the highest inventory risk?",
  "Which customers may be affected by fulfillment issues?",
  "Give me an executive summary of today's retail risks.",
  "What actions should we prioritize to reduce lost sales?",
];

interface ConversationTurn {
  id: string;
  query: string;
  response: RetailAiQueryResponse | null;
  error: string | null;
  loading: boolean;
}

export default function AskRetailAiPage() {
  const snapshot = useApi(() => getDashboardSummary(), []);
  const aiStatus = useApi(() => getRetailAiStatus(), []);

  const [queryText, setQueryText] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const nextTurnId = useRef(0);

  async function runQuery(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    nextTurnId.current += 1;
    const id = `turn-${nextTurnId.current}`;
    setTurns((prev) => [{ id, query: trimmed, response: null, error: null, loading: true }, ...prev]);
    setQueryText("");

    try {
      const response = await postRetailAiQuery({ query: trimmed });
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, response, loading: false } : t)));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "An unexpected error occurred.";
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: message, loading: false } : t)));
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Ask Retail AI</h1>
          {aiStatus.data && (
            <Badge
              label={aiStatus.data.openai_narration_configured ? "AI narration: enabled" : "AI narration: rule-based only"}
              tone={aiStatus.data.openai_narration_configured ? "info" : "neutral"}
              dot
            />
          )}
        </div>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Natural-language retail questions, routed through the existing Retail Intelligence Orchestrator across
          Inventory, Demand, Promotion, Order Fulfillment, and Customer Experience. Deterministic rule-based
          routing works with no OpenAI API key; when one is configured, answers also get a narrated summary.
        </p>
      </div>

      {/* ---- Today's snapshot: relevant KPI summaries, reused from the existing dashboard summary ---- */}
      {snapshot.loading && <LoadingState message="Loading today's snapshot..." />}
      {snapshot.error && <ErrorState message={snapshot.error} />}
      {snapshot.data && (
        <div>
          <DataFreshnessNote note="Today's snapshot (reused from the Executive Overview's own summary) -- ask a question below for a focused answer." />
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <KpiCard
              label="Critical + High Inventory Risk"
              value={
                snapshot.data.inventory_summary
                  ? (snapshot.data.inventory_summary.risk_level_counts.critical ?? 0) +
                    (snapshot.data.inventory_summary.risk_level_counts.high ?? 0)
                  : "Unavailable"
              }
            />
            <KpiCard
              label="Demand Spikes"
              value={snapshot.data.demand_summary?.products_with_demand_spike ?? "Unavailable"}
            />
            <KpiCard
              label="Promotions Insufficient"
              value={snapshot.data.promotion_summary?.readiness_counts?.insufficient ?? "Unavailable"}
            />
            <KpiCard
              label="Critical Open Orders"
              value={snapshot.data.fulfillment_summary?.risk_counts?.critical ?? "Unavailable"}
            />
            <KpiCard
              label="Customer Impact Risks"
              value={snapshot.data.cx_summary?.total_customer_impact_risks ?? "Unavailable"}
            />
          </div>
        </div>
      )}

      <div>
        <p className="mb-2 text-sm font-medium text-[var(--ric-text-primary)]">Suggested business questions:</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => void runQuery(question)}
              className="rounded-full border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-xs text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
            >
              {question}
            </button>
          ))}
        </div>
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void runQuery(queryText);
        }}
      >
        <input
          type="text"
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="Or type your own retail question..."
          className="flex-1 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-2 text-sm text-[var(--ric-text-primary)] outline-none focus:border-[var(--ric-primary)]"
        />
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-md bg-[var(--ric-primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--ric-primary-hover)]"
        >
          <Send className="h-3.5 w-3.5" aria-hidden="true" />
          Ask
        </button>
      </form>

      {turns.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-[var(--ric-border)] px-6 py-10 text-center">
          <MessageSquareText className="h-6 w-6 text-[var(--ric-text-secondary)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ric-text-primary)]">No questions asked yet</p>
          <p className="max-w-sm text-xs text-[var(--ric-text-secondary)]">
            Pick a suggested question above or type your own. Every answer includes structured findings, evidence,
            and read-only recommended actions -- never an automatic action.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-[var(--ric-text-primary)]">
              Conversation history ({turns.length})
            </p>
            <button
              type="button"
              onClick={() => setTurns([])}
              className="flex items-center gap-1 text-xs text-[var(--ric-text-secondary)] hover:text-[var(--ric-text-primary)]"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              Clear (this session only)
            </button>
          </div>

          {turns.map((turn) => (
            <div key={turn.id} className="space-y-2">
              <p className="text-sm text-[var(--ric-text-secondary)]">
                <span className="font-medium text-[var(--ric-text-primary)]">You asked:</span> {turn.query}
              </p>
              {turn.loading && <LoadingState message="Routing your question through the orchestrator..." />}
              {turn.error && <ErrorState message={turn.error} />}
              {turn.response && <RetailAiAnswerCard response={turn.response} />}
            </div>
          ))}
        </div>
      )}

      <DisclaimerFooter />
    </div>
  );
}
