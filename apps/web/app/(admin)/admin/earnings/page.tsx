"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, TrendingDown, TrendingUp, Wallet } from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { cn, formatNumber } from "@/lib/utils";
import type { CustomerEarningsOut, CustomerEarningsPeriodOut } from "@/types/api";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatCard,
} from "@/components/admin/admin-ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type PeriodKey = "daily" | "weekly" | "monthly";

const PERIOD_LABEL: Record<PeriodKey, string> = {
  daily: "Bugun",
  weekly: "Son 7 Gun",
  monthly: "Son 30 Gun",
};

function pnlClass(value: string | number) {
  const n = Number(value);
  if (n > 0) return "text-emerald-600 dark:text-emerald-400";
  if (n < 0) return "text-destructive";
  return "text-muted-foreground";
}

function PnlCell({ value }: { value: string | number }) {
  const n = Number(value);
  return (
    <span className={cn("font-medium tabular-nums", pnlClass(value))}>
      {n >= 0 ? "+" : ""}
      {formatNumber(n, 2)} USDT
    </span>
  );
}

function PeriodTable({ rows, period }: { rows: CustomerEarningsOut[]; period: PeriodKey }) {
  const router = useRouter();
  const sorted = [...rows].sort((a, b) => Number(b[period].net_pnl_usdt) - Number(a[period].net_pnl_usdt));

  const goToCustomer = (customerId: string) => {
    router.push(`/admin/earnings/${customerId}`);
  };

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>#</TableHead>
          <TableHead>Musteri</TableHead>
          <TableHead>Net Kazanc</TableHead>
          <TableHead>Brut</TableHead>
          <TableHead>Islem</TableHead>
          <TableHead>Kazan/Kayip</TableHead>
          <TableHead>Win %</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row, idx) => {
          const p: CustomerEarningsPeriodOut = row[period];
          return (
            <TableRow
              key={row.customer_id}
              className="cursor-pointer"
              onClick={() => goToCustomer(row.customer_id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  goToCustomer(row.customer_id);
                }
              }}
              tabIndex={0}
              role="link"
              aria-label={`${row.email} musteri detayi`}
            >
              <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
              <TableCell>
                <span className="font-medium text-primary">{row.email}</span>
                <p className="text-xs text-muted-foreground">{row.full_name || "—"}</p>
              </TableCell>
              <TableCell>
                <PnlCell value={p.net_pnl_usdt} />
              </TableCell>
              <TableCell className="tabular-nums text-sm">{formatNumber(p.gross_pnl_usdt, 2)}</TableCell>
              <TableCell>{p.trades_count}</TableCell>
              <TableCell className="text-xs text-muted-foreground">
                <span className="text-emerald-600">{p.winning_trades}W</span>
                {" / "}
                <span className="text-destructive">{p.losing_trades}L</span>
              </TableCell>
              <TableCell>{formatNumber(p.win_rate_pct, 1)}%</TableCell>
            </TableRow>
          );
        })}
        {sorted.length === 0 && (
          <TableRow>
            <TableCell colSpan={7}>
              <AdminEmptyState title="Kayitli musteri yok" />
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

export default function AdminCustomerEarningsPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["platform", "customer-earnings"],
    queryFn: platformAdminApi.customerEarnings,
    refetchInterval: 60_000,
    retry: 1,
  });

  if (isLoading) {
    return <AdminLoading />;
  }

  if (isError || !data) {
    const message = error instanceof ApiError ? error.message : "Veriler alinamadi";
    return (
      <div className="mx-auto max-w-lg space-y-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center shadow-sm">
        <p className="font-medium text-destructive">Kazanc raporu yuklenemedi</p>
        <p className="text-sm text-muted-foreground">{message}</p>
        <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
          {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Tekrar Dene
        </Button>
      </div>
    );
  }

  const customers = data.customers;

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Kazanc Raporlari"
        description={`Kapatilmis islemlerden net PnL · ${new Date(data.generated_at).toLocaleString("tr-TR")}`}
        badge={<Badge variant="outline">{data.customer_count} musteri</Badge>}
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Kazanclar" }]}
        actions={
          <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Yenile
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <AdminStatCard
          title="Bugun (Toplam)"
          value={`${Number(data.daily_total_net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.daily_total_net_pnl_usdt, 2)} USDT`}
          hint={`${data.customer_count} musteri`}
          icon={Wallet}
          tone={Number(data.daily_total_net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
        <AdminStatCard
          title="Son 7 Gun"
          value={`${Number(data.weekly_total_net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.weekly_total_net_pnl_usdt, 2)} USDT`}
          hint="Platform geneli"
          icon={TrendingUp}
          tone={Number(data.weekly_total_net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
        <AdminStatCard
          title="Son 30 Gun"
          value={`${Number(data.monthly_total_net_pnl_usdt) >= 0 ? "+" : ""}${formatNumber(data.monthly_total_net_pnl_usdt, 2)} USDT`}
          hint="Platform geneli"
          icon={TrendingDown}
          tone={Number(data.monthly_total_net_pnl_usdt) >= 0 ? "success" : "danger"}
        />
      </div>

      <Tabs defaultValue="monthly" className="space-y-4">
        <TabsList className="h-auto p-1">
          <TabsTrigger value="daily">{PERIOD_LABEL.daily}</TabsTrigger>
          <TabsTrigger value="weekly">{PERIOD_LABEL.weekly}</TabsTrigger>
          <TabsTrigger value="monthly">{PERIOD_LABEL.monthly}</TabsTrigger>
        </TabsList>

        {(["daily", "weekly", "monthly"] as PeriodKey[]).map((period) => (
          <TabsContent key={period} value={period} className="mt-0">
            <AdminSectionCard
              title={`${PERIOD_LABEL[period]} — Musteri Siralamasi`}
              description="Satira tiklayarak musteri kazanc detayina gidebilirsiniz."
              actions={<Badge variant="outline">{customers.length} musteri</Badge>}
              noPadding
            >
              <PeriodTable rows={customers} period={period} />
            </AdminSectionCard>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

