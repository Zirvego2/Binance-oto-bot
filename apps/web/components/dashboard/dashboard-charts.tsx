"use client";

import * as React from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn, formatPct, formatUsdt, pnlColorClass, toNumber } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardStatisticsOut } from "@/types/api";

const CHART_MARGIN = { top: 8, right: 8, left: 4, bottom: 0 };
const AXIS_COLOR = "hsl(215 20% 58%)";
const GRID_COLOR = "hsl(217 33% 15%)";
const TOOLTIP_STYLE: React.CSSProperties = {
  background: "hsl(222 40% 8%)",
  border: "1px solid hsl(217 33% 24%)",
  borderRadius: "8px",
  boxShadow: "0 8px 24px hsl(222 47% 4% / 0.45)",
  fontSize: "12px",
  padding: "10px 12px",
};
const SUCCESS = "hsl(142 71% 45%)";
const DESTRUCTIVE = "hsl(0 72% 51%)";
const ACCENT = "hsl(45 93% 47%)";

export interface DashboardChartPoint {
  date: string;
  fullDate: string;
  netPnl: number;
  cumulativePnl: number;
  trades: number;
  winning: number;
  losing: number;
  winRate: number;
}

function buildChartData(statistics: DashboardStatisticsOut[]): DashboardChartPoint[] {
  let cumulative = 0;
  return statistics
    .slice()
    .reverse()
    .map((row) => {
      const netPnl = toNumber(row.net_pnl_usdt);
      cumulative += netPnl;
      const [, month, day] = row.stat_date.split("-");
      return {
        date: `${day}.${month}`,
        fullDate: row.stat_date,
        netPnl,
        cumulativePnl: cumulative,
        trades: row.trades_count,
        winning: row.winning_trades,
        losing: row.losing_trades,
        winRate: toNumber(row.win_rate_pct),
      };
    });
}

function formatAxisValue(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return value.toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number; payload: DashboardChartPoint }>;
  label?: string;
  mode: "pnl" | "trades";
}

