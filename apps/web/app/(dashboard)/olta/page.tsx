"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Anchor, XCircle, Clock, TrendingUp, TrendingDown, RefreshCw, Settings2 } from "lucide-react";
import { ordersApi, settingsApi } from "@/lib/api";
import type { OrderOut, BotSettingsOut } from "@/types/api";
import { cn, parseApiUtcDate } from "@/lib/utils";

function formatPrice(v: string | null | undefined) {
  if (!v) return "—";
  return parseFloat(v).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 6 });
}

function formatQty(v: string | null | undefined) {
  if (!v) return "—";
  return parseFloat(v).toFixed(4);
}

function timeAgo(iso: string | null): string {
  const then = parseApiUtcDate(iso);
  if (!then) return "—";
  const diff = Math.floor((Date.now() - then.getTime()) / 1000);
  if (diff < 60) return `${diff}s önce`;
  if (diff < 3600) return `${Math.floor(diff / 60)}dk önce`;
  return `${Math.floor(diff / 3600)}s ${Math.floor((diff % 3600) / 60)}dk önce`;
}

function timeRemaining(iso: string | null, timeoutMinutes: number): string {
  const then = parseApiUtcDate(iso);
  if (!then) return "—";
  const elapsed = (Date.now() - then.getTime()) / 1000 / 60;
  const remaining = timeoutMinutes - elapsed;
  if (remaining <= 0) return "Süresi doldu — iptal bekleniyor";
  if (remaining < 1) return `${Math.round(remaining * 60)}s kaldı`;
  return `${Math.floor(remaining)}dk kaldı`;
}

function timeRemainingPct(iso: string | null, timeoutMinutes: number): number {
  const then = parseApiUtcDate(iso);
  if (!then) return 100;
  const elapsed = (Date.now() - then.getTime()) / 1000 / 60;
  return Math.max(0, Math.min(100, ((timeoutMinutes - elapsed) / timeoutMinutes) * 100));
}

function isTimedOut(iso: string | null, timeoutMinutes: number): boolean {
  const then = parseApiUtcDate(iso);
  if (!then) return false;
  const elapsed = (Date.now() - then.getTime()) / 1000 / 60;
  return elapsed >= timeoutMinutes;
}

