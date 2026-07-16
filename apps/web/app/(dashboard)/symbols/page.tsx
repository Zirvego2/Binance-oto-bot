"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { symbolsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useCurrentAdmin } from "@/hooks/use-auth";
import { formatNumber, formatPct, formatUsdt } from "@/lib/utils";
import type { SymbolOut } from "@/types/api";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast-provider";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function SymbolsPage() {
  const [search, setSearch] = React.useState("");
  const { push } = useToast();
  const queryClient = useQueryClient();
  const { data: admin } = useCurrentAdmin();

  const { data, isLoading } = useQuery({
    queryKey: ["symbols", admin?.id],
    queryFn: symbolsApi.list,
    enabled: Boolean(admin?.id),
    refetchInterval: 30_000,
  });

  const updateMutation = useMutation({
    mutationFn: ({ symbol, payload }: { symbol: string; payload: Partial<SymbolOut> }) =>
      symbolsApi.update(symbol, payload),
    onMutate: async ({ symbol, payload }) => {
      await queryClient.cancelQueries({ queryKey: ["symbols", admin?.id] });
      const previous = queryClient.getQueryData<SymbolOut[]>(["symbols", admin?.id]);
      queryClient.setQueryData<SymbolOut[]>(["symbols", admin?.id], (old) =>
        old?.map((s) => (s.symbol === symbol ? { ...s, ...payload } : s))
      );
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(["symbols", admin?.id], context.previous);
      push({ title: "Guncelleme basarisiz", description: error instanceof ApiError ? error.message : undefined, variant: "error" });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["symbols", admin?.id] }),
  });

  const filtered = (data ?? []).filter((s) => s.symbol.includes(search.toUpperCase()));

  return (
    <div>
      <PageHeader
        title="Semboller"
        description="Analiz edilen USDT-M sembolleri; kara liste ve LONG/SHORT izinlerini buradan yonetin"
        actions={<Input placeholder="Sembol ara..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-56" />}
      />

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sembol</TableHead>
                <TableHead>Son Fiyat</TableHead>
                <TableHead>24s Hacim</TableHead>
                <TableHead>Funding</TableHead>
                <TableHead>Spread</TableHead>
                <TableHead>Min. Teminat (3x)</TableHead>
                <TableHead>LONG</TableHead>
                <TableHead>SHORT</TableHead>
                <TableHead>Kara Liste</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {!isLoading && filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                    Kayit bulunamadi. Worker servisi calisip exchangeInfo senkronize ettiginde semboller burada gorunecektir.
                  </TableCell>
                </TableRow>
              )}
              {filtered.map((symbol) => (
                <TableRow key={symbol.symbol}>
                  <TableCell className="font-medium">
                    {symbol.symbol}
                    {symbol.is_blacklisted && (
                      <Badge variant="destructive" className="ml-2">
                        Yasakli
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{symbol.last_price ? formatUsdt(symbol.last_price, 4) : "-"}</TableCell>
                  <TableCell>{symbol.volume_24h_usdt ? formatUsdt(symbol.volume_24h_usdt, 0) : "-"}</TableCell>
                  <TableCell>{symbol.funding_rate ? formatPct(symbol.funding_rate, 4) : "-"}</TableCell>
                  <TableCell>{symbol.spread_pct ? formatPct(symbol.spread_pct, 3) : "-"}</TableCell>
                  <TableCell>{symbol.required_min_margin_at_3x ? formatUsdt(symbol.required_min_margin_at_3x) : "-"}</TableCell>
                  <TableCell>
                    <Switch
                      checked={symbol.long_enabled}
                      onCheckedChange={(checked) => updateMutation.mutate({ symbol: symbol.symbol, payload: { long_enabled: checked } })}
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={symbol.short_enabled}
                      onCheckedChange={(checked) => updateMutation.mutate({ symbol: symbol.symbol, payload: { short_enabled: checked } })}
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={symbol.is_blacklisted}
                      onCheckedChange={(checked) => updateMutation.mutate({ symbol: symbol.symbol, payload: { is_blacklisted: checked } })}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="mt-2 text-xs text-muted-foreground">
        Toplam {formatNumber(filtered.length, 0)} sembol goruntuleniyor.
      </p>
    </div>
  );
}
