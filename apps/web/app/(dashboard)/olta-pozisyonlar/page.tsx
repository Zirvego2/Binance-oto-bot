"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Anchor, TrendingUp, TrendingDown, RefreshCw, XCircle, CheckCircle2,
  Clock, BarChart2, AlertTriangle,
} from "lucide-react";
import { positionsApi, settingsApi } from "@/lib/api";
import type { PositionOut, BotSettingsOut } from "@/types/api";
import { cn } from "@/lib/utils";

type Tab = "open" | "closed";

function fp(v: string | null | undefined, decimals = 4) {
  if (!v) return "—";
  const n = parseFloat(v);
  return n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: decimals });
}

function pnlColor(v: string | null | undefined) {
  if (!v) return "text-muted-foreground";
  return parseFloat(v) >= 0 ? "text-green-400" : "text-red-400";
}

function roiColor(v: string | null | undefined) {
  if (!v) return "text-muted-foreground";
  return parseFloat(v) >= 0 ? "text-green-400" : "text-red-400";
}

function timeAgo(iso: string | null) {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s önce`;
  if (diff < 3600) return `${Math.floor(diff / 60)}dk`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}s ${Math.floor((diff % 3600) / 60)}dk`;
  return `${Math.floor(diff / 86400)}g`;
}

export default function OltaPozisyonlarPage() {
  const [tab, setTab] = useState<Tab>("open");
  const qc = useQueryClient();
  const [closingId, setClosingId] = useState<string | null>(null);

  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["olta-positions", tab],
    queryFn: () => positionsApi.oltaPositions(tab === "open" ? "OPEN" : "CLOSED"),
    refetchInterval: tab === "open" ? 5000 : 30000,
  });

  const { data: settings } = useQuery<BotSettingsOut>({
    queryKey: ["bot-settings"],
    queryFn: () => settingsApi.get(),
  });

  const closeMut = useMutation({
    mutationFn: (id: string) => positionsApi.close(id, "MANUAL"),
    onMutate: (id) => setClosingId(id),
    onSettled: () => {
      setClosingId(null);
      qc.invalidateQueries({ queryKey: ["olta-positions"] });
    },
  });

  const positions: PositionOut[] = data?.items ?? [];
  const limitEnabled = settings?.limit_entry_enabled ?? false;
  const offsetPct = parseFloat(String(settings?.limit_entry_offset_pct ?? "0.30")).toFixed(2);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500">
            <Anchor className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Olta Pozisyonları</h1>
            <p className="text-sm text-muted-foreground">
              Limit emir (olta) ile açılmış pozisyonlar — offset %{offsetPct}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString("tr-TR") : "—"}</span>
          <RefreshCw className="h-3.5 w-3.5 animate-spin opacity-40" />
        </div>
      </div>

      {/* Mode warning */}
      {!limitEnabled && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Olta modu su an kapali.{" "}
          <Link href="/pozisyon-ayarlari" className="font-semibold underline hover:text-amber-300">
            Ayarlar
          </Link>{" "}
          sayfasinda <strong>Olta limit modu aktif</strong> anahtarini acin.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-border bg-muted/30 p-1 w-fit">
        {(["open", "closed"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
              tab === t
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t === "open" ? "Açık" : "Kapanmış"}
            {data && (
              <span className={cn(
                "ml-2 rounded-full px-1.5 py-0.5 text-xs",
                tab === t ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              )}>
                {data.total}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Position list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          Yükleniyor…
        </div>
      ) : positions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <Anchor className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            {tab === "open"
              ? "Henüz olta ile açılmış aktif pozisyon yok"
              : "Olta ile açılmış kapanmış pozisyon yok"}
          </p>
          {tab === "open" && limitEnabled && (
            <p className="mt-1 text-xs text-muted-foreground/60">
              Sinyal gelince otomatik limit emir atılır ve dolunca burada görünür
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {positions.map((pos) => {
            const isLong = pos.side === "LONG";
            const pnl = parseFloat(pos.unrealized_pnl ?? "0");
            const roi = parseFloat(pos.roi_pct ?? "0");
            const isClosing = closingId === pos.id;

            return (
              <div
                key={pos.id}
                className={cn(
                  "rounded-xl border bg-card/60 p-4",
                  isLong ? "border-green-500/20" : "border-red-500/20"
                )}
              >
                <div className="flex items-start gap-4">
                  {/* Icon + symbol */}
                  <div
                    className={cn(
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg",
                      isLong ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                    )}
                  >
                    {isLong ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                  </div>

                  {/* Main info */}
                  <div className="flex-1 grid grid-cols-2 gap-x-8 gap-y-2 text-sm md:grid-cols-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Sembol</p>
                      <div className="mt-0.5 flex items-center gap-2">
                        <span className="font-bold">{pos.symbol}</span>
                        <span className={cn(
                          "rounded px-1.5 py-0.5 text-xs font-semibold",
                          isLong ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                        )}>
                          {pos.side}
                        </span>
                      </div>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">Giriş / Mark</p>
                      <p className="mt-0.5 tabular-nums">
                        {fp(pos.entry_price, 6)}
                        {pos.mark_price && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            / {fp(pos.mark_price, 6)}
                          </span>
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">PnL / ROI</p>
                      <p className={cn("mt-0.5 tabular-nums font-semibold", pnlColor(pos.unrealized_pnl))}>
                        {pnl >= 0 ? "+" : ""}{fp(pos.unrealized_pnl, 2)} USDT
                        <span className={cn("ml-1 text-xs", roiColor(pos.roi_pct))}>
                          ({roi >= 0 ? "+" : ""}{fp(pos.roi_pct, 2)}%)
                        </span>
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">SL / TP</p>
                      <p className="mt-0.5 tabular-nums text-xs">
                        <span className="text-red-400">{fp(pos.stop_loss_price, 4)}</span>
                        {" / "}
                        <span className="text-green-400">{fp(pos.take_profit_price, 4)}</span>
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">Kaldıraç / Marj</p>
                      <p className="mt-0.5 tabular-nums">
                        x{pos.leverage} · {fp(pos.margin_usdt, 2)} USDT
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">Miktar / Notional</p>
                      <p className="mt-0.5 tabular-nums">
                        {fp(pos.quantity, 4)} · {fp(pos.notional_usdt, 2)} USDT
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">Açılış</p>
                      <p className="mt-0.5 flex items-center gap-1 text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {timeAgo(pos.opened_at)}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">Durum</p>
                      <div className="mt-0.5 flex items-center gap-1">
                        {pos.status === "OPEN" ? (
                          <span className="flex items-center gap-1 text-xs text-green-400">
                            <CheckCircle2 className="h-3 w-3" /> Açık
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <BarChart2 className="h-3 w-3" /> Kapandı
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Close button (only for open) */}
                  {pos.status === "OPEN" && (
                    <button
                      onClick={() => closeMut.mutate(pos.id)}
                      disabled={isClosing}
                      className={cn(
                        "flex shrink-0 items-center gap-1.5 rounded-lg border border-destructive/30 px-3 py-2 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10",
                        isClosing && "cursor-not-allowed opacity-50"
                      )}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      {isClosing ? "Kapatılıyor…" : "Manuel Kapat"}
                    </button>
                  )}
                </div>

                {/* Liq warning */}
                {pos.liquidation_price && pos.status === "OPEN" && (
                  <div className="mt-2 flex items-center gap-1 rounded bg-destructive/5 px-2 py-1 text-xs text-muted-foreground">
                    <AlertTriangle className="h-3 w-3 text-destructive/70" />
                    Likidasyon: <span className="ml-1 font-mono text-destructive/80">{fp(pos.liquidation_price, 4)}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
