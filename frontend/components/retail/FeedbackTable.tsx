/**
 * Renders rows from agent_feedback/store.py -- every row is a REAL thumbs
 * up/down submission (fanned out to one row per contributing agent_key),
 * never sample or simulated feedback. counted_in_adjustment_id is shown so
 * it's visible which feedback already contributed to a prompt adjustment.
 */

import type { FeedbackRecord } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";

export function FeedbackTable({ feedback }: { feedback: FeedbackRecord[] }) {
  const columns: DataTableColumn<FeedbackRecord>[] = [
    {
      key: "rating",
      header: "Rating",
      sortable: true,
      accessor: (r) => r.rating,
      render: (r) =>
        r.rating === "up" ? <Badge label="Up" tone="success" dot /> : <Badge label="Down" tone="danger" dot />,
    },
    {
      key: "agent",
      header: "Agent",
      sortable: true,
      accessor: (r) => AGENT_NAME_BY_KEY[r.agent_key] ?? r.agent_key,
    },
    { key: "query", header: "Query", accessor: (r) => r.query },
    { key: "comment", header: "Comment", accessor: (r) => r.comment ?? "", render: (r) => r.comment ?? "--" },
    {
      key: "counted",
      header: "Counted toward adjustment",
      accessor: (r) => (r.counted_in_adjustment_id != null ? "yes" : "no"),
      render: (r) => (r.counted_in_adjustment_id != null ? `#${r.counted_in_adjustment_id}` : "--"),
    },
    {
      key: "submitted_at",
      header: "Submitted",
      sortable: true,
      accessor: (r) => r.submitted_at,
      render: (r) => new Date(r.submitted_at).toLocaleString(),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={feedback}
      rowKey={(r) => String(r.id)}
      emptyMessage="No feedback submitted yet. Thumbs up/down on an Ask Retail AI answer to get started."
      defaultSortKey="submitted_at"
      defaultSortDirection="desc"
    />
  );
}
