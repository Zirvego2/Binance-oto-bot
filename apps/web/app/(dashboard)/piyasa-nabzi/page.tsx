"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bitcoin,
  RefreshCw,
  Scale,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { marketApi } from "@/lib/api";
import type { MarketOverviewOut, TickerMoverOut } from "@/types/api";
import { cn, formatDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const SENTIMENT_CONFIG = {
  BULLISH: {
    label: "Alim Baskisi",
    sub: "Piyasa genelde yukseliyor — coinlerin cogunlugu yesil",
    icon: TrendingUp,
    text: "text-green-400",
    bg: "from-green-500/20 to-emerald-600/5",
    border: "border-green-500/40",
    badge: "bg-green-500/15 text-green-400",
  },
  BEARISH: {
    label: "Satim Baskisi",
    sub: "Piyasa genelde dusuyor — coinlerin cogunlugu kirmizi",
    icon: TrendingDown,
    text: "text-red-400",
    bg: "from-red-500/20 to-rose-600/5",
    border: "border-red-500/40",
    badge: "bg-red-500/15 text-red-400",
  },
  NEUTRAL: {
    label: "Dengeli Piyasa",
    sub: "Net alim veya satim baskisi yok — karisik hareket",
    icon: Scale,
    text: "text-amber-400",
    bg: "from-amber-500/15 to-orange-600/5",
    border: "border-amber-500/30",
    badge: "bg-amber-500/15 text-amber-400",
  },
} as const;

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

function SentimentGauge({ score }: { score: number }) {
  const clamped = Math.max(-100, Math.min(100, score));
  const pct = ((clamped + 100) / 200) * 100;
  const color =
    score >= 15 ? "bg-green-500" : score <= -15 ? "bg-red-500" : "bg-amber-500";

  return (
    <div className="space-y-2">
      <div className="relative h-3 overflow-hidden rounded-full bg-secondary">
        <div
          className={cn("absolute left-0 top-0 h-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
        <div className="absolute left-1/2 top-0 h-full w-0.5 -translate-x-1/2 bg-border" />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>Satim</span>
        <span className="font-mono font-semibold text-foreground">{score > 0 ? "+" : ""}{score.toFixed(1)}</span>
        <span>Alim</span>
      </div>
    </div>
  );
}

function PressureBar({ buy, sell }: { buy: number; sell: number }) {
  return (
    <div className="space-y-2">
      <div className="flex h-4 overflow-hidden rounded-md">
        <div
          className="flex items-center justify-center bg-green-500/80 text-[10px] font-semibold text-white"
          style={{ width: `${buy}%` }}
        >
          {buy >= 18 ? `${buy.toFixed(0)}% Alim` : ""}
        </div>
        <div
          className="flex items-center justify-center bg-red-500/80 text-[10px] font-semibold text-white"
          style={{ width: `${sell}%` }}
        >
          {sell >= 18 ? `${sell.toFixed(0)}% Satim` : ""}
        </div>
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span className="text-green-400">Hacim agirlikli alim: {buy.toFixed(1)}%</span>
        <span className="text-red-400">Hacim agirlikli satim: {sell.toFixed(1)}%</span>
      </div>
    </div>
  );
}

function BreadthBar({ rising, falling, flat }: { rising: number; falling: number; flat: number }) {
  return (
    <div className="space-y-2">
      <div className="flex h-5 overflow-hidden rounded-md">
        <div className="bg-green-500/75" style={{ width: `${rising}%` }} title={`Yukselen ${rising}%`} />
        <div className="bg-zinc-500/50" style={{ width: `${flat}%` }} title={`Yatay ${flat}%`} />
        <div className="bg-red-500/75" style={{ width: `${falling}%` }} title={`Dusen ${falling}%`} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <p className="font-semibold text-green-400">{rising.toFixed(1)}%</p>
          <p className="text-muted-foreground">Yukselen</p>
        </div>
        <div>
          <p className="font-semibold text-zinc-400">{flat.toFixed(1)}%</p>
          <p className="text-muted-foreground">Yatay</p>
        </div>
        <div>
          <p className="font-semibold text-red-400">{falling.toFixed(1)}%</p>
          <p className="text-muted-foreground">Dusen</p>
        </div>
      </div>
    </div>
  );
}

function MoverTable({
  title,
  rows,
  variant,
}: {
  title: string;
  rows: TickerMoverOut[];
  variant: "gain" | "loss" | "volume";
}) {
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <h3 className="mb-3 font-semibold">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="pb-2 pr-2">Sembol</th>
              <th className="pb-2 pr-2">Fiyat</th>
              <th className="pb-2 pr-2">24s</th>
              {variant === "volume" ? <th className="pb-2">Hacim</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} className="border-b border-border/40 last:border-0">
                <td className="py-2 pr-2 font-medium">{row.symbol.replace("USDT", "")}</td>
                <td className="py-2 pr-2 font-mono text-xs">${row.last_price.toLocaleString("en-US", { maximumFractionDigits: 4 })}</td>
                <td
                  className={cn(
                    "py-2 pr-2 font-semibold",
                    row.change_pct >= 0 ? "text-green-400" : "text-red-400"
                  )}
                >
                  {row.change_pct >= 0 ? "+" : ""}
                  {row.change_pct.toFixed(2)}%
                </td>
                {variant === "volume" ? (
                  <td className="py-2 text-muted-foreground">{formatVolume(row.quote_volume_usdt)}</td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function PiyasaNabziPage() {
  const { data, isLoading, isError, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["market-overview"],
    queryFn: () => marketApi.overview(),
    refetchInterval: 30_000,
  });

  const sentimentKey = (data?.sentiment ?? "NEUTRAL") as keyof typeof SENTIMENT_CONFIG;
  const cfg = SENTIMENT_CONFIG[sentimentKey] ?? SENTIMENT_CONFIG.NEUTRAL;
  const Icon = cfg.icon;

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Activity className="h-7 w-7 text-primary" />
            Piyasa Nabzi
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Futures evreninde alim mi satim mi baskin — genislik, hacim ve BTC anlik gorunumu
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw className={cn("mr-2 h-4 w-4", isFetching && "animate-spin")} />
          Yenile
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Piyasa verisi yukleniyor...</p>
      ) : isError || !data ? (
        <p className="text-red-400">Piyasa verisi alinamadi. API ve Binance baglantisini kontrol edin.</p>
      ) : (
        <OverviewContent data={data} cfg={cfg} Icon={Icon} updatedAt={dataUpdatedAt} />
      )}
    </div>
  );
}

function OverviewContent({
  data,
  cfg,
  Icon,
  updatedAt,
}: {
  data: MarketOverviewOut;
  cfg: (typeof SENTIMENT_CONFIG)[keyof typeof SENTIMENT_CONFIG];
  Icon: typeof TrendingUp;
  updatedAt: number;
}) {
  return (
    <>
      <div
        className={cn(
          "rounded-2xl border bg-gradient-to-br p-6",
          cfg.border,
          cfg.bg
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className={cn("inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold", cfg.badge)}>
              <Icon className="h-4 w-4" />
              {cfg.label}
            </div>
            <p className={cn("text-lg font-medium", cfg.text)}>{cfg.sub}</p>
            <p className="text-xs text-muted-foreground">
              {data.universe_count} USDT perpetual · Son guncelleme: {formatDateTime(new Date(updatedAt).toISOString())}
            </p>
          </div>
          <div className="min-w-[220px] rounded-xl border border-border/60 bg-background/60 p-4">
            <p className="mb-2 text-xs text-muted-foreground">Piyasa Nabiz Skoru</p>
            <SentimentGauge score={data.sentiment_score} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card/50 p-4">
          <h2 className="mb-3 flex items-center gap-2 font-semibold">
            <Zap className="h-4 w-4 text-primary" />
            Coin Genisligi (24s)
          </h2>
          <BreadthBar rising={data.rising_pct} falling={data.falling_pct} flat={data.flat_pct} />
          <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
            <StatPill label="Yukselen" value={data.rising_count} tone="green" />
            <StatPill label="Yatay" value={data.flat_count} tone="zinc" />
            <StatPill label="Dusen" value={data.falling_count} tone="red" />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card/50 p-4">
          <h2 className="mb-3 flex items-center gap-2 font-semibold">
            <Scale className="h-4 w-4 text-primary" />
            Hacim Baskisi (Alim vs Satim)
          </h2>
          <PressureBar buy={data.buy_pressure_pct} sell={data.sell_pressure_pct} />
          <p className="mt-3 text-xs text-muted-foreground">
            Yukselen coinlerin 24s USDT hacmi vs dusen coinlerin hacmi. Yuksek alim yuzdesi = para yukselen tarafa akiyor.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Ort. Degisim"
          value={`${data.avg_change_pct >= 0 ? "+" : ""}${data.avg_change_pct.toFixed(2)}%`}
          positive={data.avg_change_pct >= 0}
        />
        <MetricCard
          label="Medyan Degisim"
          value={`${data.median_change_pct >= 0 ? "+" : ""}${data.median_change_pct.toFixed(2)}%`}
          positive={data.median_change_pct >= 0}
        />
        <MetricCard label="Toplam 24s Hacim" value={`$${formatVolume(data.total_volume_24h_usdt)}`} />
        <MetricCard
          label="Bot Rejimi"
          value={data.bot_regime_direction ?? "—"}
          hint={
            data.market_direction_filter_enabled
              ? "Yon filtresi acik — sadece rejime uygun sinyaller"
              : "Yon filtresi kapali"
          }
        />
      </div>

      <div className="rounded-xl border border-border bg-card/50 p-4">
        <h2 className="mb-4 flex items-center gap-2 font-semibold">
          <Bitcoin className="h-5 w-5 text-amber-400" />
          BTC Ozeti
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div>
            <p className="text-xs text-muted-foreground">Fiyat</p>
            <p className="font-mono text-lg font-bold">${data.btc.last_price.toLocaleString("en-US")}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">24s Degisim</p>
            <p className={cn("font-semibold", data.btc.change_24h_pct >= 0 ? "text-green-400" : "text-red-400")}>
              {data.btc.change_24h_pct >= 0 ? "+" : ""}
              {data.btc.change_24h_pct.toFixed(2)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Mark Fiyat</p>
            <p className="font-mono font-semibold">${data.btc.mark_price.toLocaleString("en-US")}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Funding</p>
            <p className={cn("font-semibold", data.btc.funding_rate_pct >= 0 ? "text-green-400" : "text-red-400")}>
              {data.btc.funding_rate_pct >= 0 ? "+" : ""}
              {data.btc.funding_rate_pct.toFixed(4)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">24s Hacim</p>
            <p className="font-semibold">${formatVolume(data.btc.quote_volume_24h_usdt)}</p>
          </div>
        </div>

        {data.order_book_pressure ? (
          <div className="mt-4 rounded-lg border border-border/60 bg-background/40 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">BTC Emir Defteri Baskisi (anlik)</p>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="text-green-400">
                <ArrowUpRight className="mr-1 inline h-4 w-4" />
                Bid {data.order_book_pressure.bid_pct.toFixed(1)}%
              </span>
              <span className="text-red-400">
                <ArrowDownRight className="mr-1 inline h-4 w-4" />
                Ask {data.order_book_pressure.ask_pct.toFixed(1)}%
              </span>
              <span
                className={cn(
                  "rounded px-2 py-0.5 text-xs font-semibold",
                  data.order_book_pressure.bias === "BUY"
                    ? "bg-green-500/15 text-green-400"
                    : data.order_book_pressure.bias === "SELL"
                      ? "bg-red-500/15 text-red-400"
                      : "bg-zinc-500/15 text-zinc-400"
                )}
              >
                {data.order_book_pressure.bias === "BUY"
                  ? "Alim baskisi"
                  : data.order_book_pressure.bias === "SELL"
                    ? "Satim baskisi"
                    : "Dengeli defter"}
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <MoverTable title="En Cok Yukselenler" rows={data.top_gainers} variant="gain" />
        <MoverTable title="En Cok Dusenler" rows={data.top_losers} variant="loss" />
        <MoverTable title="En Yuksek Hacim" rows={data.top_volume} variant="volume" />
      </div>

      <div className="rounded-xl border border-dashed border-border/80 bg-card/30 p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Bu sayfa ne anlatiyor?</p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li><strong>Coin genisligi:</strong> Kac coin yukseliyor / dusuyor — piyasanin genel yonu.</li>
          <li><strong>Hacim baskisi:</strong> Para hangi tarafa daha cok akiyor (yuzdesel hacim agirligi).</li>
          <li><strong>BTC emir defteri:</strong> Anlik alim-satim duvarlari — kisa vadeli baskı ipucu.</li>
          <li><strong>Bot rejimi:</strong> Botun BTC tabanli LONG/SHORT/NOTR karari; filtre aciksa sadece uyumlu sinyaller acilir.</li>
        </ul>
      </div>
    </>
  );
}

function StatPill({ label, value, tone }: { label: string; value: number; tone: "green" | "red" | "zinc" }) {
  const cls =
    tone === "green"
      ? "text-green-400 bg-green-500/10"
      : tone === "red"
        ? "text-red-400 bg-red-500/10"
        : "text-zinc-400 bg-zinc-500/10";
  return (
    <div className={cn("rounded-lg px-3 py-2 text-center", cls)}>
      <p className="text-lg font-bold">{value}</p>
      <p className="text-xs opacity-80">{label}</p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  positive,
  hint,
}: {
  label: string;
  value: string;
  positive?: boolean;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-xl font-bold",
          positive === true ? "text-green-400" : positive === false ? "text-red-400" : ""
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-[10px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
