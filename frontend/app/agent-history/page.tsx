"use client";

/**
 * Agent Execution History -- a chronological feed across every monitored
 * agent, from the same real, locally-logged execution records as the
 * Agent Monitoring workspace (agent_monitoring/execution_log.py via
 * GET /agent-monitoring/executions). No row here is sample or simulated
 * data; this page simply shows more of the same real log, unfiltered by
 * agent, for reviewing recent activity end-to-end.
 */

import { useMemo, useState } from "react";

import { getAllAgentExecutions } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";
import { AgentExecutionTable } from "@/components/retail/AgentExecutionTable";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { EmptyState } from "@/components/retail/EmptyState";
import { ErrorState } from "@/components/retail/ErrorState";
import { LoadingState } from "@/components/retail/LoadingState";
import { FilterBar } from "@/components/ui/FilterBar";
import { SelectFilter } from "@/components/ui/SelectFilter";

const ALL = "__all__";
const LIMIT_OPTIONS = [
  { value: "50", label: "Last 50" },
  { value: "100", label: "Last 100" },
  { value: "250", label: "Last 250" },
];

export default function AgentHistoryPage() {
  const [limit, setLimit] = useState(100);
  const executions = useApi(() => getAllAgentExecutions(limit), [limit]);
  const [agentFilter, setAgentFilter] = useState(ALL);

  const items = useMemo(() => executions.data ?? [], [executions.data]);

  const agentOptions = useMemo(() => {
    const keys = new Set<string>();
    for (const item of items) keys.add(item.agent_key);
    return [
      { value: ALL, label: "All agents" },
      ...[...keys].sort().map((k) => ({ value: k, label: AGENT_NAME_BY_KEY[k] ?? k })),
    ];
  }, [items]);

  const filtered = useMemo(
    () => (agentFilter === ALL ? items : items.filter((i) => i.agent_key === agentFilter)),
    [items, agentFilter]
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Agent Execution History</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          A chronological feed of real, locally-logged API executions across every monitored agent -- not sample
          or simulated data. See the Agent Monitoring workspace for per-agent status and stats.
        </p>
      </div>

      <Card>
        <CardHeader title="Filters" />
        <FilterBar>
          <SelectFilter label="Agent" value={agentFilter} options={agentOptions} onChange={setAgentFilter} />
          <SelectFilter
            label="Show"
            value={String(limit)}
            options={LIMIT_OPTIONS}
            onChange={(v) => setLimit(Number(v))}
          />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filtered.length} of {items.length} logged execution(s).
          </p>
          {executions.loading && <LoadingState message="Loading execution history..." />}
          {executions.error && <ErrorState message={executions.error} />}
          {!executions.loading && !executions.error && filtered.length === 0 && (
            <EmptyState message="No execution history recorded yet. Executions are logged as agent API routes are actually called." />
          )}
          {!executions.loading && filtered.length > 0 && (
            <AgentExecutionTable executions={filtered} showAgent />
          )}
        </CardBody>
      </Card>

      <DisclaimerFooter text="This page only ever shows real, locally-logged execution records. No agent activity is simulated or displayed in real time beyond what has actually been logged." />
    </div>
  );
}
