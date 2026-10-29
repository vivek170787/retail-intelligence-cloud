/**
 * Renders rows from agent_evaluation/eval_log.py -- every row is a REAL
 * evaluation of a real hardcoded test case (agent_evaluation/test_cases.py)
 * against a real agent answer, combining a rubric check (evidence presence
 * + answer keyword check) with an LLM-as-judge score. judge_overall is
 * null, not 0, when judged is 0 (no OPENAI_API_KEY configured, no answer
 * was generated, or the judge call itself failed) -- see judge_error.
 */

import type { EvaluationResultRow } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";

export function EvaluationResultTable({ results }: { results: EvaluationResultRow[] }) {
  const columns: DataTableColumn<EvaluationResultRow>[] = [
    {
      key: "passed",
      header: "Rubric",
      sortable: true,
      accessor: (r) => r.passed,
      render: (r) =>
        r.passed ? <Badge label="Pass" tone="success" dot /> : <Badge label="Fail" tone="danger" dot />,
    },
    {
      key: "agent",
      header: "Agent",
      sortable: true,
      accessor: (r) => AGENT_NAME_BY_KEY[r.agent_key] ?? r.agent_key,
    },
    { key: "question", header: "Question", accessor: (r) => r.question },
    {
      key: "status",
      header: "Status",
      accessor: (r) => r.status,
      render: (r) =>
        r.status === "skipped_no_answer" ? (
          <Badge label="No answer generated" tone="neutral" />
        ) : (
          <Badge label="Checked" tone="info" />
        ),
    },
    {
      key: "missing_evidence",
      header: "Missing evidence",
      accessor: (r) => r.missing_evidence_keys.join(", "),
      render: (r) => (r.missing_evidence_keys.length > 0 ? r.missing_evidence_keys.join(", ") : "--"),
    },
    {
      key: "judge_overall",
      header: "Judge score",
      align: "right",
      sortable: true,
      accessor: (r) => r.judge_overall,
      render: (r) => (r.judged ? `${r.judge_overall} / 5` : "Not judged"),
    },
    {
      key: "judge_rationale",
      header: "Judge rationale",
      accessor: (r) => r.judge_rationale ?? r.judge_error ?? "",
      render: (r) => r.judge_rationale ?? r.judge_error ?? "--",
    },
    {
      key: "ran_at",
      header: "Ran at",
      sortable: true,
      accessor: (r) => r.ran_at,
      render: (r) => new Date(r.ran_at).toLocaleString(),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={results}
      rowKey={(r) => String(r.id)}
      emptyMessage="No evaluation runs yet. Click 'Run Evaluations' to score every agent against its hardcoded test cases."
      defaultSortKey="ran_at"
      defaultSortDirection="desc"
    />
  );
}
