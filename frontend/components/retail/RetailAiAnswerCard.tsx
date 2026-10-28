"use client";

/**
 * Renders one Ask Retail AI answer -- the full structured result from
 * POST /retail-ai/query (RetailIntelligenceOrchestrator.handle_query()),
 * plus its optional AI narration. Every number/finding/action shown here
 * is already present in the response; this component only presents it --
 * no computation happens here, matching the orchestrator's own contract
 * ("return structured results, never duplicate agent calculations").
 *
 * The "At a glance" strip is deliberately built only from fields present
 * on every response regardless of category (severity, affected-entity
 * counts, action/gap counts) rather than parsing each category's
 * differently-shaped `evidence` object -- robust across all seven
 * categories without category-specific guessing.
 */

import { Sparkles } from "lucide-react";

import type { RetailAiQueryResponse } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DataGapsPanel } from "@/components/retail/DataGapsPanel";
import { EmptyState } from "@/components/retail/EmptyState";
import { EvidencePanel } from "@/components/retail/EvidencePanel";
import { KpiCard } from "@/components/retail/KpiCard";
import { SeverityBadge } from "@/components/retail/SeverityBadge";
import { StatusBadge } from "@/components/retail/StatusBadge";
import { DataTable } from "@/components/ui/DataTable";

export function RetailAiAnswerCard({ response }: { response: RetailAiQueryResponse }) {
  const affectedCount =
    response.affected_entities.skus.length +
    response.affected_entities.stores.length +
    response.affected_entities.orders.length;

  return (
    <Card>
      <CardHeader title={response.summary} subtitle={`"${response.query}" -- category: ${response.category}`} />
      <CardBody className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-[var(--ric-border)] p-3">
            <p className="text-xs text-[var(--ric-text-secondary)]">Severity</p>
            <div className="mt-1.5">
              <SeverityBadge value={response.severity} />
            </div>
          </div>
          <KpiCard label="Entities Affected" value={affectedCount} />
          <KpiCard label="Recommended Actions" value={response.recommended_actions.length} />
          <KpiCard label="Data Gaps" value={response.data_gaps_and_uncertainty.length} />
        </div>

        {/* ---- AI narration (optional, non-blocking enrichment) ---- */}
        {response.ai_narration.answer ? (
          <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-page-bg)] p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-[var(--ric-text-secondary)]">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              AI narration (narrates the structured result below -- never computes new numbers)
            </div>
            <p className="text-sm text-[var(--ric-text-primary)]">{response.ai_narration.answer}</p>
          </div>
        ) : (
          <p className="text-xs text-[var(--ric-text-secondary)]">
            {response.ai_narration.configured
              ? response.ai_narration.message
              : "AI narration not enabled for this deployment -- set OPENAI_API_KEY to add a natural-language summary. All structured findings below are available either way."}
          </p>
        )}

        {response.key_findings.length > 0 && (
          <div>
            <p className="mb-1 text-sm font-medium text-[var(--ric-text-primary)]">Key findings:</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
              {response.key_findings.map((finding, i) => (
                <li key={i}>{finding}</li>
              ))}
            </ul>
          </div>
        )}

        {affectedCount > 0 && (
          <div>
            <p className="mb-1 text-sm font-medium text-[var(--ric-text-primary)]">Affected entities (evidence):</p>
            <DataTable
              rowKey={(row) => row.type}
              columns={[
                { key: "type", header: "Type", widthClassName: "w-28", accessor: (row) => row.type },
                { key: "ids", header: "IDs", accessor: (row) => row.ids },
              ]}
              rows={[
                { type: "SKUs", ids: response.affected_entities.skus.slice(0, 20).join(", ") },
                { type: "Stores", ids: response.affected_entities.stores.slice(0, 20).join(", ") },
                { type: "Orders", ids: response.affected_entities.orders.slice(0, 20).join(", ") },
              ].filter((row) => row.ids.length > 0)}
            />
          </div>
        )}

        <div>
          <p className="mb-1 text-sm font-medium text-[var(--ric-text-primary)]">
            Recommended actions (human review required):
          </p>
          {response.recommended_actions.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-[var(--ric-text-primary)]">
              {response.recommended_actions.map((action, i) => (
                <li key={i}>{action}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No specific recommended actions for this query." />
          )}
        </div>

        <DataGapsPanel gaps={response.data_gaps_and_uncertainty} />
        <EvidencePanel evidence={response.evidence} />

        <div className="flex items-center gap-2">
          <p className="text-xs text-[var(--ric-text-secondary)]">Agents consulted:</p>
          {response.agents_used.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {response.agents_used.map((agent, i) => (
                <StatusBadge key={`${agent}-${i}`} label={agent} />
              ))}
            </div>
          ) : (
            <span className="text-xs text-[var(--ric-text-secondary)]">none</span>
          )}
        </div>

        <p className="text-xs text-[var(--ric-text-secondary)]">{response.disclaimer}</p>
      </CardBody>
    </Card>
  );
}
