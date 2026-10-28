"use client";

/**
 * Audit Log workspace. Of the four record categories this page could
 * show, only "Agent Executions" is actually backed by a durable,
 * queryable record in this project -- the same real, locally-logged
 * execution log that backs Agent Monitoring (GET /agent-monitoring/executions).
 *
 * "Recommendations Generated", "User-Approved Actions", and "Configuration
 * Changes" are NOT persisted anywhere in this codebase: recommendations
 * are computed on demand and returned directly in each agent response
 * (never logged to a durable trail); the "Mark reviewed" affordance
 * elsewhere in this app (ReviewActionButton) is explicitly session-only,
 * client-side state, not a backend record; and there is no settings store
 * to change. Rather than fabricate sample rows for these, this page shows
 * them as honestly empty, with the reason stated.
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

export default function AuditLogPage() {
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
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Audit Log</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Actual available records only -- no simulated demonstration entries appear on this page.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Agent Executions (real)"
          subtitle="Every real, locally-logged API call to an agent -- the same data as the Agent Monitoring workspace."
        />
        <FilterBar>
          <SelectFilter label="Agent" value={agentFilter} options={agentOptions} onChange={setAgentFilter} />
          <SelectFilter label="Show" value={String(limit)} options={LIMIT_OPTIONS} onChange={(v) => setLimit(Number(v))} />
        </FilterBar>
        <CardBody>
          <p className="mb-2 text-xs text-[var(--ric-text-secondary)]">
            Showing {filtered.length} of {items.length} logged execution(s).
          </p>
          {executions.loading && <LoadingState message="Loading execution log..." />}
          {executions.error && <ErrorState message={executions.error} />}
          {!executions.loading && !executions.error && filtered.length === 0 && (
            <EmptyState message="No execution history recorded yet." />
          )}
          {!executions.loading && filtered.length > 0 && <AgentExecutionTable executions={filtered} showAgent />}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Recommendations Generated" />
        <CardBody>
          <EmptyState message="Not tracked by this backend. Each agent computes and returns its recommendations on demand in its own API response; no durable historical log of past recommendations is persisted anywhere in this codebase." />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="User-Approved Actions" />
        <CardBody>
          <EmptyState message="Not tracked by this backend. The “Mark reviewed” control elsewhere in this app is explicitly session-only, client-side state (see ReviewActionButton) -- it is never sent to or persisted by the server, so there is no record to show here." />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Configuration Changes" />
        <CardBody>
          <EmptyState message="Not tracked by this backend. This project has no persisted settings store (see Organization & Workspace settings) -- there is nothing to log a change to." />
        </CardBody>
      </Card>

      <DisclaimerFooter text="This page only ever shows real, locally-logged records. No audit entry on this page is simulated or fabricated." />
    </div>
  );
}
