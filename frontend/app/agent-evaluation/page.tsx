"use client";

/**
 * Agent Evaluation workspace. Combines static hardcoded test cases
 * (agent_evaluation/test_cases.py) with REAL evaluation runs -- each run
 * calls the actual agent code (same answer_question()/handle_query() path
 * each agent's own cli.py and the live Ask Retail AI page use), scores it
 * with a rubric check (evidence presence + answer keyword check) and an
 * LLM-as-judge call, and logs the result locally (agent_evaluation/
 * eval_log.py). No evaluation result here is fabricated or simulated.
 *
 * Judge scores are null, not 0, whenever OPENAI_API_KEY is not configured
 * or no answer was generated for a test case -- never backfilled with a
 * placeholder score.
 */

import { useState } from "react";
import { ClipboardCheck, ListChecks, Sparkles, XCircle } from "lucide-react";

import { getEvaluationResults, getEvaluationSummary, runEvaluations } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";
import { Card, CardBody } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { EvaluationResultTable } from "@/components/retail/EvaluationResultTable";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";

export default function AgentEvaluationPage() {
  const summary = useApi(() => getEvaluationSummary(), []);
  const results = useApi(() => getEvaluationResults(), []);
  const [runningAgent, setRunningAgent] = useState<string | "__all__" | null>(null);

  const summaryRows = summary.data ?? [];
  const totalRuns = summaryRows.reduce((sum, a) => sum + a.total_runs, 0);
  const totalPassed = summaryRows.reduce((sum, a) => sum + a.passed, 0);
  const totalFailed = summaryRows.reduce((sum, a) => sum + a.failed, 0);
  const judgedAgents = summaryRows.filter((a) => a.avg_judge_overall != null);
  const avgJudgeOverall =
    judgedAgents.length > 0
      ? judgedAgents.reduce((sum, a) => sum + (a.avg_judge_overall ?? 0), 0) / judgedAgents.length
      : null;

  async function handleRun(agentKey?: string) {
    setRunningAgent(agentKey ?? "__all__");
    try {
      await runEvaluations(agentKey);
      await Promise.all([summary.refetch(), results.refetch()]);
    } finally {
      setRunningAgent(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Agent Evaluation</h1>
          <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
            Score every agent against a fixed set of test questions: a rubric check (evidence presence + answer
            keywords) plus an independent LLM-as-judge score.
          </p>
        </div>
        <button
          type="button"
          onClick={() => handleRun()}
          disabled={runningAgent !== null}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-primary)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {runningAgent === "__all__" ? "Running..." : "Run Evaluations"}
        </button>
      </div>

      <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-page-bg)] px-3 py-2.5 text-xs text-[var(--ric-text-secondary)]">
        Test questions are catalog-wide and hardcoded (<code>agent_evaluation/test_cases.py</code>), so results
        don&apos;t depend on which synthetic SKU/order IDs exist in this environment. All data is synthetic test
        data generated for development.
      </div>

      {(summary.loading || results.loading) && <LoadingState message="Loading evaluation data..." />}
      {summary.error && <ErrorState message={summary.error} />}
      {results.error && <ErrorState message={results.error} />}

      {summary.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Total Eval Runs" value={totalRuns} icon={ListChecks} />
          <KpiCard label="Passed" value={totalPassed} icon={ClipboardCheck} />
          <KpiCard label="Failed" value={totalFailed} icon={XCircle} />
          <KpiCard
            label="Avg Judge Score"
            value={avgJudgeOverall != null ? `${avgJudgeOverall.toFixed(2)} / 5` : "Not judged"}
            icon={Sparkles}
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {summaryRows.map((agent) => (
          <Card key={agent.agent_key}>
            <CardBody className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-[var(--ric-text-primary)]">
                  {AGENT_NAME_BY_KEY[agent.agent_key] ?? agent.agent_name}
                </p>
                <button
                  type="button"
                  onClick={() => handleRun(agent.agent_key)}
                  disabled={runningAgent !== null}
                  className="rounded-lg border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)] disabled:opacity-50"
                >
                  {runningAgent === agent.agent_key ? "Running..." : "Run"}
                </button>
              </div>

              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Runs</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.total_runs}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Passed</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.passed}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Failed</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.failed}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Judge Score</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">
                    {agent.avg_judge_overall != null ? agent.avg_judge_overall.toFixed(2) : "--"}
                  </p>
                </div>
              </div>

              <p className="text-xs text-[var(--ric-text-secondary)]">
                {agent.last_run_at
                  ? `Last run: ${new Date(agent.last_run_at).toLocaleString()}`
                  : "Not evaluated yet."}
              </p>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardBody>
          <p className="mb-3 text-sm font-semibold text-[var(--ric-text-primary)]">Recent evaluation results</p>
          <EvaluationResultTable results={results.data ?? []} />
        </CardBody>
      </Card>

      <DisclaimerFooter text="Every evaluation result here comes from a real call to the agent's own code against a fixed test question -- no result is simulated or fabricated. Judge scores require OPENAI_API_KEY to be configured." />
    </div>
  );
}
