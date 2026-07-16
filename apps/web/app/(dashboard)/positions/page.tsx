"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Plus, Wallet, TrendingUp, TrendingDown, Coins, AlertTriangle, RefreshCw } from "lucide-react";

import { dashboardApi, positionsApi, settingsApi } from "@/lib/api";
import { useDashboardWs } from "@/hooks/use-dashboard-ws";
import { ApiError } from "@/lib/api-client";
import { cn, formatDateTimeShort, formatPct, formatTry, formatUsdt, pnlColorClass, toNumber } from "@/lib/utils";
import type { DashboardWsPositionSnapshot, PositionOut } from "@/types/api";
import { PageHeader } from "@/components/shared/page-header";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { SideBadge, StatusBadge, NewPositionBadge } from "@/components/shared/side-badge";
import { UsdtWithTry } from "@/components/shared/usdt-with-try";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { useToast } from "@/components/ui/toast-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CoinChartDialog } from "@/components/avci/coin-chart-dialog";

function mergePositionsWithLive(
  items: PositionOut[],
  liveSnapshots: DashboardWsPositionSnapshot[] | undefined,
): PositionOut[] {
  if (!liveSnapshots?.length) return items;
  const liveById = new Map(liveSnapshots.map((p) => [p.id, p]));
  return items.map((pos) => {
    const live = liveById.get(pos.id);
    if (!live || pos.status !== "OPEN") return pos;
    return {
      ...pos,
      mark_price: live.mark_price ?? pos.mark_price,
      unrealized_pnl: live.unrealized_pnl,
      roi_pct: live.roi_pct,
    };
  });
}

