"use client";

/**
 * Data Quality workspace -- every number here comes from GET
 * /data-quality/report (data_quality/report.py), which recomputes the
 * same checks as the project's existing quality_checks.py script (SKU
 * consistency, store ID validity, non-negative quantities, duplicate
 * keys, missing values) live against the current data/*.csv contents,
 * plus data freshness for the three datasets that actually carry a date
 * column. Nothing here is cached, sampled, or fabricated.
 */

import { CalendarClock, CheckCircle2, Database, XCircle } from "lucide-react";

import { getDataQualityReport } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Badge } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";
import { ErrorState } from "@/components/retail/ErrorState";
import { KpiCard } from "@/components/retail/KpiCard";
import { LoadingState } from "@/components/retail/LoadingState";
import type {
  DataFreshnessEntry,
  DataQualityDatasetSummary,
  DataQualityValidationCheck,
} from "@/lib/types";

export default function DataQualityPage() {
  const report = useApi(() => getDataQualityReport(), []);
  const data = report.data;

  const totalRecords = data?.datasets.reduce((sum, d) => sum + d.record_count, 0) ?? 0;
  const datasetsWithMissing = data?.datasets.filter((d) => Object.keys(d.missing_value_counts).length > 0).length ?? 0;
  const failedChecks = data?.validation_checks.filter((c) => !c.passed).length ?? 0;

  const datasetColumns: DataTableColumn<DataQualityDatasetSummary>[] = [
    { key: "name", header: "Dataset", sortable: true, accessor: (r) => r.name },
    { key: "count", header: "Records", align: "right", sortable: true, accessor: (r) => r.record_count },
    {
      key: "missing",
      header: "Missing Values",
      accessor: (r) => Object.keys(r.missing_value_counts).length,
      render: (r) =>
        Object.keys(r.missing_value_counts).length === 0 ? (
          <Badge label="None" tone="success" />
        ) : (
          <span className="text-[var(--ric-text-primary)]">
            {Object.entries(r.missing_value_counts)
              .map(([col, count]) => `${col}: ${count}`)
              .join(", ")}
          </span>
        ),
    },
    {
      key: "duplicates",
      header: "Duplicate Records",
      align: "right",
      accessor: (r) => r.duplicate_record_count ?? "N/A",
      render: (r) =>
        r.duplicate_record_count == null ? (
          "N/A"
        ) : r.duplicate_record_count === 0 ? (
          <Badge label="0" tone="success" />
        ) : (
          <Badge label={String(r.duplicate_record_count)} tone="danger" />
        ),
    },
  ];

  const checkColumns: DataTableColumn<DataQualityValidationCheck>[] = [
    {
      key: "passed",
      header: "Result",
      sortable: true,
      accessor: (r) => (r.passed ? 1 : 0),
      render: (r) => (r.passed ? <Badge label="Pass" tone="success" dot /> : <Badge label="Fail" tone="danger" dot />),
    },
    { key: "check", header: "Validation Check", accessor: (r) => r.check },
    { key: "count", header: "Invalid Record Count", align: "right", sortable: true, accessor: (r) => r.invalid_count },
    {
      key: "examples",
      header: "Examples",
      accessor: (r) => r.examples.join(", "),
      render: (r) => (r.examples.length > 0 ? r.examples.join(", ") : "--"),
    },
  ];

  const freshnessColumns: DataTableColumn<DataFreshnessEntry>[] = [
    { key: "dataset", header: "Dataset", accessor: (r) => r.dataset },
    { key: "column", header: "Date Column", accessor: (r) => r.date_column },
    { key: "most_recent", header: "Most Recent Record Date", accessor: (r) => r.most_recent_date ?? "Unknown" },
    {
      key: "age",
      header: "Days Since Most Recent",
      align: "right",
      accessor: (r) => r.days_since_most_recent ?? -1,
      render: (r) => r.days_since_most_recent ?? "Unknown",
    },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Data Quality</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Missing data, invalid records, duplicates, freshness, and validation results, computed live against the
          current dataset.
        </p>
      </div>

      {report.loading && <LoadingState message="Loading data quality report..." />}
      {report.error && <ErrorState message={report.error} />}

      {data && (
        <>
          <div className="flex items-center gap-2">
            {data.overall_passed ? (
              <Badge label="All checks passing" tone="success" dot />
            ) : (
              <Badge label="One or more checks failing" tone="danger" dot />
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Datasets" value={data.datasets.length} icon={Database} />
            <KpiCard label="Total Records" value={totalRecords} icon={Database} />
            <KpiCard label="Failed Validation Checks" value={failedChecks} icon={XCircle} />
            <KpiCard label="Datasets with Missing Values" value={datasetsWithMissing} icon={CheckCircle2} />
          </div>

          <Card>
            <CardHeader title="Datasets" subtitle="Record counts, missing values, and duplicate records per dataset." />
            <CardBody>
              <DataTable columns={datasetColumns} rows={data.datasets} rowKey={(r) => r.name} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Validation Checks"
              subtitle="SKU/store reference integrity and non-negative-quantity checks -- the same checks quality_checks.py runs."
            />
            <CardBody>
              <DataTable columns={checkColumns} rows={data.validation_checks} rowKey={(r) => r.check} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Data Freshness"
              subtitle="Only shown for datasets that actually carry a date column -- never estimated for the rest."
            />
            <CardBody className="space-y-3">
              <DataTable columns={freshnessColumns} rows={data.data_freshness} rowKey={(r) => r.dataset} />
              <p className="flex items-start gap-1.5 text-xs text-[var(--ric-text-secondary)]">
                <CalendarClock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {data.note}
              </p>
            </CardBody>
          </Card>
        </>
      )}

      <DisclaimerFooter text="Every figure on this page is computed live from the current dataset -- nothing is cached, sampled, or fabricated." />
    </div>
  );
}
