"use client";

import { AlertTriangle, Cpu } from "lucide-react";

import type { DashboardOut } from "@/types/api";
import { formatDateTimeShort } from "@/lib/utils";

export function WorkerStatusBanner({ dashboard }: { dashboard: DashboardOut | null | undefined }) {
  if (!dashboard || dashboard.worker_connected) return null;

  const staleMinutes =
    dashboard.worker_stale_seconds != null ? Math.max(1, Math.round(dashboard.worker_stale_seconds / 60)) : null;

  return (
    <div className="mb-4 flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">Worker durdu — sinyal ve analiz uretilmiyor</p>
        <p className="mt-1 text-xs opacity-90">
          Son heartbeat: {formatDateTimeShort(dashboard.worker_heartbeat_at)}
          {staleMinutes != null ? ` (${staleMinutes} dk once)` : ""}. Supervisor otomatik yeniden baslatmayi
          deniyor; devam ederse{" "}
          <code className="rounded bg-destructive/10 px-1">scripts\start_bot.ps1</code> calistirin.
        </p>
      </div>
      <Cpu className="hidden h-5 w-5 shrink-0 opacity-60 sm:block" />
    </div>
  );
}
