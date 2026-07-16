"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, RefreshCw } from "lucide-react";
import { enhancedApi } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";

export default function MarketRegimePage() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["market-regime-current"],
    queryFn: () => enhancedApi.marketRegimeCurrent(),
    refetchInterval: 30000,
  });
  const { data: history } = useQuery({
    queryKey: ["market-regime-history"],
    queryFn: () => enhancedApi.marketRegimeHistory(30),
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Piyasa Rejimi</h1>
          <p className="text-sm text-muted-foreground">Gelismis rejim motoru — emir acmaz, stratejiye agirlik verir</p>
        </div>
        <button onClick={() => refetch()} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} /> Yenile
        </button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Yukleniyor...</p>
      ) : data ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <MetricCard label="Rejim" value={data.regime} highlight />
          <MetricCard label="Guven" value={`${data.confidence.toFixed(1)}%`} />
          <MetricCard label="Trend Gucu" value={`${data.trend_strength.toFixed(1)}%`} />
          <MetricCard label="Volatilite" value={`${data.volatility_score.toFixed(1)}%`} />
          <MetricCard label="Breadth" value={`${data.breadth_score.toFixed(1)}%`} />
          <MetricCard label="Risk-Off" value={`${data.risk_off_score.toFixed(1)}%`} />
        </div>
      ) : null}

      {data?.reasons?.length ? (
        <div className="rounded-xl border border-border bg-card/50 p-4">
          <h2 className="mb-2 font-semibold">Rejim Nedenleri</h2>
          <ul className="list-inside list-disc text-sm text-muted-foreground">
            {data.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded-xl border border-border bg-card/50 p-4">
        <h2 className="mb-3 flex items-center gap-2 font-semibold">
          <Activity className="h-4 w-4" /> Rejim Gecmisi
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="p-2">Tarih</th>
                <th className="p-2">Rejim</th>
                <th className="p-2">Guven</th>
                <th className="p-2">Volatilite</th>
              </tr>
            </thead>
            <tbody>
              {(history ?? []).map((h) => (
                <tr key={h.id ?? h.created_at} className="border-b border-border/50">
                  <td className="p-2">{h.created_at ? formatDateTime(h.created_at) : "-"}</td>
                  <td className="p-2 font-medium">{h.regime}</td>
                  <td className="p-2">{h.confidence.toFixed(1)}%</td>
                  <td className="p-2">{h.volatility_score.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={cn("rounded-xl border p-4", highlight ? "border-primary/40 bg-primary/5" : "border-border bg-card/50")}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold">{value}</p>
    </div>
  );
}
