"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Loader2, RefreshCw } from "lucide-react";

import { avciApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { AvciCoinOut } from "@/types/api";
import { CoinChartDialog } from "@/components/avci/coin-chart-dialog";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast-provider";
import { cn, formatDateTime, formatNumber } from "@/lib/utils";

const LIVE_REFRESH_MS = 5000;

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

export default function AvciPage() {
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [openingKey, setOpeningKey] = React.useState<string | null>(null);
  const [selectedCoin, setSelectedCoin] = React.useState<AvciCoinOut | null>(null);
  const [chartOpen, setChartOpen] = React.useState(false);

  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["avci-scan"],
    queryFn: () => avciApi.scan(15),
    refetchInterval: LIVE_REFRESH_MS,
    refetchIntervalInBackground: true,
    staleTime: 0,
  });

  const openMutation = useMutation({
    mutationFn: ({ symbol, side }: { symbol: string; side: "LONG" | "SHORT" }) =>
      avciApi.open(symbol, side),
    onMutate: ({ symbol, side }) => {
      setOpeningKey(`${symbol}:${side}`);
    },
    onSettled: () => setOpeningKey(null),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      push({
        title: result.message,
        description: result.status === "CLOSED" ? "Pozisyon borsada hizla kapandi" : undefined,
        variant: result.status === "OPEN" ? "success" : "info",
      });
    },
    onError: (err) => {
      push({
        title: "Pozisyon acilamadi",
        description: err instanceof ApiError ? err.message : "Bilinmeyen hata",
        variant: "error",
      });
    },
  });

  const handleOpenPosition = (symbol: string, side: "LONG" | "SHORT") => {
    openMutation.mutate({ symbol, side });
  };

  const handleSelectCoin = (coin: AvciCoinOut) => {
    setSelectedCoin(coin);
    setChartOpen(true);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="Avcı"
          description="24 saatte en cok yukselen ve dusen coinleri canli tarayin. Coin adina tiklayinca son 1 saatlik grafik acilir."
        />
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-1 text-xs text-green-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </span>
            Canli · {LIVE_REFRESH_MS / 1000}s
          </span>
          <Button variant="outline" className="gap-2" disabled={isFetching} onClick={() => refetch()}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Yenile
          </Button>
        </div>
      </div>

      {data && (
        <p className="text-xs text-muted-foreground">
          Son guncelleme: {formatDateTime(new Date(dataUpdatedAt).toISOString())} · Coin tikla = grafik · Marj/kaldirac
          Pozisyon Ayarlari&apos;ndan
        </p>
      )}

      {isLoading && (
        <div className="flex min-h-[30vh] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
          <p className="font-medium">Tarama basarisiz</p>
          <p className="mt-1 text-muted-foreground">
            {error instanceof ApiError ? error.message : "Piyasa verisi alinamadi"}
          </p>
          <Button className="mt-3" variant="outline" size="sm" onClick={() => refetch()}>
            Tekrar Dene
          </Button>
        </div>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <CoinPanel
            title="En Cok Yukselenler"
            subtitle="24s en yuksek artis"
            icon={ArrowUpRight}
            tone="green"
            coins={data.top_gainers}
            openingKey={openingKey}
            onSelect={handleSelectCoin}
            onOpen={handleOpenPosition}
          />
          <CoinPanel
            title="En Cok Dusenler"
            subtitle="24s en buyuk dusus"
            icon={ArrowDownRight}
            tone="red"
            coins={data.top_losers}
            openingKey={openingKey}
            onSelect={handleSelectCoin}
            onOpen={handleOpenPosition}
          />
        </div>
      )}

      <CoinChartDialog
        coin={selectedCoin}
        open={chartOpen}
        onOpenChange={setChartOpen}
        onTrade={handleOpenPosition}
        openingKey={openingKey}
      />
    </div>
  );
}

function CoinPanel({
  title,
  subtitle,
  icon: Icon,
  tone,
  coins,
  openingKey,
  onSelect,
  onOpen,
}: {
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: "green" | "red";
  coins: AvciCoinOut[];
  openingKey: string | null;
  onSelect: (coin: AvciCoinOut) => void;
  onOpen: (symbol: string, side: "LONG" | "SHORT") => void;
}) {
  const border = tone === "green" ? "border-green-500/30" : "border-red-500/30";
  const headerBg = tone === "green" ? "bg-green-500/10" : "bg-red-500/10";
  const iconColor = tone === "green" ? "text-green-400" : "text-red-400";

  return (
    <div className={cn("overflow-hidden rounded-xl border", border)}>
      <div className={cn("flex items-center gap-2 border-b border-border/50 px-4 py-3", headerBg)}>
        <Icon className={cn("h-5 w-5", iconColor)} />
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>

      <div className="divide-y divide-border/40">
        {coins.length === 0 && (
          <p className="p-4 text-sm text-muted-foreground">Coin bulunamadi.</p>
        )}
        {coins.map((coin, idx) => (
          <CoinRow
            key={coin.symbol}
            rank={idx + 1}
            coin={coin}
            openingKey={openingKey}
            onSelect={() => onSelect(coin)}
            onOpen={onOpen}
          />
        ))}
      </div>
    </div>
  );
}

function CoinRow({
  rank,
  coin,
  openingKey,
  onSelect,
  onOpen,
}: {
  rank: number;
  coin: AvciCoinOut;
  openingKey: string | null;
  onSelect: () => void;
  onOpen: (symbol: string, side: "LONG" | "SHORT") => void;
}) {
  const changeColor = coin.change_pct >= 0 ? "text-green-400" : "text-red-400";
  const longLoading = openingKey === `${coin.symbol}:LONG`;
  const shortLoading = openingKey === `${coin.symbol}:SHORT`;

  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 sm:gap-3">
      <span className="w-5 text-xs font-mono text-muted-foreground">{rank}</span>
      <button
        type="button"
        onClick={onSelect}
        className="min-w-[88px] flex-1 rounded-md text-left transition-colors hover:bg-secondary/50 px-1 py-0.5 -mx-1"
      >
        <p className="font-semibold">{coin.symbol.replace("USDT", "")}</p>
        <p className="text-[11px] text-muted-foreground">
          ${formatNumber(coin.last_price, 4)} · {formatVolume(coin.quote_volume_usdt)} · grafik icin tikla
        </p>
      </button>
      <span className={cn("min-w-[64px] text-right text-sm font-bold tabular-nums", changeColor)}>
        {coin.change_pct > 0 ? "+" : ""}
        {formatNumber(coin.change_pct, 2)}%
      </span>
      <div className="flex gap-1.5">
        <Button
          size="sm"
          className="h-8 bg-green-600 px-3 hover:bg-green-700"
          disabled={longLoading || shortLoading}
          onClick={(e) => {
            e.stopPropagation();
            onOpen(coin.symbol, "LONG");
          }}
        >
          {longLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "LONG"}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          className="h-8 px-3"
          disabled={longLoading || shortLoading}
          onClick={(e) => {
            e.stopPropagation();
            onOpen(coin.symbol, "SHORT");
          }}
        >
          {shortLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "SHORT"}
        </Button>
      </div>
    </div>
  );
}