export default function PositionsPage() {
  const [page, setPage] = React.useState(1);
  const [statusFilter, setStatusFilter] = React.useState<string>("OPEN");
  const [closeTarget, setCloseTarget] = React.useState<PositionOut | null>(null);
  const [addTarget, setAddTarget] = React.useState<PositionOut | null>(null);
  const [chartTarget, setChartTarget] = React.useState<PositionOut | null>(null);
  const [emergencyOpen, setEmergencyOpen] = React.useState(false);
  const [emergencyPassword, setEmergencyPassword] = React.useState("");
  const [addLosingOpen, setAddLosingOpen] = React.useState(false);
  const { push } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["positions", page, statusFilter],
    queryFn: () =>
      positionsApi.list({ page, page_size: 20, status_filter: statusFilter === "ALL" ? undefined : statusFilter }),
    refetchInterval: statusFilter === "OPEN" ? 1_000 : 10_000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  });

  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });

  const { data: initialDashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    refetchInterval: 2_000,
  });
  const { data: wsData, connected } = useDashboardWs();
  const dashboard = wsData?.dashboard ?? initialDashboard;

  const displayItems = React.useMemo(
    () => mergePositionsWithLive(data?.items ?? [], wsData?.open_positions),
    [data?.items, wsData?.open_positions],
  );

  React.useEffect(() => {
    if (statusFilter !== "OPEN" || page !== 1 || !wsData?.open_positions || !data?.items) return;
    const wsIds = new Set(wsData.open_positions.map((p) => p.id));
    const apiIds = new Set(data.items.map((p) => p.id));
    const structuralMismatch =
      wsData.open_positions.length !== data.items.length ||
      [...wsIds].some((id) => !apiIds.has(id)) ||
      [...apiIds].some((id) => !wsIds.has(id));
    const countMismatch =
      wsData.exchange_open_count != null &&
      wsData.local_open_count != null &&
      wsData.exchange_open_count !== wsData.local_open_count;
    if (structuralMismatch || countMismatch) {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
    }
  }, [
    wsData?.open_positions,
    wsData?.exchange_open_count,
    wsData?.local_open_count,
    data?.items,
    statusFilter,
    page,
    queryClient,
  ]);

  const syncMutation = useMutation({
    mutationFn: () => positionsApi.sync(),
    onSuccess: (result) => {
      if (result.closed_ghosts.length) {
        push({
          title: "Hayalet pozisyonlar kapatildi",
          description: result.closed_ghosts.join(", "),
          variant: "success",
        });
      } else if (result.in_sync) {
        push({ title: "Binance ile esitlendi", variant: "success" });
      } else {
        push({
          title: "Senkron tamamlandi",
          description: `Panel: ${result.local_open_count}, Binance: ${result.exchange_open_count}`,
          variant: "error",
        });
      }
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Senkron basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const [nowTick, setNowTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setNowTick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, []);
  void nowTick;

  const closeMutation = useMutation({
    mutationFn: (id: string) => positionsApi.close(id, "MANUAL"),
    onSuccess: () => {
      push({ title: "Pozisyon kapatildi", variant: "success" });
      setCloseTarget(null);
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Pozisyon kapatilamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const addMutation = useMutation({
    mutationFn: (id: string) => positionsApi.add(id),
    onSuccess: () => {
      push({ title: "Pozisyona ekleme yapildi", variant: "success" });
      setAddTarget(null);
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Ekleme basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const emergencyCloseMutation = useMutation({
    mutationFn: () => positionsApi.emergencyCloseAll(emergencyPassword),
    onSuccess: (result) => {
      push({
        title: "Acil kapatma tamamlandi",
        description: `${result.closed_count} pozisyon kapatildi${result.failed_positions.length ? `, ${result.failed_positions.length} basarisiz` : ""}`,
        variant: result.failed_positions.length ? "error" : "success",
      });
      setEmergencyOpen(false);
      setEmergencyPassword("");
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Acil kapatma basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const addLosingMutation = useMutation({
    mutationFn: () => positionsApi.addLosing(),
    onSuccess: (result) => {
      const parts = [`${result.added_count} pozisyona ekleme yapildi`];
      if (result.skipped_positions.length) parts.push(`${result.skipped_positions.length} atlandi (limit)`);
      if (result.failed_positions.length) parts.push(`${result.failed_positions.length} basarisiz`);
      push({
        title: "Zarardaki pozisyonlara ekleme",
        description: parts.join(", "),
        variant: result.failed_positions.length ? "error" : "success",
      });
      setAddLosingOpen(false);
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Ekleme basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const openPositions = wsData?.open_positions ?? [];
  const losingPositionsCount = openPositions.filter((p) => toNumber(p.roi_pct) < 0).length;
  const localOpenCount = wsData?.local_open_count ?? data?.total ?? dashboard?.open_positions_count ?? 0;
  const exchangeOpenCount = wsData?.exchange_open_count;
  const countOutOfSync =
    statusFilter === "OPEN" &&
    exchangeOpenCount != null &&
    localOpenCount !== exchangeOpenCount;

  const tryRate = dashboard?.usdt_try_rate;

  return (
    <div>
      <PageHeader
        title="Pozisyonlar"
        description={
          connected
            ? `Canli · Panel ${localOpenCount}${exchangeOpenCount != null ? ` / Binance ${exchangeOpenCount}` : ""} · ${wsData?.server_time ? formatDateTimeShort(wsData.server_time) : "baglandi"}`
            : "Canli baglanti kuruluyor..."
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending || settings?.mode === "paper"}
            >
              <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
              Binance Esitle
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddLosingOpen(true)}
              disabled={losingPositionsCount === 0}
            >
              <Plus className="h-4 w-4" />
              Zarardakilere Ekle
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setEmergencyPassword("");
                setEmergencyOpen(true);
              }}
              disabled={localOpenCount === 0}
            >
              <AlertTriangle className="h-4 w-4" />
              Acil Pozisyon Kapat
            </Button>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="OPEN">Acik</SelectItem>
                <SelectItem value="CLOSED">Kapali</SelectItem>
                <SelectItem value="ALL">Tumu</SelectItem>
              </SelectContent>
            </Select>
          </div>
        }
      />

      {countOutOfSync ? (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
          <span>
            Sayi uyusmuyor: panelde <strong>{localOpenCount}</strong>, Binance&apos;de{" "}
            <strong>{exchangeOpenCount}</strong>. Borsada kapanmis pozisyonlar otomatik temizleniyor.
          </span>
          <Button variant="outline" size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
            Simdi esitle
          </Button>
        </div>
      ) : null}

      <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
          <CardContent className="flex items-center gap-2 p-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Wallet className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Gerceklesen Bakiye</p>
              <UsdtWithTry usdt={dashboard?.wallet_balance_usdt} usdtTryRate={tryRate} />
              <p className="mt-0.5 text-xs text-muted-foreground">
                Kullanilabilir:{" "}
                <span className="font-medium text-foreground">{formatUsdt(dashboard?.available_usdt)}</span>
                {formatTry(dashboard?.available_usdt, tryRate) ? (
                  <span className="text-muted-foreground"> ({formatTry(dashboard?.available_usdt, tryRate)})</span>
                ) : null}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/80">
          <CardContent className="flex items-center gap-2 p-3">
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
                toNumber(dashboard?.daily_unrealized_pnl_usdt) >= 0 ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
              )}
            >
              {toNumber(dashboard?.daily_unrealized_pnl_usdt) >= 0 ? (
                <TrendingUp className="h-4 w-4" />
              ) : (
                <TrendingDown className="h-4 w-4" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Gerceklesmeyen PnL</p>
              <UsdtWithTry
                usdt={dashboard?.daily_unrealized_pnl_usdt}
                usdtTryRate={tryRate}
                usdtClassName={pnlColorClass(dashboard?.daily_unrealized_pnl_usdt)}
                tryClassName={pnlColorClass(dashboard?.daily_unrealized_pnl_usdt)}
              />
              <p className="mt-0.5 text-xs text-muted-foreground">
                Toplam bakiye:{" "}
                <span className="font-medium text-foreground">{formatUsdt(dashboard?.total_futures_balance_usdt)}</span>
                {formatTry(dashboard?.total_futures_balance_usdt, tryRate) ? (
                  <span className="text-muted-foreground">
                    {" "}
                    ({formatTry(dashboard?.total_futures_balance_usdt, tryRate)})
                  </span>
                ) : null}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-2 p-3">
            <Coins className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Toplam Bakiye</p>
              <UsdtWithTry usdt={dashboard?.total_futures_balance_usdt} usdtTryRate={tryRate} size="md" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-2 p-3">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Bugun Gerceklesen PnL</p>
              <UsdtWithTry
                usdt={dashboard?.daily_realized_pnl_usdt}
                usdtTryRate={tryRate}
                size="md"
                usdtClassName={pnlColorClass(dashboard?.daily_realized_pnl_usdt)}
                tryClassName={pnlColorClass(dashboard?.daily_realized_pnl_usdt)}
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-2 p-3">
            <Wallet className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Kullanilan Teminat</p>
              <UsdtWithTry usdt={dashboard?.used_margin_usdt} usdtTryRate={tryRate} size="md" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Yon</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Kaldirac</TableHead>
                <TableHead>Teminat</TableHead>
                <TableHead>Giris</TableHead>
                <TableHead>Mark/Cikis</TableHead>
                <TableHead>SL / TP</TableHead>
                <TableHead>PnL</TableHead>
                <TableHead>ROI</TableHead>
                <TableHead>Korumali</TableHead>
                <TableHead>Acilis</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {!isLoading && displayItems.length === 0 && (
                <TableRow>
                  <TableCell colSpan={13} className="py-6 text-center text-muted-foreground">
                    Kayit bulunamadi
                  </TableCell>
                </TableRow>
              )}
              {displayItems.map((position) => {
                const maxAdds = settings?.loss_add_max_count ?? 0;
                const canAdd = maxAdds > 0 && (position.loss_add_count ?? 0) < maxAdds;
                return (
                <TableRow key={position.id}>
                  <TableCell className="font-medium">
                    <span className="inline-flex flex-wrap items-center gap-1.5">
                      <button
                        type="button"
                        className="text-left font-medium text-primary hover:underline"
                        title="Grafigi ac"
                        onClick={() => setChartTarget(position)}
                      >
                        {position.symbol}
                      </button>
                      <NewPositionBadge openedAt={position.opened_at} status={position.status} />
                    </span>
                  </TableCell>
                  <TableCell>
                    <SideBadge side={position.side} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={position.status} />
                  </TableCell>
                  <TableCell>{position.leverage}x</TableCell>
                  <TableCell>{formatUsdt(position.margin_usdt)}</TableCell>
                  <TableCell>{formatUsdt(position.entry_price, 4)}</TableCell>
                  <TableCell>{formatUsdt(position.status === "OPEN" ? position.mark_price : position.mark_price, 4)}</TableCell>
                  <TableCell className="text-xs">
                    <span className="text-destructive">{formatUsdt(position.stop_loss_price, 4)}</span>
                    {" / "}
                    <span className="text-success">{formatUsdt(position.take_profit_price, 4)}</span>
                  </TableCell>
                  <TableCell className={pnlColorClass(position.unrealized_pnl)}>{formatUsdt(position.unrealized_pnl)}</TableCell>
                  <TableCell className={pnlColorClass(position.roi_pct)}>{formatPct(position.roi_pct)}</TableCell>
                  <TableCell>
                    <StatusBadge status={position.protective_orders_ok ? "FILLED" : "REJECTED"} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDateTimeShort(position.opened_at)}</TableCell>
                  <TableCell>
                    {position.status === "OPEN" && (
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => setAddTarget(position)}
                          disabled={!canAdd}
                          title={
                            !canAdd
                              ? `Maksimum ekleme sayisina ulasildi (${position.loss_add_count}/${maxAdds})`
                              : undefined
                          }
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Ekle
                        </Button>
                        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => setCloseTarget(position)}>
                          <X className="h-3.5 w-3.5" />
                          Kapat
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              );})}
            </TableBody>
          </Table>
          {data && <PaginationBar page={data.page} totalPages={data.total_pages} total={data.total} onPageChange={setPage} />}
        </CardContent>
      </Card>

      <CoinChartDialog
        symbol={chartTarget?.symbol ?? null}
        open={chartTarget !== null}
        onOpenChange={(open) => !open && setChartTarget(null)}
        showTradeActions={false}
        positionLevels={
          chartTarget
            ? {
                side: chartTarget.side,
                entry_price: chartTarget.entry_price,
                stop_loss_price: chartTarget.stop_loss_price,
                take_profit_price: chartTarget.take_profit_price,
              }
            : null
        }
      />

      <ConfirmDialog
        open={addLosingOpen}
        onOpenChange={setAddLosingOpen}
        title="Zarardaki pozisyonlara ekleme yap"
        description={`ROI negatif olan ${losingPositionsCount} acik pozisyona ayarlardaki islem basina teminat kadar (${formatUsdt(settings?.margin_per_trade_usdt ?? "0")}) market emri ile ekleme yapilacak. Maksimum ekleme limitine ulasmis pozisyonlar atlanir.`}
        confirmLabel="Zarardakilere Ekle"
        isLoading={addLosingMutation.isPending}
        onConfirm={() => addLosingMutation.mutate()}
      />

      <ConfirmDialog
        open={addTarget !== null}
        onOpenChange={(open) => !open && setAddTarget(null)}
        title="Pozisyona ekleme yap"
        description={`${addTarget?.symbol} ${addTarget?.side} pozisyonuna ayarlardaki islem basina teminat kadar (${formatUsdt(settings?.margin_per_trade_usdt ?? "0")}) market emri ile ekleme yapilacak. Ortalama giris fiyati ve SL/TP guncellenir.`}
        confirmLabel="Ekleme Yap"
        isLoading={addMutation.isPending}
        onConfirm={() => addTarget && addMutation.mutate(addTarget.id)}
      />

      <ConfirmDialog
        open={closeTarget !== null}
        onOpenChange={(open) => !open && setCloseTarget(null)}
        title="Pozisyonu kapat"
        description={`${closeTarget?.symbol} ${closeTarget?.side} pozisyonunu piyasa fiyatindan manuel olarak kapatmak istediginize emin misiniz? Bu islem geri alinamaz.`}
        confirmLabel="Pozisyonu Kapat"
        destructive
        isLoading={closeMutation.isPending}
        onConfirm={() => closeTarget && closeMutation.mutate(closeTarget.id)}
      />

      <Dialog
        open={emergencyOpen}
        onOpenChange={(open) => {
          if (!open) setEmergencyPassword("");
          setEmergencyOpen(open);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Acil Pozisyon Kapat
            </DialogTitle>
            <DialogDescription>
              Mevcut moddaki tum acik pozisyonlar ({localOpenCount}) piyasa fiyatindan kapatilacak.
              Bu islem geri alinamaz. Devam etmek icin sifrenizi girin.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="emergency-password">Acil kapatma sifresi</Label>
            <Input
              id="emergency-password"
              type="password"
              autoComplete="off"
              placeholder="Sifre"
              value={emergencyPassword}
              onChange={(e) => setEmergencyPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && emergencyPassword.length > 0 && !emergencyCloseMutation.isPending) {
                  emergencyCloseMutation.mutate();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmergencyOpen(false)} disabled={emergencyCloseMutation.isPending}>
              Vazgec
            </Button>
            <Button
              variant="destructive"
              disabled={!emergencyPassword || emergencyCloseMutation.isPending}
              onClick={() => emergencyCloseMutation.mutate()}
            >
              Tum Pozisyonlari Kapat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
