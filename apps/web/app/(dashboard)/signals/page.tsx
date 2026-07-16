"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { signalsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { formatDateTimeShort, formatNumber } from "@/lib/utils";
import type { SignalEntryMode, StrategySignalOut } from "@/types/api";
import { PageHeader } from "@/components/shared/page-header";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { SideBadge, StatusBadge } from "@/components/shared/side-badge";
import { useToast } from "@/components/ui/toast-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const DECISION_VARIANT: Record<string, "success" | "destructive" | "secondary" | "outline"> = {
  ISLEM_AC: "success",
  AC: "success",
  BEKLE: "outline",
  RED: "destructive",
  REDDEDILDI: "destructive",
  RISK_NEDENIYLE_ATLANDI: "secondary",
};

const ENTRY_MODE_LABEL: Record<SignalEntryMode, string> = {
  market: "Piyasa (hemen)",
  limit: "Olta (limit)",
  settings: "Bot ayari",
};

export default function SignalsPage() {
  const [symbol, setSymbol] = React.useState("");
  const [entryMode, setEntryMode] = React.useState<SignalEntryMode>("market");
  const [executeTarget, setExecuteTarget] = React.useState<StrategySignalOut | null>(null);
  const { push } = useToast();
  const queryClient = useQueryClient();

  const { data: signals } = useQuery({
    queryKey: ["signals", symbol],
    queryFn: () => signalsApi.list({ symbol: symbol || undefined, limit: 100 }),
    refetchInterval: 15_000,
  });

  const { data: analysis } = useQuery({
    queryKey: ["signals", "analysis", symbol],
    queryFn: () => signalsApi.analysis({ symbol: symbol || undefined, limit: 100 }),
    refetchInterval: 15_000,
  });

  const executeMutation = useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: SignalEntryMode }) => signalsApi.execute(id, mode),
    onSuccess: (result) => {
      push({
        title: result.status === "opened" ? "Pozisyon acildi" : "Olta emri gonderildi",
        description: result.message ?? undefined,
        variant: "success",
      });
      setExecuteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["signals"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      push({
        title: "Islem acilamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  return (
    <div>
      <PageHeader
        title="Sinyaller & Analiz"
        description="Platform geneli ortak sinyaller ve teknik analiz sonuclari"
        actions={
          <div className="flex items-center gap-2">
            <Select value={entryMode} onValueChange={(v) => setEntryMode(v as SignalEntryMode)}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Giris modu" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="market">Piyasa (hemen)</SelectItem>
                <SelectItem value="limit">Olta (limit)</SelectItem>
                <SelectItem value="settings">Bot ayari</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Sembol filtrele (orn. BTCUSDT)"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-56"
            />
          </div>
        }
      />

      <Tabs defaultValue="signals">
        <TabsList>
          <TabsTrigger value="signals">Sinyaller</TabsTrigger>
          <TabsTrigger value="analysis">Analiz Detaylari</TabsTrigger>
        </TabsList>

        <TabsContent value="signals">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sembol</TableHead>
                    <TableHead>Yon</TableHead>
                    <TableHead>Toplam Skor</TableHead>
                    <TableHead>Kullanildi mi?</TableHead>
                    <TableHead>Mod</TableHead>
                    <TableHead>Zaman</TableHead>
                    <TableHead className="text-right">Islem</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(signals?.length ?? 0) === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="py-6 text-center text-muted-foreground">
                        Kayit bulunamadi
                      </TableCell>
                    </TableRow>
                  )}
                  {signals?.map((signal) => (
                    <TableRow key={signal.id}>
                      <TableCell className="font-medium">{signal.symbol}</TableCell>
                      <TableCell>
                        <SideBadge side={signal.side} />
                      </TableCell>
                      <TableCell>{formatNumber(signal.total_score, 1)}</TableCell>
                      <TableCell>
                        <StatusBadge status={signal.consumed ? "FILLED" : "NEW"} />
                      </TableCell>
                      <TableCell className="text-xs uppercase text-muted-foreground">{signal.bot_mode}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatDateTimeShort(signal.created_at)}</TableCell>
                      <TableCell className="text-right">
                        {signal.consumed ? (
                          <span className="text-xs text-muted-foreground">—</span>
                        ) : (
                          <Button size="sm" variant="default" onClick={() => setExecuteTarget(signal)}>
                            Al
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analysis">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sembol</TableHead>
                    <TableHead>Onerilen Yon</TableHead>
                    <TableHead>Karar</TableHead>
                    <TableHead>EMA (H/O/D)</TableHead>
                    <TableHead>RSI</TableHead>
                    <TableHead>ATR</TableHead>
                    <TableHead>Toplam Skor</TableHead>
                    <TableHead>Neden</TableHead>
                    <TableHead>Zaman</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(analysis?.length ?? 0) === 0 && (
                    <TableRow>
                      <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                        Kayit bulunamadi
                      </TableCell>
                    </TableRow>
                  )}
                  {analysis?.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="font-medium">{row.symbol}</TableCell>
                      <TableCell>
                        <SideBadge side={row.suggested_side} />
                      </TableCell>
                      <TableCell>
                        <Badge variant={DECISION_VARIANT[row.decision] ?? "outline"}>{row.decision}</Badge>
                      </TableCell>
                      <TableCell className="text-xs">
                        {formatNumber(row.ema_fast, 2)} / {formatNumber(row.ema_mid, 2)} / {formatNumber(row.ema_slow, 2)}
                      </TableCell>
                      <TableCell>{formatNumber(row.rsi_value, 1)}</TableCell>
                      <TableCell>{formatNumber(row.atr_value, 4)}</TableCell>
                      <TableCell className="font-medium">{formatNumber(row.total_score, 1)}</TableCell>
                      <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground" title={row.reason}>
                        {row.reason}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatDateTimeShort(row.analyzed_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={executeTarget !== null}
        onOpenChange={(open) => !open && setExecuteTarget(null)}
        title="Sinyali manuel al"
        description={
          executeTarget
            ? `${executeTarget.symbol} ${executeTarget.side} sinyalini ${ENTRY_MODE_LABEL[entryMode].toLowerCase()} modunda acmak istediginize emin misiniz?`
            : undefined
        }
        confirmLabel="Al"
        isLoading={executeMutation.isPending}
        onConfirm={() =>
          executeTarget && executeMutation.mutate({ id: executeTarget.id, mode: entryMode })
        }
      />
    </div>
  );
}
