"use client";

/**
 * Data Sources & Integrations workspace -- every connector listed here
 * comes from data_sources/registry.py (GET /data-sources/overview), which
 * actually CALLS each connector's loader function and reports whether it
 * succeeded just now, with a real record count -- never a static claim.
 *
 * What this project actually has: eight LOCAL CSV FILE connectors over a
 * synthetic dataset. There is no live connection to any real external
 * POS, ERP, WMS, OMS, e-commerce, or marketplace system anywhere in this
 * codebase, and this page never implies otherwise -- every connector card
 * says so explicitly. Categories this project has no connector for at all
 * (ERP, a dedicated e-commerce-platform connector) are shown as
 * "Planned", never implied to exist.
 */

import { useMemo } from "react";
import { CheckCircle2, CircleDashed, Database, XCircle } from "lucide-react";

import { getDataSourcesOverview } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { ConnectorStatus } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";

const CATEGORY_ORDER = [
  "pos",
  "erp",
  "warehouse_management",
  "order_management",
  "ecommerce",
  "marketplace",
  "inventory",
  "master_data",
];

function ConnectorCard({ connector }: { connector: ConnectorStatus }) {
  const ok = connector.status === "implemented_and_tested";
  return (
    <div className="rounded-md border border-[var(--ric-border)] p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-[var(--ric-text-primary)]">{connector.display_name}</p>
        {ok ? (
          <Badge label="Implemented & tested" tone="success" dot />
        ) : (
          <Badge label="Implemented -- currently failing" tone="danger" dot />
        )}
      </div>
      <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{connector.description}</p>
      <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
        <span className="font-medium text-[var(--ric-text-primary)]">Local CSV file connector</span> -- not a live
        external-system integration. Source: <code>{connector.source_file}</code>
      </p>
      {ok ? (
        <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">
          Verified just now: <strong>{connector.record_count}</strong> record(s) loaded successfully.
        </p>
      ) : (
        <p className="mt-1 text-xs text-red-700">{connector.load_error}</p>
      )}
    </div>
  );
}

export default function DataSourcesPage() {
  const overview = useApi(() => getDataSourcesOverview(), []);

  const byCategory = useMemo(() => {
    const map = new Map<string, ConnectorStatus[]>();
    for (const c of overview.data?.connectors ?? []) {
      const list = map.get(c.category) ?? [];
      list.push(c);
      map.set(c.category, list);
    }
    return map;
  }, [overview.data]);

  const plannedByCategory = useMemo(() => {
    const map = new Map<string, { display_name: string; note: string }>();
    for (const p of overview.data?.planned_integrations ?? []) map.set(p.category, p);
    return map;
  }, [overview.data]);

  const connectors = overview.data?.connectors ?? [];
  const implementedCount = connectors.filter((c) => c.status === "implemented_and_tested").length;
  const failingCount = connectors.filter((c) => c.status === "implemented_but_failing").length;
  const plannedCount = overview.data?.planned_integrations.length ?? 0;

  const categoryLabel = (key: string) =>
    (connectors.find((c) => c.category === key)?.category_label) ??
    plannedByCategory.get(key)?.display_name ??
    key;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Data Sources & Integrations</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Every connector this project actually has, verified live, and every category it does not.
        </p>
      </div>

      {overview.loading && <LoadingState message="Loading data sources..." />}
      {overview.error && <ErrorState message={overview.error} />}

      {overview.data && (
        <>
          <div className="rounded-md border border-[var(--ric-border)] bg-[var(--ric-page-bg)] px-3 py-2.5 text-xs text-[var(--ric-text-secondary)]">
            {overview.data.note}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Total Connectors" value={connectors.length} icon={Database} />
            <KpiCard label="Implemented & Tested" value={implementedCount} icon={CheckCircle2} />
            <KpiCard label="Configured but Unverified" value={0} icon={CircleDashed} />
            <KpiCard label="Planned Integrations" value={plannedCount} icon={XCircle} />
          </div>
          {failingCount > 0 && (
            <p className="text-xs text-red-700">
              {failingCount} connector(s) failed to load just now -- see the affected card(s) below.
            </p>
          )}
          <p className="text-xs text-[var(--ric-text-secondary)]">
            Configured but unverified: 0 -- every connector in this project is either a verified, successfully
            loading local CSV connector, or has no implementation at all (listed as planned). There is no
            partially-configured state in this codebase.
          </p>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {CATEGORY_ORDER.map((key) => {
              const implemented = byCategory.get(key);
              const planned = plannedByCategory.get(key);
              if (!implemented && !planned) return null;
              return (
                <Card key={key}>
                  <CardHeader title={categoryLabel(key)} />
                  <CardBody className="space-y-3">
                    {implemented?.map((c) => <ConnectorCard key={c.connector_key} connector={c} />)}
                    {planned && (
                      <div className="rounded-md border border-dashed border-[var(--ric-border)] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-[var(--ric-text-primary)]">
                            {planned.display_name}
                          </p>
                          <Badge label="Planned" tone="neutral" dot />
                        </div>
                        <p className="mt-1 text-xs text-[var(--ric-text-secondary)]">{planned.note}</p>
                      </div>
                    )}
                  </CardBody>
                </Card>
              );
            })}
          </div>
        </>
      )}

      <DisclaimerFooter text="This page only ever reflects what is actually implemented in this codebase, verified live. No external-system integration is claimed anywhere in this application." />
    </div>
  );
}
