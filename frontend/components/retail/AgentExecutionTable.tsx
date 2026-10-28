/**
 * Renders execution rows from agent_monitoring/execution_log.py -- every
 * row is a REAL HTTP request this backend actually served (see
 * AgentExecutionRecord's own doc comment in lib/types.ts). This component
 * never fabricates a row; callers pass only what the API returned.
 *
 * Only endpoint/timing/outcome metadata is available -- request/response
 * bodies are never logged -- so "Input" is the method+endpoint actually
 * called and "Output" is the status code/duration/error, not a findings
 * payload.
 */

import type { AgentExecutionRecord } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";

export function AgentExecutionTable({
  executions,
  showAgent = false,
}: {
  executions: AgentExecutionRecord[];
  showAgent?: boolean;
}) {
  const columns: DataTableColumn<AgentExecutionRecord>[] = [
    {
      key: "outcome",
      header: "Outcome",
      sortable: true,
      accessor: (r) => r.success,
      render: (r) =>
        r.success ? <Badge label="Success" tone="success" dot /> : <Badge label="Failed" tone="danger" dot />,
    },
    ...(showAgent
      ? [
          {
            key: "agent",
            header: "Agent",
            sortable: true,
            accessor: (r: AgentExecutionRecord) => AGENT_NAME_BY_KEY[r.agent_key] ?? r.agent_key,
          } as DataTableColumn<AgentExecutionRecord>,
        ]
      : []),
    {
      key: "started_at",
      header: "Timestamp",
      sortable: true,
      accessor: (r) => r.started_at,
      render: (r) => new Date(r.started_at).toLocaleString(),
    },
    { key: "method", header: "Method", accessor: (r) => r.method },
    { key: "input", header: "Input (endpoint called)", accessor: (r) => r.path },
    {
      key: "status_code",
      header: "Status",
      align: "right",
      sortable: true,
      accessor: (r) => r.status_code,
    },
    {
      key: "duration",
      header: "Duration (ms)",
      align: "right",
      sortable: true,
      accessor: (r) => Math.round(r.duration_ms),
    },
    {
      key: "error",
      header: "Error",
      accessor: (r) => r.error_message ?? "",
      render: (r) => r.error_message ?? "--",
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={executions}
      rowKey={(r) => String(r.id)}
      emptyMessage="No execution records yet."
      defaultSortKey="started_at"
      defaultSortDirection="desc"
    />
  );
}
