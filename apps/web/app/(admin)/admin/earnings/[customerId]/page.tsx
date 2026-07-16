"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Briefcase,
  History,
  Loader2,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatCard,
  botStatusBadge,
} from "@/components/admin/admin-ui";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { SideBadge, StatusBadge } from "@/components/shared/side-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type {
  AdminTradeOut,
  CustomerEarningsPeriodOut,
  PositionOut,
} from "@/types/api";
import {
  cn,
  formatDateTimeShort,
  formatNumber,
  formatPct,
  formatUsdt,
  pnlColorClass,
} from "@/lib/utils";

const CLOSE_REASON_LABEL: Record<string, string> = {
  STOP_LOSS: "Zarar Durdur",
  TAKE_PROFIT: "Kar Al",
  MANUAL: "Manuel",
  EMERGENCY_STOP: "Acil Durdurma",
  LIQUIDATION: "Likidasyon",
  TRAILING_STOP: "Trailing Stop",
  RECONCILIATION: "Mutabakat",
  UNKNOWN: "Bilinmiyor",
};

function pnlClass(value: string | number) {
  const n = Number(value);
  if (n > 0) return "text-emerald-600 dark:text-emerald-400";
  if (n < 0) return "text-destructive";
  return "text-muted-foreground";
}

function PnlValue({ value, suffix = " USDT" }: { value: string | number; suffix?: string }) {
  const n = Number(value);
  return (
    <span className={cn("font-semibold tabular-nums", pnlClass(value))}>
      {n >= 0 ? "+" : ""}
      {formatNumber(n, 2)}
      {suffix}
    </span>
  );
}

function PeriodMiniCard({ label, period }: { label: string; period: CustomerEarningsPeriodOut }) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1">
        <PnlValue value={period.net_pnl_usdt} />
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {period.trades_count} islem · Win {formatNumber(period.win_rate_pct, 1)}%
      </p>
    </div>
  );
}

