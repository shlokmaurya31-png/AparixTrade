"use client";

import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AparixBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { AparixTable } from "@/components/aparix/AparixTable";
import {
  ALL_ROLES,
  api,
  ApiError,
  type AdminAuditLog,
  type AdminUser,
  type DataQualityFinding,
  type UserRole,
} from "@/lib/api";
import { useCurrentUser } from "@/lib/use-auth";

const STATUS_TONE: Record<DataQualityFinding["status"], "positive" | "warning" | "negative" | "neutral"> = {
  GOOD: "positive",
  WARNING: "warning",
  STALE: "warning",
  INVALID: "negative",
  UNKNOWN: "neutral",
};

export default function AdminPage() {
  const { data: user, isLoading: userLoading } = useCurrentUser();
  const queryClient = useQueryClient();
  const [roleError, setRoleError] = useState<string | null>(null);

  const enabled = Boolean(user?.is_admin);
  const users = useQuery({ queryKey: ["admin-users"], queryFn: api.admin.users, enabled, retry: false });
  const updateRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) => api.admin.updateUserRole(userId, role),
    onSuccess: () => {
      setRoleError(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (err) => setRoleError(err instanceof ApiError ? err.message : "Couldn't update role."),
  });
  const auditLogs = useQuery({ queryKey: ["admin-audit-logs"], queryFn: api.admin.auditLogs, enabled, retry: false });
  const aiUsage = useQuery({ queryKey: ["admin-ai-usage"], queryFn: api.admin.aiUsage, enabled, retry: false });
  const health = useQuery({ queryKey: ["admin-system-health"], queryFn: api.admin.systemHealth, enabled, retry: false });
  const dataQuality = useQuery({
    queryKey: ["admin-data-quality"],
    queryFn: api.admin.dataQuality,
    enabled,
    retry: false,
  });

  if (userLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;

  if (!user?.is_admin) {
    return (
      <AparixCard title="Access denied">
        <p className="text-sm text-muted-foreground">
          This account isn&rsquo;t an admin. Add your email to <code>ADMIN_EMAILS</code> in the API&rsquo;s
          environment (or have an existing admin grant the <code>admin</code> role) and log in again — see the README.
        </p>
      </AparixCard>
    );
  }

  const anyError = [users, auditLogs, aiUsage, health, dataQuality].find((q) => q.isError);
  if (anyError) {
    return (
      <AparixCard title="Couldn't load admin data">
        <p className="text-sm text-negative">
          {anyError.error instanceof ApiError ? anyError.error.message : "Something went wrong."}
        </p>
      </AparixCard>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Admin</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <AparixCard>
          <AparixMetric label="Users" value={String(health.data?.users_count ?? "—")} />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Portfolios" value={String(health.data?.portfolios_count ?? "—")} />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Securities" value={String(health.data?.securities_count ?? "—")} />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Events" value={String(health.data?.events_count ?? "—")} />
        </AparixCard>
        <AparixCard>
          <AparixMetric
            label="DB backend"
            value={health.data?.database_backend ?? "—"}
            hint={
              health.data?.last_market_tick
                ? `Last tick ${new Date(health.data.last_market_tick).toLocaleTimeString()}`
                : "No ticks yet"
            }
          />
        </AparixCard>
      </div>

      <AparixCard title="Data quality">
        <AparixTable<DataQualityFinding>
          columns={[
            { header: "Check", render: (f) => f.check },
            {
              header: "Status",
              render: (f) => <AparixBadge tone={STATUS_TONE[f.status]}>{f.status}</AparixBadge>,
            },
            { header: "Detail", render: (f) => <span className="text-muted-foreground">{f.detail}</span> },
          ]}
          rows={dataQuality.data ?? []}
          keyFor={(f) => f.check}
        />
      </AparixCard>

      <AparixCard title="AI usage">
        <div className="mb-3 flex gap-6 text-sm">
          <span>
            Sessions: <span className="font-mono-nums font-medium">{aiUsage.data?.total_sessions ?? 0}</span>
          </span>
          <span>
            Messages: <span className="font-mono-nums font-medium">{aiUsage.data?.total_messages ?? 0}</span>
          </span>
        </div>
        <AparixTable
          columns={[
            { header: "Tool", render: (t: { tool_name: string; count: number }) => t.tool_name },
            { header: "Calls", align: "right", render: (t) => t.count },
          ]}
          rows={aiUsage.data?.tool_usage ?? []}
          keyFor={(t) => t.tool_name}
          emptyMessage="No AI tool calls yet."
        />
      </AparixCard>

      <AparixCard title="Users">
        {roleError && <p className="mb-2 text-sm text-negative">{roleError}</p>}
        <AparixTable<AdminUser>
          columns={[
            { header: "Email", render: (u) => u.email },
            { header: "Name", render: (u) => u.full_name },
            {
              header: "Role",
              render: (u) => {
                const isSelf = u.id === user?.id;
                // Only a super_admin may grant/revoke super_admin, or touch
                // an existing super_admin's role — matches the server-side
                // guard exactly (domains/admin/service.py::update_user_role),
                // disabled here too so the control doesn't invite a 403.
                const touchesSuperAdmin = u.role === "super_admin";
                const disabled =
                  isSelf || updateRole.isPending || (touchesSuperAdmin && user?.role !== "super_admin");
                return (
                  <select
                    value={u.role}
                    disabled={disabled}
                    title={isSelf ? "Ask another admin to change your own role" : undefined}
                    onChange={(e) => updateRole.mutate({ userId: u.id, role: e.target.value as UserRole })}
                    className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {ALL_ROLES.filter((r) => r !== "super_admin" || user?.role === "super_admin" || u.role === r).map(
                      (r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      )
                    )}
                  </select>
                );
              },
            },
            { header: "Experience", render: (u) => u.experience_level },
            { header: "Complexity", align: "right", render: (u) => u.complexity_level },
            { header: "Portfolios", align: "right", render: (u) => u.portfolio_count },
            { header: "Joined", render: (u) => new Date(u.created_at).toLocaleDateString() },
          ]}
          rows={users.data ?? []}
          keyFor={(u) => u.id}
        />
      </AparixCard>

      <AparixCard title="Audit log">
        <AparixTable<AdminAuditLog>
          columns={[
            { header: "Action", render: (l) => l.action },
            { header: "Result", render: (l) => l.result },
            { header: "When", render: (l) => new Date(l.created_at).toLocaleString() },
          ]}
          rows={auditLogs.data ?? []}
          keyFor={(l) => l.id}
        />
      </AparixCard>
    </div>
  );
}
