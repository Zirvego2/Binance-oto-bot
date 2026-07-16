"use client";

import { useQuery } from "@tanstack/react-query";
import { enhancedApi } from "@/lib/api";

export default function CoinProfilesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["symbol-profiles"],
    queryFn: () => enhancedApi.symbolProfiles(),
  });

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-bold">Coin Profilleri</h1>
      <p className="text-sm text-muted-foreground">Shadow modda kucuk katki — otomatik engelleme yok</p>
      {isLoading ? (
        <p className="text-muted-foreground">Yukleniyor...</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card/80">
              <tr className="text-left text-muted-foreground">
                <th className="p-2">Coin</th>
                <th className="p-2">Islem</th>
                <th className="p-2">Basari</th>
                <th className="p-2">PF</th>
                <th className="p-2">Beklenen</th>
                <th className="p-2">Max DD</th>
                <th className="p-2">LONG WR</th>
                <th className="p-2">SHORT WR</th>
                <th className="p-2">Guven</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((p) => (
                <tr key={p.symbol} className="border-t border-border/50">
                  <td className="p-2 font-medium">{p.symbol}</td>
                  <td className="p-2">{p.total_trades}</td>
                  <td className="p-2">{p.win_rate.toFixed(1)}%</td>
                  <td className="p-2">{p.profit_factor.toFixed(2)}</td>
                  <td className="p-2">{p.expectancy.toFixed(4)}</td>
                  <td className="p-2">{p.max_drawdown.toFixed(4)}</td>
                  <td className="p-2">{p.long_win_rate.toFixed(1)}%</td>
                  <td className="p-2">{p.short_win_rate.toFixed(1)}%</td>
                  <td className="p-2">{p.confidence_level.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
