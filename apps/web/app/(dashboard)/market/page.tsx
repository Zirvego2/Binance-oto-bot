"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  Bitcoin,
  ArrowUpRight,
  ArrowDownRight,
  Shield,
  Sparkles,
} from "lucide-react";
import { marketApi, settingsApi } from "@/lib/api";
import type { MarketRegimeOut, TimeframeAnalysisOut } from "@/types/api";
import { cn, formatDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MarketAiResearchDialog } from "@/components/market/market-ai-research-dialog";

const DIRECTION_CONFIG = {
  LONG: {
    label: "LONG Piyasa",
    sub: "BTC yukari — altcoinler genelde yukselir",
    icon: TrendingUp,
    bg: "from-green-500/20 to-emerald-600/5",
    border: "border-green-500/40",
    text: "text-green-400",
    badge: "bg-green-500/15 text-green-400",
  },
  SHORT: {
    label: "SHORT Piyasa",
    sub: "BTC asagi — altcoinler genelde duser",
    icon: TrendingDown,
    bg: "from-red-500/20 to-rose-600/5",
    border: "border-red-500/40",
    text: "text-red-400",
    badge: "bg-red-500/15 text-red-400",
  },
  NEUTRAL: {
    label: "NOTR Piyasa",
    sub: "BTC yatay — yon net degil, dikkatli olun",
    icon: Minus,
    bg: "from-zinc-500/15 to-zinc-600/5",
    border: "border-zinc-500/30",
    text: "text-zinc-400",
    badge: "bg-zinc-500/15 text-zinc-400",
  },
} as const;

function TrendBadge({ trend }: { trend: string }) {
  const cls =
    trend === "BULLISH"
      ? "text-green-400 bg-green-500/10"
      : trend === "BEARISH"
        ? "text-red-400 bg-red-500/10"
        : "text-amber-400 bg-amber-500/10";
  const label = trend === "BULLISH" ? "Yukselis" : trend === "BEARISH" ? "Dusus" : "Karisik";
  return <span className={cn("rounded px-2 py-0.5 text-xs font-medium", cls)}>{label}</span>;
}

