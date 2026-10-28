"use client";

/**
 * Per-agent execution log drawer. The summary (status/counts/last
 * execution) is passed in from the already-fetched GET /agent-monitoring/agents
 * list; this component only fetches the recent execution rows for this
 * one agent (GET /agent-monitoring/agents/{agent_key}/executions) -- all
 * real, locally-logged HTTP requests, never sample/simulated data.
 */

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { ApiError, getAgentExecutions } from "@/lib/api";
import type { AgentExecutionRecord, AgentMonitoringSummary } from "@/lib/types";
import { AGENT_STATUS_LABEL } from "@/components/retail/agentMonitoringLabels";
import { AgentExecutionTable } from "@/components/retail/AgentExecutionTable";
import { ErrorState } from "@/components/retail/ErrorState";
import { LoadingState } from "@/components/retail/LoadingState";
import { StatusBadge } from "@/components/retail/StatusBadge";

export function AgentMonitoringDetailDrawer({
  agent,
  onClose,
}: {
  agent: AgentMonitoringSummary;
  onClose: () => void;
}) {
  const [executions, setExecutions] = useState<AgentExecutionRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
    });

    getAgentExecutions(agent.agent_key, 100)
      .then((rows) => {
        if (!cancelled) setExecutions(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "An unexpected error occurred.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [agent.agent_key]);

  useEffect(() => {
    panelRef.current?.focus();
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-detail-title"
        tabIndex={-1}
        className="relative z-50 flex h-full w-full max-w-3xl flex-col overflow-y-auto bg-[var(--ric-card-bg)] shadow-lg outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--ric-border)] px-5 py-4">
          <div>
            <h2 id="agent-detail-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {agent.agent_name}
            </h2>
            <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">{agent.purpose}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            className="rounded-md p-1.5 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-6 px-5 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={AGENT_STATUS_LABEL[agent.status] ?? agent.status} />
            <span className="text-xs text-[var(--ric-text-secondary)]">
              API path prefix: <code>{agent.path_prefix}</code>
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-md border border-[var(--ric-border)] p-3">
              <p className="text-xs text-[var(--ric-text-secondary)]">Total runs</p>
              <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">{agent.total_runs}</p>
            </div>
            <div className="rounded-md border border-[var(--ric-border)] p-3">
              <p className="text-xs text-[var(--ric-text-secondary)]">Successful</p>
              <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">{agent.successful_runs}</p>
            </div>
            <div className="rounded-md border border-[var(--ric-border)] p-3">
              <p className="text-xs text-[var(--ric-text-secondary)]">Failed</p>
              <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">{agent.failed_runs}</p>
            </div>
            <div className="rounded-md border border-[var(--ric-border)] p-3">
              <p className="text-xs text-[var(--ric-text-secondary)]">Last execution duration</p>
              <p className="mt-1 text-lg font-semibold text-[var(--ric-text-primary)]">
                {agent.last_execution ? `${Math.round(agent.last_execution.duration_ms)} ms` : "Unavailable"}
              </p>
            </div>
          </div>

          {agent.last_execution ? (
            <div className="rounded-md border border-[var(--ric-border)] p-3 text-sm">
              <p className="text-xs font-medium text-[var(--ric-text-secondary)]">Last execution</p>
              <p className="mt-1 text-[var(--ric-text-primary)]">
                {new Date(agent.last_execution.started_at).toLocaleString()} -- {agent.last_execution.method}{" "}
                {agent.last_execution.path}
              </p>
              {agent.last_execution.error_message && (
                <p className="mt-1 text-xs text-red-700">{agent.last_execution.error_message}</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--ric-text-secondary)]">
              No execution has been logged for this agent yet -- it simply hasn&apos;t been called since this
              backend started logging. This is not an error.
            </p>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
              Recent executions (real, locally-logged -- not sample data)
            </h3>
            <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
              &quot;Input&quot; is the API endpoint actually called; &quot;Output&quot; is its status code, duration,
              and error (if any). Request/response bodies are not captured by this lightweight log.
            </p>
            {loading && <LoadingState message="Loading execution log..." />}
            {error && <ErrorState message={error} />}
            {executions && <AgentExecutionTable executions={executions} />}
          </div>
        </div>
      </div>
    </div>
  );
}
