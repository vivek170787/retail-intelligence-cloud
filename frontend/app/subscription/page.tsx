"use client";

/**
 * Subscription & Usage workspace. This project has no real billing, plan,
 * or subscription system -- the Plan Overview and Configurable Limits
 * sections below are CLEARLY LABELED DEMONSTRATION DATA, not a real paid
 * billing integration (none is introduced here, per instruction).
 *
 * The Usage Metrics / Agent Execution Counts section is NOT demo data --
 * it is reused directly from the real local execution log that backs the
 * Agent Monitoring workspace (GET /agent-monitoring/agents), the same
 * real, locally-logged records described there.
 */

import { Activity, Boxes, Gauge, Layers } from "lucide-react";

import { getAgentMonitoringList } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import type { AgentMonitoringSummary } from "@/lib/types";

const DEMO_PLAN_FEATURES = [
  "All 5 retail intelligence agents + orchestrator",
  "Unlimited workspaces (demo: 1 synthetic workspace)",
  "Ask Retail AI natural-language queries",
  "Agent monitoring & execution history",
];

const DEMO_LIMITS: { label: string; limit: string }[] = [
  { label: "Agent executions / month", limit: "10,000 (demo value)" },
  { label: "Ask Retail AI queries / day", limit: "500 (demo value)" },
  { label: "Workspaces", limit: "1 (demo value)" },
  { label: "Users", limit: "10 (demo value)" },
];

export default function SubscriptionPage() {
  const agents = useApi(() => getAgentMonitoringList(), []);
  const list = agents.data ?? [];
  const totalRuns = list.reduce((sum, a) => sum + a.total_runs, 0);
  const totalSuccessful = list.reduce((sum, a) => sum + a.successful_runs, 0);
  const totalFailed = list.reduce((sum, a) => sum + a.failed_runs, 0);

  const usageColumns: DataTableColumn<AgentMonitoringSummary>[] = [
    { key: "agent", header: "Agent", sortable: true, accessor: (r) => AGENT_NAME_BY_KEY[r.agent_key] ?? r.agent_name },
    { key: "runs", header: "Executions", align: "right", sortable: true, accessor: (r) => r.total_runs },
    { key: "succeeded", header: "Succeeded", align: "right", sortable: true, accessor: (r) => r.successful_runs },
    { key: "failed", header: "Failed", align: "right", sortable: true, accessor: (r) => r.failed_runs },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Subscription & Usage</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Plan overview and usage for this deployment.
        </p>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
        <strong>Demonstration data:</strong> this project has no real billing, plan, or subscription system, and no
        paid billing provider is integrated here. The Plan Overview and Configurable Limits sections below are
        illustrative only and enforce nothing. The Usage Metrics section below is real -- it is the same locally-
        logged agent execution data shown on the Agent Monitoring workspace.
      </div>

      <Card>
        <CardHeader title="Plan Overview" subtitle="Demonstration data -- not a real subscription." />
        <CardBody className="space-y-3">
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-[var(--ric-text-primary)]">Enterprise Demo Plan</p>
            <Badge label="Demo" tone="warning" />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
            {DEMO_PLAN_FEATURES.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-[var(--ric-text-primary)]">
          Usage Metrics -- Agent Execution Counts (real)
        </h2>
        {agents.loading && <LoadingState message="Loading usage metrics..." />}
        {agents.error && <ErrorState message={agents.error} />}
        {agents.data && (
          <>
            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard label="Total Logged Executions" value={totalRuns} icon={Activity} />
              <KpiCard label="Successful" value={totalSuccessful} icon={Gauge} />
              <KpiCard label="Failed" value={totalFailed} icon={Boxes} />
              <KpiCard label="Monitored Agents" value={list.length} icon={Layers} />
            </div>
            <Card>
              <CardBody>
                <DataTable columns={usageColumns} rows={list} rowKey={(r) => r.agent_key} />
              </CardBody>
            </Card>
          </>
        )}
      </div>

      <Card>
        <CardHeader title="Configurable Limits" subtitle="Demonstration data -- none of these are actually enforced by this backend." />
        <CardBody>
          <DataTable
            columns={[
              { key: "label", header: "Limit", accessor: (r: { label: string; limit: string }) => r.label },
              { key: "value", header: "Demo Value", align: "right", accessor: (r: { label: string; limit: string }) => r.limit },
            ]}
            rows={DEMO_LIMITS}
            rowKey={(r) => r.label}
          />
        </CardBody>
      </Card>

      <DisclaimerFooter text="Plan and limit figures above are clearly labeled demonstration data. No paid billing provider is integrated in this application." />
    </div>
  );
}
