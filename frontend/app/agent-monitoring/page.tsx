"use client";

/**
 * Agent Monitoring workspace. Combines static agent metadata
 * (agent_monitoring/registry.py) with REAL execution records written by
 * api/main.py's logging middleware to a dedicated local SQLite database
 * (agent_monitoring/execution_log.py) -- no execution data here is
 * fabricated, sampled, or simulated. There was no execution-history
 * infrastructure anywhere in this project before this workspace; this IS
 * that lightweight local logging.
 *
 * An agent showing "No executions recorded" simply has not been called
 * since this backend process started logging -- not an error, and never
 * backfilled with a placeholder entry.
 */

import { useState } from "react";
import { Activity, CheckCircle2, Timer, XCircle } from "lucide-react";

import { getAgentMonitoringList } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { AgentMonitoringSummary } from "@/lib/types";
import { AGENT_STATUS_LABEL } from "@/components/retail/agentMonitoringLabels";
import { AgentMonitoringDetailDrawer } from "@/components/retail/AgentMonitoringDetailDrawer";
import { Card, CardBody } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import { StatusBadge } from "@/components/retail/StatusBadge";

export default function AgentMonitoringPage() {
  const agents = useApi(() => getAgentMonitoringList(), []);
  const [selectedAgent, setSelectedAgent] = useState<AgentMonitoringSummary | null>(null);

  const list = agents.data ?? [];
  const totalRuns = list.reduce((sum, a) => sum + a.total_runs, 0);
  const totalFailed = list.reduce((sum, a) => sum + a.failed_runs, 0);
  const agentsWithData = list.filter((a) => a.total_runs > 0).length;
  const agentsInError = list.filter((a) => a.status === "error").length;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Agent Monitoring</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Status and execution history for every implemented agent and the orchestrator.
          </p>
        </div>
        <button
          type="button"
          onClick={() => agents.refetch()}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
        >
          Refresh data
        </button>
      </div>

      <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-page-bg)] px-3 py-2.5 text-xs text-[var(--ric-text-secondary)]">
        Every record on this page is a real HTTP request this backend actually served, logged locally to a
        dedicated SQLite database (<code>agent_monitoring/execution_log.py</code>) -- none of it is sample,
        simulated, or fabricated data. An agent with no executions yet has simply not been called since this
        backend process started logging.
      </div>

      {agents.loading && <LoadingState message="Loading agent monitoring data..." />}
      {agents.error && <ErrorState message={agents.error} />}

      {agents.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Monitored Agents" value={list.length} icon={Activity} />
          <KpiCard label="Agents With Logged Activity" value={agentsWithData} icon={CheckCircle2} />
          <KpiCard label="Total Logged Runs" value={totalRuns} icon={Timer} />
          <KpiCard label="Agents in Error (last run failed)" value={agentsInError} icon={XCircle} />
          {totalFailed > 0 && (
            <p className="col-span-full text-xs text-[var(--ric-text-secondary)]">
              {totalFailed} failed run(s) recorded across all agents -- open an agent below for details.
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {list.map((agent) => (
          <Card key={agent.agent_key}>
            <CardBody className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--ric-text-primary)]">{agent.agent_name}</p>
                  <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{agent.purpose}</p>
                </div>
                <StatusBadge label={AGENT_STATUS_LABEL[agent.status] ?? agent.status} />
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Runs</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.total_runs}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Succeeded</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.successful_runs}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Failed</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.failed_runs}</p>
                </div>
              </div>

              <p className="text-xs text-[var(--ric-text-secondary)]">
                {agent.last_execution ? (
                  <>
                    Last execution: {new Date(agent.last_execution.started_at).toLocaleString()} (
                    {Math.round(agent.last_execution.duration_ms)} ms)
                  </>
                ) : (
                  "No executions recorded yet."
                )}
              </p>

              <button
                type="button"
                onClick={() => setSelectedAgent(agent)}
                className="w-full rounded-lg border border-[var(--ric-border)] px-3 py-1.5 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)]"
              >
                View execution log
              </button>
            </CardBody>
          </Card>
        ))}
      </div>

      <DisclaimerFooter text="This page only ever shows real, locally-logged execution records. No agent activity is simulated or displayed in real time beyond what has actually been logged." />

      {selectedAgent && (
        <AgentMonitoringDetailDrawer agent={selectedAgent} onClose={() => setSelectedAgent(null)} />
      )}
    </div>
  );
}
