"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { avciApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { AvciChartHours, AvciCoinOut } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn, formatDateTimeShort, formatNumber, toNumber } from "@/lib/utils";

const HOUR_OPTIONS: { value: AvciChartHours; label: string }[] = [
  { value: 1, label: "1s" },
  { value: 4, label: "4s" },
  { value: 6, label: "6s" },
  { value: 12, label: "12s" },
  { value: 24, label: "24s" },
];

function formatChartLabel(iso: string, hours: AvciChartHours): string {
  const d = new Date(iso);
  if (hours >= 12) {
    return d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }
  return formatDateTimeShort(iso);
}

export interface PositionChartLevels {
  side: string;
  entry_price: string | number | null;
  stop_loss_price: string | number | null;
  take_profit_price: string | number | null;
}

interface CoinChartDialogProps {
  symbol?: string | null;
  coin?: AvciCoinOut | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTrade?: (symbol: string, side: "LONG" | "SHORT") => void;
  openingKey?: string | null;
  showTradeActions?: boolean;
  positionLevels?: PositionChartLevels | null;
}

export function CoinChartDialog({
  symbol: symbolProp,
  coin,
  open,
  onOpenChange,
  onTrade,
  openingKey = null,
  showTradeActions = true,
  positionLevels,
}: CoinChartDialogProps) {
  const symbol = symbolProp ?? coin?.symbol ?? "";
  const [hours, setHours] = React.useState<AvciChartHours>(1);

  React.useEffect(() => {
    if (open) setHours(1);
  }, [open, symbol]);

  const { data: chart, isLoading, isFetching, isError, error: chartError } = useQuery({
    queryKey: ["avci-chart", symbol, hours],
    queryFn: () => avciApi.chart(symbol, hours),
    enabled: open && Boolean(symbol),
    refetchInterval: open ? 5000 : false,
  });

  const chartData = React.useMemo(
    () =>
      (chart?.klines ?? []).map((k) => ({
        time: k.time,
        label: formatChartLabel(k.time, hours),
        close: k.close,
        high: k.high,
        low: k.low,
      })),
    [chart?.klines, hours]
  );

  const changePct = chart?.change_pct ?? coin?.change_pct ?? 0;
  const lastPrice = chart?.last_price ?? coin?.last_price ?? 0;
  const interval = chart?.interval ?? (hours === 1 ? "1m" : hours <= 6 ? "5m" : "15m");
  const changeColor = changePct >= 0 ? "text-green-400" : "text-red-400";
  const strokeColor = changePct >= 0 ? "#4ade80" : "#f87171";
  const longLoading = openingKey === `${symbol}:LONG`;
  const shortLoading = openingKey === `${symbol}:SHORT`;
  const fillId = `avciPriceFill-${symbol || "chart"}`;
  const entryPrice = positionLevels ? toNumber(positionLevels.entry_price) : null;
  const stopLossPrice = positionLevels ? toNumber(positionLevels.stop_loss_price) : null;
  const takeProfitPrice = positionLevels ? toNumber(positionLevels.take_profit_price) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl gap-3">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {symbol.replace("USDT", "")}/USDT
            <span className={cn("text-base font-bold tabular-nums", changeColor)}>
              {changePct > 0 ? "+" : ""}
              {formatNumber(changePct, 2)}%
            </span>
            <span className="text-sm font-normal text-muted-foreground">
              son {hours} saat · {interval}
            </span>
          </DialogTitle>
          <DialogDescription>
            ${formatNumber(lastPrice, 6)} · Grafik {isFetching ? "guncelleniyor..." : "canli"}
            {positionLevels ? (
              <>
                {" · "}
                <span className="font-medium">{positionLevels.side}</span>
                {entryPrice != null && entryPrice > 0 ? (
                  <> · Giris ${formatNumber(entryPrice, 4)}</>
                ) : null}
              </>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-1.5">
          {HOUR_OPTIONS.map((opt) => (
            <Button
              key={opt.value}
              type="button"
              size="sm"
              variant={hours === opt.value ? "default" : "outline"}
              className="h-8 min-w-[44px] px-3"
              onClick={() => setHours(opt.value)}
            >
              {opt.label}
            </Button>
          ))}
        </div>

        <div className="h-[280px] w-full rounded-lg border border-border/60 bg-secondary/20 p-2">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : chartData.length === 0 && !isError ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
              <p>Grafik verisi yok</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={strokeColor} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={strokeColor} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.4} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  interval="preserveStartEnd"
                  minTickGap={hours >= 24 ? 40 : hours >= 12 ? 32 : 28}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  width={56}
                  tickFormatter={(v) => formatNumber(v, 4)}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => [`$${formatNumber(value, 6)}`, "Fiyat"]}
                  labelFormatter={(label) => String(label)}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={strokeColor}
                  strokeWidth={2}
                  fill={`url(#${fillId})`}
                  dot={false}
                  isAnimationActive={false}
                />
                {entryPrice != null && entryPrice > 0 ? (
                  <ReferenceLine
                    y={entryPrice}
                    stroke="#60a5fa"
                    strokeDasharray="4 4"
                    label={{ value: "Giris", position: "insideTopRight", fill: "#60a5fa", fontSize: 10 }}
                  />
                ) : null}
                {stopLossPrice != null && stopLossPrice > 0 ? (
                  <ReferenceLine
                    y={stopLossPrice}
                    stroke="#f87171"
                    strokeDasharray="4 4"
                    label={{ value: "SL", position: "insideBottomRight", fill: "#f87171", fontSize: 10 }}
                  />
                ) : null}
                {takeProfitPrice != null && takeProfitPrice > 0 ? (
                  <ReferenceLine
                    y={takeProfitPrice}
                    stroke="#4ade80"
                    strokeDasharray="4 4"
                    label={{ value: "TP", position: "insideTopLeft", fill: "#4ade80", fontSize: 10 }}
                  />
                ) : null}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {showTradeActions && onTrade ? (
          <div className="flex justify-end gap-2">
            <Button
              className="bg-green-600 hover:bg-green-700"
              disabled={!symbol || longLoading || shortLoading}
              onClick={() => onTrade(symbol, "LONG")}
            >
              {longLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "LONG Ac"}
            </Button>
            <Button
              variant="destructive"
              disabled={!symbol || longLoading || shortLoading}
              onClick={() => onTrade(symbol, "SHORT")}
            >
              {shortLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "SHORT Ac"}
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
