"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, CalendarDays, Clock } from "lucide-react";

import { dashboardApi, tradesApi } from "@/lib/api";
import { formatDateTimeShort, formatPct, formatTry, formatUsdt, pnlColorClass } from "@/lib/utils";
import { PageHeader } from "@/components/shared/page-header";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { SideBadge } from "@/components/shared/side-badge";
import { StatCard } from "@/components/shared/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { TradePnlPeriodSummary } from "@/types/api";

const CLOSE_REASON_LABEL: Record<string, string> = {
  STOP_LOSS: "Zarar Durdur",
  TAKE_PROFIT: "Kar Al",
  MANUAL: "Manuel",
  EMERGENCY_STOP: "Acil Durdurma",
  LIQUIDATION: "Likidasyon",
  UNKNOWN: "Bilinmiyor",
};

const PERIOD_HINT_CLASS = "text-base font-medium leading-snug";

function periodHint(period: TradePnlPeriodSummary): string {
  return `${period.trades_count} islem, ${period.winning_trades} kazanan, ${period.losing_trades} kaybeden, kazanma orani ${formatPct(period.win_rate_pct)}`;
}

export default function TradesPage() {
  const [page, setPage] = React.useState(1);
  const [symbol, setSymbol] = React.useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["trades", page, symbol],
    queryFn: () => tradesApi.list({ page, page_size: 25, symbol: symbol || undefined }),
  });

  const { data: pnlSummary } = useQuery({
    queryKey: ["trades", "pnl-summary", symbol],
    queryFn: () => tradesApi.pnlSummary({ symbol: symbol || undefined }),
    refetchInterval: 30_000,
  });

  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    refetchInterval: 30_000,
  });

  const tryRate = dashboard?.usdt_try_rate;

  const totals = React.useMemo(() => {
    if (!data) return null;
    const netPnl = data.items.reduce((acc, t) => acc + Number.parseFloat(t.net_pnl_usdt), 0);
    return { netPnl, count: data.items.length };
  }, [data]);

  return (
    <div>
      <PageHeader
        title="Islem Gecmisi"
        description="Kapanmis (sonuclanmis) islemler"
        actions={
          <Input
            placeholder="Sembol filtrele (orn. BTCUSDT)"
            value={symbol}
            onChange={(e) => {
              setSymbol(e.target.value.toUpperCase());
              setPage(1);
            }}
            className="w-56"
          />
        }
      />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="Son 24 Saat Net PnL"
          value={formatUsdt(pnlSummary?.last_24h.net_pnl_usdt)}
          tryLabel={formatTry(pnlSummary?.last_24h.net_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(pnlSummary?.last_24h.net_pnl_usdt)}
          hint={pnlSummary ? periodHint(pnlSummary.last_24h) : undefined}
          hintClassName={PERIOD_HINT_CLASS}
          icon={Clock}
        />
        <StatCard
          label="Son 7 Gun Net PnL"
          value={formatUsdt(pnlSummary?.last_7d.net_pnl_usdt)}
          tryLabel={formatTry(pnlSummary?.last_7d.net_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(pnlSummary?.last_7d.net_pnl_usdt)}
          hint={pnlSummary ? periodHint(pnlSummary.last_7d) : undefined}
          hintClassName={PERIOD_HINT_CLASS}
          icon={Calendar}
        />
        <StatCard
          label="Son 30 Gun Net PnL"
          value={formatUsdt(pnlSummary?.last_30d.net_pnl_usdt)}
          tryLabel={formatTry(pnlSummary?.last_30d.net_pnl_usdt, tryRate)}
          valueClassName={pnlColorClass(pnlSummary?.last_30d.net_pnl_usdt)}
          hint={pnlSummary ? periodHint(pnlSummary.last_30d) : undefined}
          hintClassName={PERIOD_HINT_CLASS}
          icon={CalendarDays}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Yon</TableHead>
                <TableHead>Kaldirac</TableHead>
                <TableHead>Teminat</TableHead>
                <TableHead>Giris</TableHead>
                <TableHead>Cikis</TableHead>
                <TableHead>Brut PnL</TableHead>
                <TableHead>Komisyon</TableHead>
                <TableHead>Funding</TableHead>
                <TableHead>Net PnL</TableHead>
                <TableHead>Net ROI</TableHead>
                <TableHead>Kapanis Nedeni</TableHead>
                <TableHead>Kapanis</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={13} className="py-6 text-center text-muted-foreground">
                    Kayit bulunamadi
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((trade) => (
                <TableRow key={trade.id}>
                  <TableCell className="font-medium">{trade.symbol}</TableCell>
                  <TableCell>
                    <SideBadge side={trade.side} />
                  </TableCell>
                  <TableCell>{trade.leverage}x</TableCell>
                  <TableCell>{formatUsdt(trade.margin_usdt)}</TableCell>
                  <TableCell>{formatUsdt(trade.entry_price, 4)}</TableCell>
                  <TableCell>{formatUsdt(trade.exit_price, 4)}</TableCell>
                  <TableCell className={pnlColorClass(trade.gross_pnl_usdt)}>{formatUsdt(trade.gross_pnl_usdt)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatUsdt(
                      (Number.parseFloat(trade.open_commission_usdt) + Number.parseFloat(trade.close_commission_usdt)).toString(),
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatUsdt(trade.funding_fee_usdt)}</TableCell>
                  <TableCell className={pnlColorClass(trade.net_pnl_usdt)}>{formatUsdt(trade.net_pnl_usdt)}</TableCell>
                  <TableCell className={pnlColorClass(trade.net_roi_pct)}>{formatPct(trade.net_roi_pct)}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{CLOSE_REASON_LABEL[trade.close_reason] ?? trade.close_reason}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDateTimeShort(trade.closed_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data && <PaginationBar page={data.page} totalPages={data.total_pages} total={data.total} onPageChange={setPage} />}
          {totals && (
            <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
              Bu sayfadaki {totals.count} islemin net PnL toplami:{" "}
              <span className={pnlColorClass(totals.netPnl)}>{formatUsdt(totals.netPnl.toString())}</span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
