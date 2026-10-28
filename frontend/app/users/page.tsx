"use client";

/**
 * User Management workspace. This project has NO real authentication or
 * authorization system (see components/layout/UserMenu.tsx -- "Sign out"
 * is disabled and explicitly labeled "not a real signed-in session"). No
 * backend enforcement of any kind exists for the roles/permissions shown
 * here, so this page is entirely demonstration UI, clearly labeled as
 * such throughout, and nothing on it is interactive in a way that could
 * be mistaken for a real, enforced access-control change: role/permission
 * state is session-only (component state), never sent to the server.
 */

import { useState } from "react";
import { Check, Minus } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Card, CardBody, CardHeader } from "@/components/retail/Card";
import { DisclaimerFooter } from "@/components/retail/DisclaimerFooter";

interface DemoUser {
  id: string;
  name: string;
  role: "Admin" | "Analyst" | "Viewer";
  workspaceAccess: string;
  status: "Active" | "Invited";
}

const DEMO_USERS: DemoUser[] = [
  { id: "u1", name: "Demo User", role: "Admin", workspaceAccess: "Synthetic Demo Workspace", status: "Active" },
  { id: "u2", name: "Demo Analyst", role: "Analyst", workspaceAccess: "Synthetic Demo Workspace", status: "Active" },
  { id: "u3", name: "Demo Viewer", role: "Viewer", workspaceAccess: "Synthetic Demo Workspace", status: "Invited" },
];

const PERMISSIONS = [
  "View all workspaces",
  "Use Ask Retail AI",
  "View Agent Monitoring & Execution History",
  "View Audit Log",
  "Manage users & roles (demo only -- not enforced)",
];

const ROLE_PERMISSIONS: Record<DemoUser["role"], boolean[]> = {
  Admin: [true, true, true, true, true],
  Analyst: [true, true, true, false, false],
  Viewer: [true, true, false, false, false],
};

const ROLE_TONE: Record<DemoUser["role"], BadgeTone> = {
  Admin: "info",
  Analyst: "success",
  Viewer: "neutral",
};

export default function UsersPage() {
  const [users] = useState(DEMO_USERS);

  const userColumns: DataTableColumn<DemoUser>[] = [
    { key: "name", header: "User", sortable: true, accessor: (r) => r.name },
    {
      key: "role",
      header: "Role",
      sortable: true,
      accessor: (r) => r.role,
      render: (r) => <Badge label={r.role} tone={ROLE_TONE[r.role]} />,
    },
    { key: "workspace", header: "Workspace Access", accessor: (r) => r.workspaceAccess },
    {
      key: "status",
      header: "Status",
      accessor: (r) => r.status,
      render: (r) => <Badge label={r.status} tone={r.status === "Active" ? "success" : "warning"} />,
    },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[var(--ric-text-primary)]">User Management</h1>
        <p className="mt-1 text-sm text-[var(--ric-text-secondary)]">
          Users, roles, permissions, and workspace access for this deployment.
        </p>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
        <strong>Demonstration UI only:</strong> this project has no real authentication or authorization system.
        The users, roles, and permissions below are illustrative, session-only data with no backend persistence or
        enforcement -- nothing on this page grants, revokes, or changes real access to anything. The top bar&apos;s
        user menu and organization switcher are the same cosmetic placeholders described there.
      </div>

      <Card>
        <CardHeader title="Users" subtitle="Demo data -- not a real user directory." />
        <CardBody>
          <DataTable columns={userColumns} rows={users} rowKey={(r) => r.id} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Roles & Permissions"
          subtitle="Demo role definitions -- illustrative only, not enforced by any backend."
        />
        <CardBody>
          <div className="overflow-x-auto rounded-md border border-[var(--ric-border)]">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[var(--ric-page-bg)]">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
                    Permission
                  </th>
                  {(["Admin", "Analyst", "Viewer"] as const).map((role) => (
                    <th
                      key={role}
                      className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]"
                    >
                      {role}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--ric-border)]">
                {PERMISSIONS.map((permission, i) => (
                  <tr key={permission}>
                    <td className="px-3 py-2 text-[var(--ric-text-primary)]">{permission}</td>
                    {(["Admin", "Analyst", "Viewer"] as const).map((role) => (
                      <td key={role} className="px-3 py-2 text-center">
                        {ROLE_PERMISSIONS[role][i] ? (
                          <Check className="mx-auto h-4 w-4 text-emerald-600" aria-hidden="true" />
                        ) : (
                          <Minus className="mx-auto h-4 w-4 text-[var(--ric-text-secondary)]" aria-hidden="true" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Workspace Access" subtitle="This demo has exactly one workspace." />
        <CardBody>
          <p className="text-sm text-[var(--ric-text-primary)]">
            <strong>Synthetic Demo Workspace</strong> -- all {users.length} demo user(s) above have access to this
            single workspace. Multi-workspace access control is not implemented in this project (see
            components/layout/WorkspaceSelector.tsx).
          </p>
        </CardBody>
      </Card>

      <DisclaimerFooter text="This entire page is demonstration UI with no backend enforcement. Treat nothing here as a real access-control system." />
    </div>
  );
}
