"use client";

/**
 * Agent Feedback workspace -- the human-facing half of the AI feedback
 * loop. Shows REAL thumbs up/down submissions (collected on the Ask
 * Retail AI page via RetailAiAnswerCard) and the prompt adjustments
 * agent_feedback/retuning.py has automatically derived from them once
 * negative feedback for an agent crosses NEGATIVE_FEEDBACK_THRESHOLD.
 *
 * "Force retune" bypasses the threshold so this loop can be demonstrated
 * without needing to submit exactly N organic thumbs-down first -- it
 * still only uses real, already-submitted feedback comments (or a
 * generic fallback note when there are none), never a fabricated one.
 */

import { useState } from "react";
import { MessageSquareWarning, ThumbsDown, ThumbsUp, Wrench } from "lucide-react";

import { forceRetune, getFeedback, getFeedbackSummary, getPromptAdjustments } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AGENT_NAME_BY_KEY } from "@/components/retail/agentMonitoringLabels";
import { Card, CardBody } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { FeedbackTable } from "@/components/retail/FeedbackTable";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";

export default function AgentFeedbackPage() {
  const summary = useApi(() => getFeedbackSummary(), []);
  const feedback = useApi(() => getFeedback(), []);
  const adjustments = useApi(() => getPromptAdjustments(), []);
  const [retuningAgent, setRetuningAgent] = useState<string | null>(null);

  const summaryRows = summary.data ?? [];
  const totalUp = summaryRows.reduce((sum, a) => sum + a.up_count, 0);
  const totalDown = summaryRows.reduce((sum, a) => sum + a.down_count, 0);
  const agentsWithAdjustment = summaryRows.filter((a) => a.active_adjustment != null).length;

  async function handleForceRetune(agentKey: string) {
    setRetuningAgent(agentKey);
    try {
      await forceRetune(agentKey);
      await Promise.all([summary.refetch(), adjustments.refetch()]);
    } finally {
      setRetuningAgent(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Agent Feedback</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Human feedback on agent answers, and the prompt adjustments automatically derived from it once negative
          feedback for an agent crosses the threshold.
        </p>
      </div>

      <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-page-bg)] px-3 py-2.5 text-xs text-[var(--ric-text-secondary)]">
        Submit feedback from the thumbs up/down buttons on an Ask Retail AI answer. Every row and adjustment below
        is real, locally-logged data (<code>agent_feedback/store.py</code>) -- never simulated.
      </div>

      {(summary.loading || feedback.loading || adjustments.loading) && (
        <LoadingState message="Loading feedback data..." />
      )}
      {summary.error && <ErrorState message={summary.error} />}
      {feedback.error && <ErrorState message={feedback.error} />}
      {adjustments.error && <ErrorState message={adjustments.error} />}

      {summary.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Thumbs Up" value={totalUp} icon={ThumbsUp} />
          <KpiCard label="Thumbs Down" value={totalDown} icon={ThumbsDown} />
          <KpiCard label="Agents With Active Adjustment" value={agentsWithAdjustment} icon={MessageSquareWarning} />
          <KpiCard label="Total Adjustments Made" value={(adjustments.data ?? []).length} icon={Wrench} />
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
                  onClick={() => handleForceRetune(agent.agent_key)}
                  disabled={retuningAgent !== null}
                  className="rounded-lg border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-primary)] hover:bg-[var(--ric-page-bg)] disabled:opacity-50"
                >
                  {retuningAgent === agent.agent_key ? "Retuning..." : "Force retune"}
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Up</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.up_count}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Down</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.down_count}</p>
                </div>
                <div className="rounded-lg bg-[var(--ric-page-bg)] p-2">
                  <p className="text-xs text-[var(--ric-text-secondary)]">Total</p>
                  <p className="text-base font-semibold text-[var(--ric-text-primary)]">{agent.total}</p>
                </div>
              </div>

              <p className="text-xs text-[var(--ric-text-secondary)]">
                {agent.active_adjustment ? (
                  <>
                    <span className="font-medium text-[var(--ric-text-primary)]">Active adjustment: </span>
                    {agent.active_adjustment}
                  </>
                ) : (
                  "No active prompt adjustment."
                )}
              </p>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardBody>
          <p className="mb-3 text-sm font-semibold text-[var(--ric-text-primary)]">Recent feedback</p>
          <FeedbackTable feedback={feedback.data ?? []} />
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <p className="mb-3 text-sm font-semibold text-[var(--ric-text-primary)]">Prompt adjustments</p>
          <div className="space-y-2">
            {(adjustments.data ?? []).length === 0 && (
              <p className="text-sm text-[var(--ric-text-secondary)]">No prompt adjustments have been made yet.</p>
            )}
            {(adjustments.data ?? []).map((adj) => (
              <div key={adj.id} className="rounded-lg border border-[var(--ric-border)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-[var(--ric-text-primary)]">
                    {AGENT_NAME_BY_KEY[adj.agent_key] ?? adj.agent_key}
                  </p>
                  <p className="text-xs text-[var(--ric-text-secondary)]">
                    {new Date(adj.created_at).toLocaleString()} -- triggered by {adj.trigger_feedback_count}{" "}
                    feedback entr{adj.trigger_feedback_count === 1 ? "y" : "ies"}
                  </p>
                </div>
                <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{adj.adjustment_text}</p>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      <DisclaimerFooter text="Prompt adjustments are synthesized from real feedback comments via a fixed template -- never a second LLM call -- so this loop stays deterministic and works even without OPENAI_API_KEY configured." />
    </div>
  );
}