function TimeframeCard({ title, tf }: { title: string; tf: TimeframeAnalysisOut }) {
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        <span className="text-xs text-muted-foreground">{tf.interval}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Fiyat</p>
          <p className="font-mono font-semibold">${tf.price.toLocaleString("en-US")}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">RSI</p>
          <p className={cn("font-semibold", tf.rsi >= 55 ? "text-green-400" : tf.rsi <= 45 ? "text-red-400" : "")}>
            {tf.rsi.toFixed(1)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">1 Saat</p>
          <p className={cn("font-semibold", tf.change_1h_pct >= 0 ? "text-green-400" : "text-red-400")}>
            {tf.change_1h_pct >= 0 ? "+" : ""}
            {tf.change_1h_pct.toFixed(2)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">4 Saat</p>
          <p className={cn("font-semibold", tf.change_4h_pct >= 0 ? "text-green-400" : "text-red-400")}>
            {tf.change_4h_pct >= 0 ? "+" : ""}
            {tf.change_4h_pct.toFixed(2)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Trend</p>
          <TrendBadge trend={tf.trend} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Momentum</p>
          <p className="text-xs font-medium">{tf.momentum.replace(/_/g, " ")}</p>
        </div>
      </div>
      <div className="mt-3 border-t border-border/50 pt-3 text-xs text-muted-foreground">
        EMA {tf.ema_fast.toFixed(0)} / {tf.ema_mid.toFixed(0)} / {tf.ema_slow.toFixed(0)}
      </div>
    </div>
  );
}

export default function MarketPage() {
  const [aiOpen, setAiOpen] = useState(false);

  const { data, isLoading, isError, dataUpdatedAt, refetch, isFetching } = useQuery({
    queryKey: ["market-regime"],
    queryFn: () => marketApi.regime(),
    refetchInterval: 30_000,
  });

  const { data: settings } = useQuery({
    queryKey: ["bot-settings"],
    queryFn: () => settingsApi.get(),
  });

  const cfg = data ? DIRECTION_CONFIG[data.direction] : DIRECTION_CONFIG.NEUTRAL;
  const Icon = cfg.icon;
  const filterOn = settings?.market_direction_filter_enabled ?? false;

  const aiResearch = useMutation({
    mutationFn: (forceRefresh?: boolean) => marketApi.aiResearch(forceRefresh),
    onSuccess: () => setAiOpen(true),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500/10 text-orange-500">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Market Piyasasi</h1>
            <p className="text-sm text-muted-foreground">BTC yonu ile kisa vadeli piyasa egilimi</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="default"
            size="sm"
            className="gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500"
            disabled={isLoading || isError || aiResearch.isPending}
            onClick={() => aiResearch.mutate(false)}
          >
            {aiResearch.isPending ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Yapay Zeka Gorusu Al
          </Button>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground hover:bg-secondary/50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
            {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString("tr-TR") : "—"}
          </button>
        </div>
      </div>

      <MarketAiResearchDialog
        open={aiOpen}
        onOpenChange={setAiOpen}
        data={aiResearch.data ?? null}
        loading={aiResearch.isPending}
        onRefresh={() => aiResearch.mutate(true)}
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-24 text-muted-foreground">
          <RefreshCw className="mr-2 h-5 w-5 animate-spin" />
          BTC analiz ediliyor…
        </div>
      ) : isError || !data ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center text-destructive">
          Piyasa verisi alinamadi. Binance baglantisini kontrol edin.
        </div>
      ) : (
        <>
          {/* Ana yon karti */}
          <div
            className={cn(
              "relative overflow-hidden rounded-2xl border bg-gradient-to-br p-6 md:p-8",
              cfg.bg,
              cfg.border
            )}
          >
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className={cn("rounded-2xl p-4", cfg.badge)}>
                  <Icon className="h-10 w-10" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Bitcoin className="h-5 w-5 text-orange-400" />
                    <span className="text-sm text-muted-foreground">BTCUSDT</span>
                  </div>
                  <h2 className={cn("mt-1 text-3xl font-bold", cfg.text)}>{cfg.label}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{cfg.sub}</p>
                  <p className="mt-3 max-w-lg text-sm">{data.reason}</p>
                </div>
              </div>

              <div className="flex flex-col items-start gap-3 md:items-end">
                <div className="text-right">
                  <p className="text-3xl font-bold tabular-nums">
                    ${data.btc_price.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </p>
                  <div className="mt-1 flex gap-3 text-sm">
                    <span className={cn("flex items-center gap-0.5", data.change_1h_pct >= 0 ? "text-green-400" : "text-red-400")}>
                      {data.change_1h_pct >= 0 ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                      1s: {data.change_1h_pct >= 0 ? "+" : ""}{data.change_1h_pct.toFixed(2)}%
                    </span>
                    <span className={cn(data.change_4h_pct >= 0 ? "text-green-400" : "text-red-400")}>
                      4s: {data.change_4h_pct >= 0 ? "+" : ""}{data.change_4h_pct.toFixed(2)}%
                    </span>
                  </div>
                </div>

                <div className="w-full min-w-[200px] md:w-48">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">Guven</span>
                    <span className={cn("font-bold", cfg.text)}>{data.confidence.toFixed(0)}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        data.direction === "LONG" ? "bg-green-500" : data.direction === "SHORT" ? "bg-red-500" : "bg-zinc-500"
                      )}
                      style={{ width: `${data.confidence}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Skorlar */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <ScoreCard label="Long Skor" value={data.long_score} color="green" />
            <ScoreCard label="Short Skor" value={data.short_score} color="red" />
            <ScoreCard
              label="Net Egilim"
              value={data.long_score - data.short_score}
              color={data.long_score > data.short_score ? "green" : data.long_score < data.short_score ? "red" : "zinc"}
            />
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <p className="text-xs text-muted-foreground">Son Analiz</p>
              <p className="mt-1 text-sm font-medium">{formatDateTime(data.analyzed_at)}</p>
            </div>
          </div>

          {/* Timeframe kartlari */}
          <div className="grid gap-4 md:grid-cols-2">
            <TimeframeCard title="Kisa Vade (Ana)" tf={data.primary} />
            <TimeframeCard title="Orta Vade (Dogrulama)" tf={data.confirm} />
          </div>

          {/* Oneri + filtre */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <h3 className="mb-2 font-semibold">Islem Onerisi</h3>
              <p className="text-sm text-muted-foreground">{data.recommendation}</p>
              <ul className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                <li>• LONG piyasa → Long sinyaller oncelikli</li>
                <li>• SHORT piyasa → Short sinyaller oncelikli</li>
                <li>• NOTR → Her iki yon icin yuksek skorlu sinyallere bakin</li>
              </ul>
            </div>
            <div className="rounded-xl border border-border bg-card/40 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                <h3 className="font-semibold">Bot Filtresi</h3>
              </div>
              <p className={cn("text-sm font-medium", filterOn ? "text-green-400" : "text-amber-400")}>
                {filterOn ? "Aktif — piyasa yonune ters islem acilmaz" : "Kapali — tum sinyaller degerlendirilir"}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Ayarlar&apos;dan <code className="rounded bg-muted px-1">market_direction_filter_enabled</code> ile acip kapatabilirsiniz.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ScoreCard({ label, value, color }: { label: string; value: number; color: "green" | "red" | "zinc" }) {
  const cls = color === "green" ? "text-green-400" : color === "red" ? "text-red-400" : "text-zinc-400";
  return (
    <div className="rounded-xl border border-border bg-card/40 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold tabular-nums", cls)}>{value.toFixed(1)}</p>
    </div>
  );
}
