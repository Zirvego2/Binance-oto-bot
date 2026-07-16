"use client";

import { useQuery } from "@tanstack/react-query";
import { enhancedApi } from "@/lib/api";

export default function TradeCandidatesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["trade-candidates"],
    queryFn: () => enhancedApi.tradeCandidates(),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-bold">Aday Karsilastirmasi</h1>
      <p className="text-sm text-muted-foreground">Risk ayarli firsat puani ile siralanmis adaylar</p>
      {isLoading ? (
        <p className="text-muted-foreground">Yukleniyor...</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card/80">
              <tr className="text-left text-muted-foreground">
                <th className="p-2">Sira</th>
                <th className="p-2">Coin</th>
                <th className="p-2">Yon</th>
                <th className="p-2">Sinyal</th>
                <th className="p-2">Risk</th>
                <th className="p-2">R/R</th>
                <th className="p-2">Rejim</th>
                <th className="p-2">Profil</th>
                <th className="p-2">Korelasyon</th>
                <th className="p-2">Final</th>
                <th className="p-2">Durum</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((c) => (
                <tr key={`${c.scan_id}-${c.rank}`} className={c.selected ? "bg-primary/10" : "border-t border-border/50"}>
                  <td className="p-2">{c.rank}</td>
                  <td className="p-2 font-medium">{c.symbol}</td>
                  <td className="p-2">{c.direction}</td>
                  <td className="p-2">{c.signal_score.toFixed(1)}</td>
                  <td className="p-2">{c.risk_score.toFixed(1)}</td>
                  <td className="p-2">{c.risk_reward_ratio.toFixed(2)}</td>
                  <td className="p-2">{c.regime_alignment_score.toFixed(1)}</td>
                  <td className="p-2">{c.symbol_profile_score.toFixed(1)}</td>
                  <td className="p-2">{c.correlation_penalty.toFixed(1)}</td>
                  <td className="p-2 font-semibold">{c.final_opportunity_score.toFixed(1)}</td>
                  <td className="p-2 text-xs">{c.selected ? "Secildi" : c.rejection_reason ?? "Red"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
