"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { ordersApi } from "@/lib/api";
import { formatDateTimeShort, formatUsdt } from "@/lib/utils";
import { PageHeader } from "@/components/shared/page-header";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { SideBadge, StatusBadge } from "@/components/shared/side-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const PURPOSE_LABELS: Record<string, string> = {
  OPEN: "Acis",
  CLOSE: "Kapanis",
  MANUAL_CLOSE: "Manuel Kapat",
  EMERGENCY_CLOSE: "Acil Kapat",
};

export default function OrdersPage() {
  const [page, setPage] = React.useState(1);
  const [symbol, setSymbol] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("ALL");

  const hasPending = statusFilter === "PENDING" || statusFilter === "ALL";

  const { data, isLoading } = useQuery({
    queryKey: ["orders", page, symbol, statusFilter],
    queryFn: () =>
      ordersApi.list({
        page,
        page_size: 25,
        symbol: symbol || undefined,
        status_filter: statusFilter === "ALL" ? undefined : statusFilter,
      }),
    refetchInterval: hasPending ? 3_000 : 15_000,
  });

  return (
    <div>
      <PageHeader
        title="Emirler"
        description="Piyasa emirlerinin canli listesi — bekleyen emirler her 3 saniyede guncellenir"
        actions={
          <div className="flex items-center gap-2">
            <Input
              placeholder="Sembol (orn. BTCUSDT)"
              value={symbol}
              onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setPage(1); }}
              className="w-44"
            />
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">Tumu</SelectItem>
                <SelectItem value="PENDING">Bekleyen</SelectItem>
                <SelectItem value="FILLED">Doldu</SelectItem>
                <SelectItem value="CANCELED">Iptal</SelectItem>
                <SelectItem value="FAILED">Basarisiz</SelectItem>
              </SelectContent>
            </Select>
          </div>
        }
      />

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Yon</TableHead>
                <TableHead>Tur</TableHead>
                <TableHead>Amac</TableHead>
                <TableHead>Miktar</TableHead>
                <TableHead>Ort. Dolum Fiyati</TableHead>
                <TableHead>Komisyon</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Mod</TableHead>
                <TableHead>Olusturma</TableHead>
                <TableHead>Dolum</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={11} className="py-6 text-center text-muted-foreground">
                    Kayit bulunamadi
                  </TableCell>
                </TableRow>
              )}
              {data?.items.map((order) => (
                <TableRow
                  key={order.id}
                  className={order.status === "PENDING" ? "animate-pulse bg-yellow-500/5" : undefined}
                >
                  <TableCell className="font-medium">{order.symbol}</TableCell>
                  <TableCell>
                    <SideBadge side={order.side === "BUY" ? "LONG" : order.side === "SELL" ? "SHORT" : null} />
                  </TableCell>
                  <TableCell className="text-xs">{order.order_type}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {PURPOSE_LABELS[order.purpose] ?? order.purpose}
                  </TableCell>
                  <TableCell>{formatUsdt(order.filled_quantity, 4).replace(" USDT", "")}</TableCell>
                  <TableCell>{order.avg_fill_price ? formatUsdt(order.avg_fill_price, 4) : "-"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {order.commission_usdt ? formatUsdt(order.commission_usdt, 4) : "-"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={order.status} />
                  </TableCell>
                  <TableCell className="text-xs uppercase text-muted-foreground">{order.bot_mode}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDateTimeShort(order.created_at)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {order.filled_at ? formatDateTimeShort(order.filled_at) : "-"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data && (
            <PaginationBar
              page={data.page}
              totalPages={data.total_pages}
              total={data.total}
              onPageChange={setPage}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
