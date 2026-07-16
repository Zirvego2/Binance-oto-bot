"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";

import { binanceApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { formatDateTime, formatUsdt } from "@/lib/utils";
import { PageHeader } from "@/components/shared/page-header";
import { SideBadge } from "@/components/shared/side-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast-provider";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function CheckRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-2 text-sm last:border-0">
      <span className="text-muted-foreground">{label}</span>
      {ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-destructive" />}
    </div>
  );
}

export default function BinancePage() {
  const { push } = useToast();
  const queryClient = useQueryClient();

  const { data: status } = useQuery({ queryKey: ["binance", "status"], queryFn: binanceApi.status });
  const { data: account } = useQuery({ queryKey: ["binance", "account"], queryFn: binanceApi.account });
  const { data: positions } = useQuery({ queryKey: ["binance", "positions"], queryFn: binanceApi.positions });
  const { data: openOrders } = useQuery({ queryKey: ["binance", "open-orders"], queryFn: binanceApi.openAlgoOrders });

  const testMutation = useMutation({
    mutationFn: binanceApi.testConnection,
    onSuccess: () => {
      push({ title: "Baglanti testi tamamlandi", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["binance"] });
    },
    onError: (error) =>
      push({ title: "Baglanti testi basarisiz", description: error instanceof ApiError ? error.message : undefined, variant: "error" }),
  });

  const reconcileMutation = useMutation({
    mutationFn: binanceApi.reconcile,
    onSuccess: (run) =>
      push({
        title: "Reconciliation tamamlandi",
        description: `${run.mismatches_found} tutarsizlik bulundu`,
        variant: run.mismatches_found > 0 ? "info" : "success",
      }),
    onError: (error) =>
      push({ title: "Reconciliation basarisiz", description: error instanceof ApiError ? error.message : undefined, variant: "error" }),
  });

  const isPaper = status?.environment === "paper";

  return (
    <div>
      <PageHeader
        title="Binance Baglantisi"
        description="Binance USDS-M Futures API baglanti durumu ve hesap bilgileri"
        actions={
          <div className="flex gap-2">
            {!isPaper && (
              <Button variant="outline" size="sm" onClick={() => reconcileMutation.mutate()} disabled={reconcileMutation.isPending}>
                {reconcileMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Reconciliation Calistir
              </Button>
            )}
            <Button size="sm" onClick={() => testMutation.mutate()} disabled={testMutation.isPending || isPaper}>
              {testMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Baglantiyi Test Et
            </Button>
          </div>
        }
      />

      {isPaper && (
        <div className="mb-4 rounded-md border border-border bg-card/40 px-3 py-2 text-sm text-muted-foreground">
          Sistem su anda <strong>PAPER</strong> modunda calisiyor. Gercek Binance API baglantisi kullanilmiyor; tum
          hesap/pozisyon verileri veritabaninda simule edilen sanal islem verileridir.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Baglanti Kontrolleri ({status?.environment?.toUpperCase()})</CardTitle>
          </CardHeader>
          <CardContent>
            <CheckRow label="API bilgileri tanimli" ok={!!status?.is_configured} />
            <CheckRow label="Baglanti kuruldu" ok={!!status?.is_connected} />
            <CheckRow label="Hesap erisimi" ok={!!status?.account_access_ok} />
            <CheckRow label="Futures hesabi kullanilabilir" ok={!!status?.futures_account_usable} />
            <CheckRow label="Islem (trading) izni" ok={!!status?.trading_permission_ok} />
            <CheckRow label="ONE_WAY position mode" ok={!!status?.position_mode_verified} />
            <CheckRow label="Multi-Assets Mode kapali" ok={!!status?.multi_assets_mode_off_verified} />
            {status?.last_error_message && (
              <p className="mt-2 rounded-md bg-destructive/10 px-2 py-1.5 text-xs text-destructive">{status.last_error_message}</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">Son basarili: {formatDateTime(status?.last_success_at)}</p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Hesap Ozeti</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <SummaryStat label="Toplam Bakiye" value={formatUsdt(account?.total_wallet_balance)} />
            <SummaryStat label="Kullanilabilir" value={formatUsdt(account?.available_balance)} />
            <SummaryStat label="Teminat Bakiyesi" value={formatUsdt(account?.total_margin_balance)} />
            <SummaryStat label="Gerceklesmeyen PnL" value={formatUsdt(account?.total_unrealized_pnl)} />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Borsadaki Acik Pozisyonlar</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Yon</TableHead>
                <TableHead>Miktar</TableHead>
                <TableHead>Giris</TableHead>
                <TableHead>Mark</TableHead>
                <TableHead>PnL</TableHead>
                <TableHead>Kaldirac</TableHead>
                <TableHead>Likidasyon</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(positions?.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="py-6 text-center text-muted-foreground">
                    Acik pozisyon yok
                  </TableCell>
                </TableRow>
              )}
              {positions?.map((p) => (
                <TableRow key={p.symbol}>
                  <TableCell className="font-medium">{p.symbol}</TableCell>
                  <TableCell>
                    <SideBadge side={p.position_side} />
                  </TableCell>
                  <TableCell>{p.quantity}</TableCell>
                  <TableCell>{formatUsdt(p.entry_price, 4)}</TableCell>
                  <TableCell>{formatUsdt(p.mark_price, 4)}</TableCell>
                  <TableCell>{formatUsdt(p.unrealized_pnl)}</TableCell>
                  <TableCell>{p.leverage}x</TableCell>
                  <TableCell>{formatUsdt(p.liquidation_price, 4)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Acik Algo Emirleri (SL/TP)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Tur</TableHead>
                <TableHead>Taraf</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Emir ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(openOrders?.length ?? 0) === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                    Acik algo emri yok
                  </TableCell>
                </TableRow>
              )}
              {openOrders?.map((o) => (
                <TableRow key={o.binance_order_id}>
                  <TableCell className="font-medium">{o.symbol}</TableCell>
                  <TableCell>{o.order_type}</TableCell>
                  <TableCell>{o.side}</TableCell>
                  <TableCell>{o.status}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{o.binance_order_id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}
