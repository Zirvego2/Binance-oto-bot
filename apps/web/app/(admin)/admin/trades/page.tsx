"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Search, Trash2 } from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { formatDateTimeShort, formatPct, formatUsdt, pnlColorClass } from "@/lib/utils";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
} from "@/components/admin/admin-ui";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { SideBadge } from "@/components/shared/side-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast-provider";
import type { AdminTradeOut } from "@/types/api";

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

export default function AdminTradesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [page, setPage] = React.useState(1);
  const [symbol, setSymbol] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [deleteTarget, setDeleteTarget] = React.useState<AdminTradeOut | null>(null);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["platform", "trades", page, symbol, search],
    queryFn: () =>
      platformAdminApi.trades({
        page,
        page_size: 30,
        symbol: symbol || undefined,
        search: search || undefined,
      }),
    refetchInterval: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => platformAdminApi.deleteTrade(id),
    onSuccess: () => {
      push({ title: "Islem silindi", variant: "success" });
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["platform", "trades"] });
    },
    onError: (err) => {
      push({
        title: "Islem silinemedi",
        description: err instanceof ApiError ? err.message : undefined,
        variant: "error",
      });
    },
  });

  const totals = React.useMemo(() => {
    if (!data?.items.length) return null;
    const netPnl = data.items.reduce((acc, t) => acc + Number.parseFloat(t.net_pnl_usdt), 0);
    return { netPnl, count: data.items.length };
  }, [data?.items]);

  const applySearch = () => {
    setSearch(searchInput.trim());
    setPage(1);
  };

  if (isLoading && !data) {
    return <AdminLoading />;
  }

  if (isError && !data) {
    const message = error instanceof ApiError ? error.message : "Veriler alinamadi";
    return (
      <div className="mx-auto max-w-lg space-y-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center shadow-sm">
        <p className="font-medium text-destructive">Islem gecmisi yuklenemedi</p>
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
        title="Islem Gecmisi"
        description="Tum musterilerin kapanmis islemleri tek listede"
        badge={<Badge variant="outline">{data?.total ?? 0} islem</Badge>}
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Islem Gecmisi" }]}
        actions={
          <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Yenile
          </Button>
        }
      />

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Musteri ara (e-posta / ad)</label>
          <div className="flex gap-2">
            <Input
              placeholder="ornek@gmail.com"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applySearch();
              }}
            />
            <Button type="button" variant="secondary" onClick={applySearch}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="min-w-[180px]">
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Sembol</label>
          <Input
            placeholder="BTCUSDT"
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value.toUpperCase());
              setPage(1);
            }}
          />
        </div>
      </div>

      <AdminSectionCard title="Kapanmis Islemler" noPadding contentClassName="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Musteri</TableHead>
              <TableHead>Sembol</TableHead>
              <TableHead>Yon</TableHead>
              <TableHead>Mod</TableHead>
              <TableHead>Kaldirac</TableHead>
              <TableHead>Teminat</TableHead>
              <TableHead>Giris</TableHead>
              <TableHead>Cikis</TableHead>
              <TableHead>Net PnL</TableHead>
              <TableHead>Net ROI</TableHead>
              <TableHead>Kapanis</TableHead>
              <TableHead>Neden</TableHead>
              <TableHead className="sticky right-0 z-10 min-w-[88px] bg-card shadow-[-8px_0_12px_-8px_rgba(0,0,0,0.45)]">
                Sil
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!isLoading && (data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={13}>
                  <AdminEmptyState title="Kayit bulunamadi" />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((trade) => (
              <TableRow
                key={trade.id}
                className="cursor-pointer"
                onClick={() => trade.customer_id && router.push(`/admin/customers/${trade.customer_id}`)}
              >
                <TableCell>
                  {trade.customer_id ? (
                    <Link
                      href={`/admin/customers/${trade.customer_id}`}
                      className="font-medium text-primary hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {trade.customer_email ?? "—"}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                  {trade.customer_full_name ? (
                    <p className="text-xs text-muted-foreground">{trade.customer_full_name}</p>
                  ) : null}
                </TableCell>
                <TableCell className="font-medium">{trade.symbol}</TableCell>
                <TableCell>
                  <SideBadge side={trade.side} />
                </TableCell>
                <TableCell className="text-xs uppercase text-muted-foreground">{trade.bot_mode}</TableCell>
                <TableCell>{trade.leverage}x</TableCell>
                <TableCell>{formatUsdt(trade.margin_usdt)}</TableCell>
                <TableCell>{formatUsdt(trade.entry_price, 4)}</TableCell>
                <TableCell>{formatUsdt(trade.exit_price, 4)}</TableCell>
                <TableCell className={pnlColorClass(trade.net_pnl_usdt)}>{formatUsdt(trade.net_pnl_usdt)}</TableCell>
                <TableCell className={pnlColorClass(trade.net_roi_pct)}>{formatPct(trade.net_roi_pct)}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{formatDateTimeShort(trade.closed_at)}</TableCell>
                <TableCell>
                  <Badge variant="outline">{CLOSE_REASON_LABEL[trade.close_reason] ?? trade.close_reason}</Badge>
                </TableCell>
                <TableCell className="sticky right-0 z-10 bg-card shadow-[-8px_0_12px_-8px_rgba(0,0,0,0.45)]">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Islemi sil"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(trade);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Sil
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data ? (
          <>
            <PaginationBar page={data.page} totalPages={data.total_pages} total={data.total} onPageChange={setPage} />
            {totals ? (
              <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
                Bu sayfadaki {totals.count} islemin net PnL toplami:{" "}
                <span className={pnlColorClass(totals.netPnl)}>{formatUsdt(totals.netPnl.toString())}</span>
              </div>
            ) : null}
          </>
        ) : null}
      </AdminSectionCard>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Islemi sil"
        description={
          deleteTarget ? (
            <>
              <span className="font-medium">{deleteTarget.symbol}</span> ({deleteTarget.side}) islemini gecmisten
              kalici olarak silmek istediginize emin misiniz? Bu islem geri alinamaz.
            </>
          ) : undefined
        }
        confirmLabel="Sil"
        destructive
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </div>
  );
}