function ChartTooltip({ active, payload, label, mode }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  return (
    <div style={TOOLTIP_STYLE} className="min-w-[180px] space-y-1.5">
      <p className="text-xs font-semibold text-foreground">{label ?? point.date}</p>
      {mode === "pnl" ? (
        <>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Gunluk Net PnL</span>
            <span className={cn("font-semibold tabular-nums", pnlColorClass(point.netPnl))}>
              {formatUsdt(point.netPnl)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Kumulatif</span>
            <span className={cn("font-semibold tabular-nums", pnlColorClass(point.cumulativePnl))}>
              {formatUsdt(point.cumulativePnl)}
            </span>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Toplam islem</span>
            <span className="font-semibold tabular-nums">{point.trades}</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Kazanan</span>
            <span className="font-semibold tabular-nums text-success">{point.winning}</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-muted-foreground">Kaybeden</span>
            <span className="font-semibold tabular-nums text-destructive">{point.losing}</span>
          </div>
        </>
      )}
      <div className="flex items-center justify-between gap-4 border-t border-border/60 pt-1.5">
        <span className="text-muted-foreground">Kazanma orani</span>
        <span className="font-semibold tabular-nums">{formatPct(point.winRate)}</span>
      </div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border/80 bg-muted/20">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function DashboardCharts({ statistics }: { statistics: DashboardStatisticsOut[] | undefined }) {
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const chartData = React.useMemo(() => buildChartData(statistics ?? []), [statistics]);

  const summary = React.useMemo(() => {
    const totalNetPnl = chartData.reduce((acc, row) => acc + row.netPnl, 0);
    const totalTrades = chartData.reduce((acc, row) => acc + row.trades, 0);
    const profitableDays = chartData.filter((row) => row.netPnl > 0).length;
    return { totalNetPnl, totalTrades, profitableDays, days: chartData.length };
  }, [chartData]);

  if (!mounted) {
    return (
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent>
            <EmptyChart message="Grafikler yukleniyor..." />
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <EmptyChart message="Grafikler yukleniyor..." />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Performans Ozeti</CardTitle>
            <CardDescription>Son 14 gun</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyChart message="Henuz istatistik verisi yok" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Islem Dagilimi</CardTitle>
            <CardDescription>Kazanan / kaybeden</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyChart message="Henuz istatistik verisi yok" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2 overflow-hidden border-border/80">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Performans Ozeti</CardTitle>
              <CardDescription>Son {summary.days} gun · gunluk net PnL ve kumulatif egri</CardDescription>
            </div>
            <div className="flex flex-wrap gap-4 text-right text-xs">
              <div>
                <p className="text-muted-foreground">Donem Net PnL</p>
                <p className={cn("text-base font-semibold tabular-nums", pnlColorClass(summary.totalNetPnl))}>
                  {formatUsdt(summary.totalNetPnl)}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Karli gun</p>
                <p className="text-base font-semibold tabular-nums">
                  {summary.profitableDays}/{summary.days}
                </p>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="h-72 pb-4 pl-0">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={CHART_MARGIN}>
              <defs>
                <linearGradient id="pnlAreaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID_COLOR} strokeDasharray="4 4" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: AXIS_COLOR, fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: GRID_COLOR }}
                dy={8}
                minTickGap={24}
              />
              <YAxis
                yAxisId="pnl"
                tick={{ fill: AXIS_COLOR, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatAxisValue}
                width={48}
              />
              <YAxis
                yAxisId="cumulative"
                orientation="right"
                tick={{ fill: AXIS_COLOR, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatAxisValue}
                width={48}
              />
              <Tooltip content={<ChartTooltip mode="pnl" />} cursor={{ fill: "hsl(217 33% 17% / 0.35)" }} />
              <ReferenceLine yAxisId="pnl" y={0} stroke="hsl(215 20% 40%)" strokeDasharray="4 4" />
              <Bar yAxisId="pnl" dataKey="netPnl" name="Gunluk Net PnL" radius={[4, 4, 0, 0]} maxBarSize={28}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.fullDate}
                    fill={entry.netPnl >= 0 ? SUCCESS : DESTRUCTIVE}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
              <Area
                yAxisId="cumulative"
                type="monotone"
                dataKey="cumulativePnl"
                name="Kumulatif PnL"
                stroke={ACCENT}
                strokeWidth={2.5}
                fill="url(#pnlAreaGradient)"
                dot={false}
                activeDot={{ r: 4, fill: ACCENT, stroke: "hsl(222 40% 9%)", strokeWidth: 2 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-border/80">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Islem Dagilimi</CardTitle>
              <CardDescription>Gunluk kazanan ve kaybeden islemler</CardDescription>
            </div>
            <div className="text-right text-xs">
              <p className="text-muted-foreground">Toplam islem</p>
              <p className="text-base font-semibold tabular-nums">{summary.totalTrades}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="h-72 pb-4 pl-0">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={CHART_MARGIN} barCategoryGap="20%">
              <CartesianGrid stroke={GRID_COLOR} strokeDasharray="4 4" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: AXIS_COLOR, fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: GRID_COLOR }}
                dy={8}
                minTickGap={24}
              />
              <YAxis
                tick={{ fill: AXIS_COLOR, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                width={36}
              />
              <Tooltip content={<ChartTooltip mode="trades" />} cursor={{ fill: "hsl(217 33% 17% / 0.35)" }} />
              <Legend
                verticalAlign="top"
                align="right"
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: "11px", paddingBottom: "8px", color: AXIS_COLOR }}
              />
              <Bar dataKey="winning" name="Kazanan" stackId="trades" fill={SUCCESS} radius={[0, 0, 0, 0]} maxBarSize={32} />
              <Bar dataKey="losing" name="Kaybeden" stackId="trades" fill={DESTRUCTIVE} radius={[4, 4, 0, 0]} maxBarSize={32} />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
