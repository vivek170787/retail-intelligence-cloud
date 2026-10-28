"use client";

/**
 * Organization & Workspace settings. This project has no persisted
 * settings store anywhere in its backend -- every field below is local
 * component state only. Edits are never sent to the server and are lost
 * on reload; this is made explicit in the banner and next to the save
 * control, the same honesty standard as every other cosmetic control in
 * this app's top bar (see components/layout/TopNav.tsx, UserMenu.tsx).
 *
 * Business Unit Configuration: this dataset has no business-unit field
 * anywhere (products.csv, stores.csv, or any other file) -- it is
 * reported as unsupported rather than backed by an invented hierarchy.
 */

import { useState } from "react";
import { Info } from "lucide-react";

import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-[var(--ric-text-secondary)]">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-3 py-1.5 text-sm text-[var(--ric-text-primary)] outline-none focus:border-[var(--ric-primary)]"
      />
    </label>
  );
}

export default function SettingsPage() {
  const [orgName, setOrgName] = useState("Demo Retail Co.");
  const [industry, setIndustry] = useState("Retail");
  const [timezone, setTimezone] = useState("Asia/Kolkata");

  const [workspaceName, setWorkspaceName] = useState("Synthetic Demo Workspace");
  const [currency, setCurrency] = useState("INR");

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">Organization & Workspace</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Organization profile, workspace settings, and business unit configuration.
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          <strong>Demonstration UI:</strong> this project has no backend settings store. Fields below are editable
          in this browser tab only -- nothing is saved, and changes are lost on reload or in any other tab/session.
        </span>
      </div>

      <Card>
        <CardHeader title="Organization Profile" subtitle="Session-only -- not persisted." />
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField label="Organization name" value={orgName} onChange={setOrgName} />
          <TextField label="Industry" value={industry} onChange={setIndustry} />
          <TextField label="Default time zone" value={timezone} onChange={setTimezone} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Workspace Settings" subtitle="Session-only -- not persisted." />
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField label="Workspace name" value={workspaceName} onChange={setWorkspaceName} />
          <TextField label="Default currency" value={currency} onChange={setCurrency} />
          <div className="sm:col-span-2">
            <span className="text-xs font-medium text-[var(--ric-text-secondary)]">Data source</span>
            <p className="mt-1 text-sm text-[var(--ric-text-primary)]">
              Local synthetic CSV dataset (<code>data/*.csv</code>) -- see Data Sources & Integrations for the full
              connector list.
            </p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Business Unit Configuration" />
        <CardBody>
          <p className="text-sm text-[var(--ric-text-primary)]">
            Not supported by this dataset -- there is no business-unit field anywhere in products.csv, stores.csv,
            or any other dataset this project reads, so no business unit hierarchy is shown here rather than one
            being invented.
          </p>
          <p className="mt-2 text-xs text-[var(--ric-text-secondary)]">
            The closest existing structures in the real data are each product&apos;s <code>category</code> (see the
            Inventory Intelligence workspace) and each store&apos;s <code>region</code> field (stores.csv) -- neither
            is currently exposed as a configurable business-unit grouping through this API.
          </p>
        </CardBody>
      </Card>

      <DisclaimerFooter text="Nothing on this page is persisted to a backend. Treat all fields above as a local preview only." />
    </div>
  );
}
