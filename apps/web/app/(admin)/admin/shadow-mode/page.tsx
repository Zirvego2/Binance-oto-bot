"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Play, Square } from "lucide-react";

import {
  AdminPageHeader,
  AdminSectionCard,
  AdminStatCard,
} from "@/components/admin/admin-ui";
import { enhancedApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function AdminShadowModePage() {
  const queryClient = useQueryClient();
  const { data: status } = useQuery({
    queryKey: ["admin", "shadow-status"],
    queryFn: () => enhancedApi.shadowStatus(),
    refetchInterval: 30_000,
  });
  const { data: comparison } = useQuery({
    queryKey: ["admin", "shadow-comparison"],
    queryFn: () => enhancedApi.shadowComparison(),
    refetchInterval: 30_000,
  });

  const startShadow = useMutation({
    mutationFn: () => enhancedApi.shadowStart(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "shadow-status"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "shadow-comparison"] });
    },
  });
  const stopShadow = useMutation({
    mutationFn: () => enhancedApi.shadowStop(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "shadow-status"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "shadow-comparison"] });
    },
  });

  const active = status?.shadow_mode_active ?? false;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Shadow Mode"
        description="Platform geneli gelismis motor karsilastirmasi — gercek emir gonderilmez, yalnizca platform yoneticisi yonetir."
        actions={
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={active || startShadow.isPending}
              onClick={() => startShadow.mutate()}
              className="gap-2"
            >
              <Play className="h-4 w-4" />
              Baslat
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!active || stopShadow.isPending}
              onClick={() => stopShadow.mutate()}
              className="gap-2"
            >
              <Square className="h-4 w-4" />
              Durdur
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <AdminStatCard title="Shadow Aktif" value={active ? "Evet" : "Hayir"} icon={Activity} />
        <AdminStatCard title="Toplam Karar" value={status?.total_decisions ?? 0} icon={CheckCircle2} />
        <AdminStatCard
          title="Uyusma Orani"
          value={`${(comparison?.agreement_rate_pct ?? 0).toFixed(1)}%`}
          icon={CheckCircle2}
          tone="success"
        />
        <AdminStatCard
          title="Fark Orani"
          value={`${(comparison?.disagreement_rate_pct ?? 0).toFixed(1)}%`}
          icon={AlertTriangle}
          tone="warning"
        />
      </div>

      <AdminSectionCard title="Son Karsilastirmalar" description="Mevcut motor vs gelismis motor sembol secimleri" noPadding>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/50 text-left text-muted-foreground">
              <th className="p-3">Mevcut</th>
              <th className="p-3">Gelismis</th>
              <th className="p-3">Fark Nedeni</th>
            </tr>
          </thead>
          <tbody>
            {(comparison?.recent ?? []).length === 0 && (
              <tr>
                <td colSpan={3} className="p-6 text-center text-muted-foreground">
                  Henuz karsilastirma kaydi yok
                </td>
              </tr>
            )}
            {(comparison?.recent ?? []).map((r, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="p-3 font-medium">{r.current ?? "-"}</td>
                <td className="p-3 font-medium">{r.enhanced ?? "-"}</td>
                <td className="p-3 text-xs text-muted-foreground">{r.disagreement ?? "Ayni"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </AdminSectionCard>
    </div>
  );
}