export default function OltaPage() {
  const qc = useQueryClient();
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const { data: ordersData, isLoading: ordersLoading, dataUpdatedAt } = useQuery({
    queryKey: ["pending-limit-orders"],
    queryFn: () => ordersApi.pendingLimit(),
    refetchInterval: 5000,
  });

  const { data: settings } = useQuery<BotSettingsOut>({
    queryKey: ["bot-settings"],
    queryFn: () => settingsApi.get(),
    refetchInterval: 30000,
  });

  const cancelMut = useMutation({
    mutationFn: (id: string) => ordersApi.cancel(id),
    onMutate: (id) => setCancellingId(id),
    onSettled: () => {
      setCancellingId(null);
      qc.invalidateQueries({ queryKey: ["pending-limit-orders"] });
    },
  });

  const orders: OrderOut[] = ordersData?.items ?? [];
  const timeoutMin = settings?.limit_entry_timeout_minutes ?? 60;
  const offsetPct = settings?.limit_entry_offset_pct ?? "0.30";
  const limitEnabled = settings?.limit_entry_enabled ?? false;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500">
            <Anchor className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Olta Emirleri</h1>
            <p className="text-sm text-muted-foreground">
              Bekleyen limit açılış emirleri — sinyal gelince piyasanın{" "}
              <span className="font-medium text-foreground">altına/üstüne</span> olta atılır
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Son güncelleme: {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString("tr-TR") : "—"}
          </span>
          <RefreshCw className="h-3.5 w-3.5 animate-spin text-muted-foreground opacity-50" />
        </div>
      </div>

      {/* Settings summary */}
      <div className="rounded-xl border border-border bg-card/40 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Settings2 className="h-4 w-4" />
          <span>Olta Ayarları</span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Mod</p>
            <p className={cn("mt-1 font-semibold", limitEnabled ? "text-green-500" : "text-muted-foreground")}>
              {limitEnabled ? "✓ Aktif" : "✗ Devre Dışı"}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Offset (piyasadan uzaklık)</p>
            <p className="mt-1 font-semibold">{parseFloat(String(offsetPct)).toFixed(2)}%</p>
          </div>
          <div>
            <p className="text-muted-foreground">Zaman aşımı</p>
            <p className="mt-1 font-semibold">{timeoutMin} dakika</p>
          </div>
        </div>
        {!limitEnabled && (
          <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
            Olta modu kapali.{" "}
            <Link href="/pozisyon-ayarlari" className="font-semibold underline hover:text-amber-400">
              Ayarlar
            </Link>{" "}
            sayfasinda <strong>Olta limit modu aktif</strong> anahtarini acin.
          </p>
        )}
      </div>

      {/* Orders list */}
      {ordersLoading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          Yükleniyor…
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <Anchor className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Bekleyen olta emri yok</p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Olta modu aktif olduğunda sinyal gelince otomatik emir atılır
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => {
            const isLong = order.side === "BUY";
            const remPct = timeRemainingPct(order.submitted_at, timeoutMin);
            const timedOut = isTimedOut(order.submitted_at, timeoutMin);
            const isCancelling = cancellingId === order.id;

            return (
              <div
                key={order.id}
                className={cn(
                  "relative overflow-hidden rounded-xl border bg-card/60 p-4 transition-all",
                  timedOut
                    ? "border-amber-500/30 bg-amber-500/5"
                    : isLong
                      ? "border-green-500/20 hover:border-green-500/40"
                      : "border-red-500/20 hover:border-red-500/40"
                )}
              >
                {/* Progress bar (time remaining) */}
                <div className="absolute bottom-0 left-0 h-0.5 bg-muted">
                  <div
                    className={cn(
                      "h-full transition-all",
                      remPct > 30 ? "bg-blue-500" : remPct > 10 ? "bg-amber-500" : "bg-red-500"
                    )}
                    style={{ width: `${remPct}%` }}
                  />
                </div>

                <div className="flex items-start justify-between gap-4">
                  {/* Left: Symbol + side */}
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                        isLong ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                      )}
                    >
                      {isLong ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{order.symbol}</span>
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5 text-xs font-semibold",
                            isLong
                              ? "bg-green-500/10 text-green-500"
                              : "bg-red-500/10 text-red-500"
                          )}
                        >
                          {isLong ? "LONG" : "SHORT"}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {isLong
                          ? "▼ Piyasanın altında bekliyor"
                          : "▲ Piyasanın üstünde bekliyor"}
                      </p>
                    </div>
                  </div>

                  {/* Center: Prices */}
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Limit Fiyat</p>
                      <p className="font-semibold tabular-nums">{formatPrice(order.price)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Miktar</p>
                      <p className="font-semibold tabular-nums">{formatQty(order.quantity)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Emir Verildi</p>
                      <p className="tabular-nums text-muted-foreground">{timeAgo(order.submitted_at)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Kalan Süre</p>
                      <p
                        className={cn(
                          "tabular-nums font-medium",
                          timedOut
                            ? "text-amber-400"
                            : remPct > 30
                              ? "text-blue-400"
                              : remPct > 10
                                ? "text-amber-400"
                                : "text-red-400"
                        )}
                      >
                        <Clock className="mr-1 inline h-3 w-3" />
                        {timeRemaining(order.submitted_at, timeoutMin)}
                      </p>
                    </div>
                  </div>

                  {/* Right: Cancel button */}
                  <div className="flex shrink-0 items-start">
                    <button
                      onClick={() => cancelMut.mutate(order.id)}
                      disabled={isCancelling}
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                        "border border-destructive/30 text-destructive hover:bg-destructive/10",
                        isCancelling && "cursor-not-allowed opacity-50"
                      )}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      {isCancelling ? "İptal…" : "Emri İptal Et"}
                    </button>
                  </div>
                </div>

                {order.last_error && (
                  <p className="mt-2 rounded bg-destructive/10 px-2 py-1 text-xs text-destructive">
                    {order.last_error}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* How it works */}
      <div className="rounded-xl border border-border/50 bg-card/20 p-4 text-xs text-muted-foreground">
        <p className="mb-1 font-medium text-foreground">Nasıl çalışır?</p>
        <ul className="list-inside list-disc space-y-1">
          <li>
            Sinyal geldiğinde piyasadan <strong>{parseFloat(String(offsetPct)).toFixed(2)}%</strong>{" "}
            {"{"}aşağı (LONG) / yukarı (SHORT){"}"} limit emir verilir
          </li>
          <li>Fiyat olta seviyesine inerse/çıkarsa emir dolar ve pozisyon açılır</li>
          <li>
            <strong>{timeoutMin} dakika</strong> içinde dolmazsa emir otomatik iptal edilir
          </li>
          <li>Sinyal geçerliliğini kaybederse emir anında iptal edilir</li>
        </ul>
      </div>
    </div>
  );
}
