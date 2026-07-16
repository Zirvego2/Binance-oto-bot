"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  ListOrdered,
  Percent,
  Coins,
  Activity,
  AlertCircle,
} from "lucide-react";

import { dashboardApi } from "@/lib/api";
import { useCurrentAdmin } from "@/hooks/use-auth";
import { useDashboardWs } from "@/hooks/use-dashboard-ws";
import { formatDateTimeShort, formatPct, formatTry, formatUsdt, pnlColorClass } from "@/lib/utils";
import { DashboardCharts } from "@/components/dashboard/dashboard-charts";
import { MembershipStatusBanner } from "@/components/shared/membership-status";
import { PageHeader } from "@/components/shared/page-header";
import { WorkerStatusBanner } from "@/components/shared/worker-status-banner";
import { StatCard } from "@/components/shared/stat-card";
import { UsdtWithTry } from "@/components/shared/usdt-with-try";
import { SideBadge } from "@/components/shared/side-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function DashboardPage() {
  const { data: admin } = useCurrentAdmin();
  const { data: initialDashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    refetchInterval: 10_000,
  });
  const { data: statistics } = useQuery({
    queryKey: ["dashboard", "statistics"],
    queryFn: () => dashboardApi.statistics(14),
  });
  const { data: wsData, connected } = useDashboardWs();

  const dashboard = wsData?.dashboard ?? initialDashboard;
  const positions = wsData?.open_positions ?? [];
  const tryRate = dashboard?.usdt_try_rate;

  return (
    <div>
      <PageHeader
        title="Panel"
        description={connected ? "Gercek zamanli veri akisi aktif" : "Gercek zamanli baglanti kuruluyor..."}
      />

      <WorkerStatusBanner dashboard={dashboard} />

      <MembershipStatusBanner admin={admin} />

      {dashboard?.last_error_message && (
        <div className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Son hata</p>
            <p className="text-xs opacity-90">{dashboard.last_error_message}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Toplam Bakiye"
          value={formatUsdt(dashboard?.total_futures_balance_usdt)}
          tryLabel={formatTry(dashboard?.total_futures_balance_usdt, tryRate)}
          icon={Wallet}
        />
        <StatCard
          label="Kullanilabilir Bakiye"
          value={formatUsdt(dashboard?.available_usdt)}
          tryLabel={formatTry(dashboard?.available_usdt, tryRate)}
          icon={Coins}
        />
        <StatCard
          label="Kullanilan Teminat"
          value={formatUsdt(dashboard?.used_margin_usdt)}
          tryLabel={formatTry(dashboard?.used_margin_usdt, tryRate)}
          icon={Activity}
        />
        <StatCard label="Acik Pozisyon" value={dashboard?.open_positions_count ?? 0} icon={ListOrdered} />

        <StatCard
          label="Gunluk Gerceklesen PnL"
          value={formatUsdt(dashboard?.daily_realized_pnl_usdt)}
          tryLabel={formatTry(dashboard?.daily_realized_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(dashboard?.daily_realized_pnl_usdt)}
          icon={TrendingUp}
        />
        <StatCard
          label="Gunluk Gerceklesmeyen PnL"
          value={formatUsdt(dashboard?.daily_unrealized_pnl_usdt)}
          tryLabel={formatTry(dashboard?.daily_unrealized_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(dashboard?.daily_unrealized_pnl_usdt)}
          icon={TrendingDown}
        />
        <StatCard
          label="Toplam Net PnL"
          value={formatUsdt(dashboard?.total_net_pnl_usdt)}
          tryLabel={formatTry(dashboard?.total_net_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(dashboard?.total_net_pnl_usdt)}
          icon={TrendingUp}
        />
        <StatCard label="Kazanma Orani (bugun)" value={formatPct(dashboard?.win_rate_pct)} icon={Percent} />
      </div>

      <DashboardCharts statistics={statistics} />

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Acik Pozisyonlar (Gercek Zamanli)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Yon</TableHead>
                <TableHead>Giris Fiyati</TableHead>
                <TableHead>Mark Fiyati</TableHead>
                <TableHead>Gerceklesmeyen PnL</TableHead>
                <TableHead>ROI</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                    Acik pozisyon yok
                  </TableCell>
                </TableRow>
              )}
              {positions.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.symbol}</TableCell>
                  <TableCell>
                    <SideBadge side={p.side} />
                  </TableCell>
                  <TableCell>{formatUsdt(p.entry_price, 4)}</TableCell>
                  <TableCell>{formatUsdt(p.mark_price, 4)}</TableCell>
                  <TableCell className={pnlColorClass(p.unrealized_pnl)}>
                    <UsdtWithTry usdt={p.unrealized_pnl} usdtTryRate={tryRate} size="sm" />
                  </TableCell>
                  <TableCell className={pnlColorClass(p.roi_pct)}>{formatPct(p.roi_pct)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs text-muted-foreground">
        <InfoRow label="Worker" value={dashboard?.worker_connected ? "Aktif" : "Durdu"} />
        <InfoRow label="Son heartbeat" value={formatDateTimeShort(dashboard?.worker_heartbeat_at)} />
        <InfoRow label="Son analiz" value={formatDateTimeShort(dashboard?.last_analysis_at)} />
        <InfoRow label="Son sinyal" value={formatDateTimeShort(dashboard?.last_signal_at)} />
        <InfoRow label="Son emir" value={formatDateTimeShort(dashboard?.last_order_at)} />
        <InfoRow
          label="Toplam komisyon"
          value={formatUsdt(dashboard?.total_commission_usdt)}
          tryValue={formatTry(dashboard?.total_commission_usdt, tryRate)}
        />
      </div>
    </div>
  );
}

function InfoRow({ label, value, tryValue }: { label: string; value: string; tryValue?: string | null }) {
  return (
    <div className="rounded-md border border-border bg-card/40 px-3 py-2">
      <p className="uppercase tracking-wide">{label}</p>
      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <p className="text-sm text-foreground">{value}</p>
        {tryValue ? <p className="text-sm text-muted-foreground">{tryValue}</p> : null}
      </div>
    </div>
  );
}