function PositionsTable({ items, loading }: { items: PositionOut[]; loading?: boolean }) {
  if (loading) return <AdminLoading />;
  if (!items.length) return <AdminEmptyState title="Pozisyon bulunamadi" />;

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Sembol</TableHead>
          <TableHead>Yon</TableHead>
          <TableHead>Durum</TableHead>
          <TableHead>Mod</TableHead>
          <TableHead>Marjin</TableHead>
          <TableHead>Giris</TableHead>
          <TableHead>Mark / Cikis</TableHead>
          <TableHead>PnL / ROI</TableHead>
          <TableHead>Acilis</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((pos) => (
          <TableRow key={pos.id}>
            <TableCell className="font-medium">{pos.symbol}</TableCell>
            <TableCell>
              <SideBadge side={pos.side} />
            </TableCell>
            <TableCell>
              <StatusBadge status={pos.status} />
            </TableCell>
            <TableCell>
              <Badge variant="outline" className="text-[10px] uppercase">
                {pos.bot_mode}
              </Badge>
            </TableCell>
            <TableCell className="tabular-nums">{formatUsdt(pos.margin_usdt)}</TableCell>
            <TableCell className="tabular-nums text-sm">{formatNumber(pos.entry_price, 4)}</TableCell>
            <TableCell className="tabular-nums text-sm">
              {pos.status === "OPEN"
                ? formatNumber(pos.mark_price ?? pos.entry_price, 4)
                : formatNumber(pos.mark_price ?? pos.entry_price, 4)}
            </TableCell>
            <TableCell>
              <div className={cn("tabular-nums text-sm font-medium", pnlColorClass(pos.unrealized_pnl))}>
                {formatUsdt(pos.unrealized_pnl)}
              </div>
              <div className={cn("text-xs tabular-nums", pnlColorClass(pos.roi_pct))}>
                {formatPct(pos.roi_pct)}
              </div>
            </TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
              {formatDateTimeShort(pos.opened_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TradesTable({ items, loading }: { items: AdminTradeOut[]; loading?: boolean }) {
  if (loading) return <AdminLoading />;
  if (!items.length) return <AdminEmptyState title="Islem bulunamadi" />;

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Sembol</TableHead>
          <TableHead>Yon</TableHead>
          <TableHead>Mod</TableHead>
          <TableHead>Net PnL</TableHead>
          <TableHead>ROI</TableHead>
          <TableHead>Marjin</TableHead>
          <TableHead>Kapanis</TableHead>
          <TableHead>Neden</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((trade) => (
          <TableRow key={trade.id}>
            <TableCell className="font-medium">{trade.symbol}</TableCell>
            <TableCell>
              <SideBadge side={trade.side} />
            </TableCell>
            <TableCell>
              <Badge variant="outline" className="text-[10px] uppercase">
                {trade.bot_mode}
              </Badge>
            </TableCell>
            <TableCell className={cn("tabular-nums font-medium", pnlColorClass(trade.net_pnl_usdt))}>
              {formatUsdt(trade.net_pnl_usdt)}
            </TableCell>
            <TableCell className={cn("tabular-nums", pnlColorClass(trade.net_roi_pct))}>
              {formatPct(trade.net_roi_pct)}
            </TableCell>
            <TableCell className="tabular-nums">{formatUsdt(trade.margin_usdt)}</TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
              {formatDateTimeShort(trade.closed_at)}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {CLOSE_REASON_LABEL[trade.close_reason] ?? trade.close_reason}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function AdminCustomerEarningsDetailPage() {
  const params = useParams<{ customerId: string }>();
  const customerId = params.customerId;

  const [openPage, setOpenPage] = React.useState(1);
  const [closedPage, setClosedPage] = React.useState(1);
  const [tradesPage, setTradesPage] = React.useState(1);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["platform", "customer-earnings", customerId],
    queryFn: () => platformAdminApi.customerEarningsDetail(customerId),
    enabled: Boolean(customerId),
    refetchInterval: 30_000,
  });

  const { data: openPositions, isLoading: openLoading } = useQuery({
    queryKey: ["platform", "customer-positions", customerId, "OPEN", openPage],
    queryFn: () =>
      platformAdminApi.customerPositions(customerId, {
        status_filter: "OPEN",
        page: openPage,
        page_size: 20,
      }),
    enabled: Boolean(customerId),
    refetchInterval: 10_000,
  });

  const { data: closedPositions, isLoading: closedLoading } = useQuery({
    queryKey: ["platform", "customer-positions", customerId, "CLOSED", closedPage],
    queryFn: () =>
      platformAdminApi.customerPositions(customerId, {
        status_filter: "CLOSED",
        page: closedPage,
        page_size: 20,
      }),
    enabled: Boolean(customerId),
  });

  const { data: trades, isLoading: tradesLoading } = useQuery({
    queryKey: ["platform", "customer-trades", customerId, tradesPage],
    queryFn: () =>
      platformAdminApi.trades({
        customer_id: customerId,
        page: tradesPage,
        page_size: 20,
      }),
    enabled: Boolean(customerId),
  });

  if (isLoading && !data) {
    return <AdminLoading />;
  }

  if (isError || !data) {
    const message = error instanceof ApiError ? error.message : "Veriler alinamadi";
    return (
      <div className="mx-auto max-w-lg space-y-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center shadow-sm">
        <p className="font-medium text-destructive">Musteri kazanc detayi yuklenemedi</p>
        <p className="text-sm text-muted-foreground">{message}</p>
        <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
          {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Tekrar Dene
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title={data.full_name || data.email}
        description={`Kazanc, pozisyon ve islem detayi · ${new Date(data.generated_at).toLocaleString("tr-TR")}`}
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Kazanclar", href: "/admin/earnings" },
          { label: data.email },
        ]}
        badge={
          <div className="flex flex-wrap items-center gap-2">
            {botStatusBadge(null, data.bot_enabled)}
            {data.bot_mode ? (
              <Badge variant="outline" className="uppercase">
                {data.bot_mode}
              </Badge>
            ) : null}
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link href="/admin/earnings">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Kazanc Raporlari
              </Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link href={`/admin/customers/${customerId}`}>Musteri Yonetimi</Link>
            </Button>
            <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
              {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Yenile
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AdminStatCard
          title="Bugun Net"
          value={`${Number(data.daily.net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.daily.net_pnl_usdt, 2)} USDT`}
          hint={`${data.daily.trades_count} islem`}
          icon={Wallet}
          tone={Number(data.daily.net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
        <AdminStatCard
          title="Son 7 Gun"
          value={`${Number(data.weekly.net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.weekly.net_pnl_usdt, 2)} USDT`}
          hint={`Win ${formatNumber(data.weekly.win_rate_pct, 1)}%`}
          icon={TrendingUp}
          tone={Number(data.weekly.net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
        <AdminStatCard
          title="Son 30 Gun"
          value={`${Number(data.monthly.net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.monthly.net_pnl_usdt, 2)} USDT`}
          hint={`${data.monthly.trades_count} islem`}
          icon={TrendingDown}
          tone={Number(data.monthly.net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
        <AdminStatCard
          title="Toplam (Lifetime)"
          value={`${Number(data.lifetime.net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.lifetime.net_pnl_usdt, 2)} USDT`}
          hint={`${data.lifetime.trades_count} kapanmis islem`}
          icon={History}
          tone={Number(data.lifetime.net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <PeriodMiniCard label="Bugun" period={data.daily} />
        <PeriodMiniCard label="7 Gun" period={data.weekly} />
        <PeriodMiniCard label="30 Gun" period={data.monthly} />
        <PeriodMiniCard label="Tum Zamanlar" period={data.lifetime} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <AdminStatCard
          title="Acik Pozisyon"
          value={String(data.open_positions_count)}
          hint="Anlik acik pozisyon sayisi"
          icon={Briefcase}
        />
        <AdminStatCard
          title="Gerceklesmemis PnL"
          value={`${Number(data.total_unrealized_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.total_unrealized_pnl_usdt, 2)} USDT`}
          hint="Acik pozisyonlardan"
          icon={TrendingUp}
          tone={Number(data.total_unrealized_pnl_usdt) >= 0 ? "success" : "danger"}
        />
      </div>

      <Tabs defaultValue="open" className="space-y-4">
        <TabsList className="h-auto p-1">
          <TabsTrigger value="open">Aktif Pozisyonlar ({openPositions?.total ?? data.open_positions_count})</TabsTrigger>
          <TabsTrigger value="closed">Gecmis Pozisyonlar ({closedPositions?.total ?? 0})</TabsTrigger>
          <TabsTrigger value="trades">Islem Gecmisi ({trades?.total ?? data.lifetime.trades_count})</TabsTrigger>
        </TabsList>

        <TabsContent value="open" className="mt-0 space-y-4">
          <AdminSectionCard
            title="Aktif Pozisyonlar"
            description="Musterinin su an acik olan pozisyonlari"
            noPadding
          >
            <PositionsTable items={openPositions?.items ?? []} loading={openLoading} />
          </AdminSectionCard>
          {openPositions && openPositions.total_pages > 1 ? (
            <PaginationBar page={openPage} totalPages={openPositions.total_pages} total={openPositions.total} onPageChange={setOpenPage} />
          ) : null}
        </TabsContent>

        <TabsContent value="closed" className="mt-0 space-y-4">
          <AdminSectionCard
            title="Gecmis Pozisyonlar"
            description="Kapatilmis pozisyon kayitlari"
            noPadding
          >
            <PositionsTable items={closedPositions?.items ?? []} loading={closedLoading} />
          </AdminSectionCard>
          {closedPositions && closedPositions.total_pages > 1 ? (
            <PaginationBar page={closedPage} totalPages={closedPositions.total_pages} total={closedPositions.total} onPageChange={setClosedPage} />
          ) : null}
        </TabsContent>

        <TabsContent value="trades" className="mt-0 space-y-4">
          <AdminSectionCard
            title="Islem Gecmisi"
            description="Kapanmis islemlerden net PnL ve kapanis nedenleri"
            noPadding
          >
            <TradesTable items={trades?.items ?? []} loading={tradesLoading} />
          </AdminSectionCard>
          {trades && trades.total_pages > 1 ? (
            <PaginationBar page={tradesPage} totalPages={trades.total_pages} total={trades.total} onPageChange={setTradesPage} />
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
