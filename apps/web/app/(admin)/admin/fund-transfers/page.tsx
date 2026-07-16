"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, RefreshCw, Send, ShieldCheck, Wallet } from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatCard,
} from "@/components/admin/admin-ui";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast-provider";
import type { FundTransferHistoryOut, WithdrawableCustomerOut } from "@/types/api";
import { formatUsdt } from "@/lib/utils";

function truncateAddress(value: string) {
  if (value.length <= 16) return value;
  return `${value.slice(0, 8)}...${value.slice(-8)}`;
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("tr-TR");
}

function eligibilityBadge(row: WithdrawableCustomerOut) {
  if (row.eligible) {
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 className="h-3 w-3" />
        Uygun
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="max-w-[220px] truncate" title={row.ineligible_reason ?? undefined}>
      {row.ineligible_reason ?? "Uygun degil"}
    </Badge>
  );
}

export default function AdminFundTransfersPage() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [transferTarget, setTransferTarget] = React.useState<WithdrawableCustomerOut | null>(null);

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["platform", "fund-transfers", "eligible"],
    queryFn: () => platformAdminApi.fundTransfersEligible(),
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["platform", "fund-transfers", "history"],
    queryFn: () => platformAdminApi.fundTransferHistory(50),
  });

  const transferMutation = useMutation({
    mutationFn: (customerId: string) => platformAdminApi.fundTransferExecute(customerId),
    onSuccess: (result) => {
      push({
        title: "TRC20 transferi baslatildi",
        description: `${formatUsdt(result.amount_usdt)} USDT — ${result.message}`,
        variant: "success",
      });
      setTransferTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["platform", "fund-transfers"] });
    },
    onError: (error) => {
      push({
        title: "Transfer basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const eligibleRows = data?.filter((row) => row.eligible) ?? [];
  const destination = data?.[0]?.destination_address ?? "—";
  const network = data?.[0]?.network ?? "TRX";
  const totalEstimated = eligibleRows.reduce((sum, row) => sum + Number(row.estimated_withdraw_usdt || 0), 0);

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="TRC20 Fon Toplama"
        description="IP izinli ve withdraw acik live musterilerin bakiyelerini admin TRC20 cuzdanina transfer edin."
        actions={
          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Yenile
          </Button>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <AdminStatCard
          title="Uygun musteri"
          value={String(eligibleRows.length)}
          icon={ShieldCheck}
          hint="IP kisitli + withdraw izinli"
        />
        <AdminStatCard
          title="Tahmini toplam"
          value={`${formatUsdt(String(totalEstimated))} USDT`}
          icon={Wallet}
          hint="Ucretler dusulmus"
        />
        <AdminStatCard
          title="Hedef cuzdan"
          value={truncateAddress(destination)}
          icon={Send}
          hint={`${network} (TRC20)`}
        />
      </div>

      <AdminSectionCard
        title="Transfer edilebilir musteriler"
        description="Yalnizca live mod, IP izinli API anahtari, withdraw izni ve acik pozisyonu olmayan musteriler listelenir."
      >
        {isLoading ? (
          <AdminLoading />
        ) : !data?.length ? (
          <AdminEmptyState
            title="Uygun musteri yok"
            description="Live mod + Binance API + IP izinli anahtar gereklidir."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Musteri</TableHead>
                  <TableHead>IP izin</TableHead>
                  <TableHead>Withdraw</TableHead>
                  <TableHead>Futures</TableHead>
                  <TableHead>Spot USDT</TableHead>
                  <TableHead>Tahmini cekim</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead className="text-right">Islem</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((row) => (
                  <TableRow key={row.customer_id}>
                    <TableCell>
                      <div className="min-w-[160px]">
                        <p className="font-medium">{row.email}</p>
                        {row.full_name ? <p className="text-xs text-muted-foreground">{row.full_name}</p> : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      {row.ip_restrict ? (
                        <Badge variant="success">Evet</Badge>
                      ) : (
                        <Badge variant="destructive">Hayir</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {row.withdraw_enabled ? (
                        <Badge variant="success">Acik</Badge>
                      ) : (
                        <Badge variant="secondary">Kapali</Badge>
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums">{formatUsdt(row.futures_available_usdt)}</TableCell>
                    <TableCell className="tabular-nums">{formatUsdt(row.spot_usdt_balance)}</TableCell>
                    <TableCell className="tabular-nums font-medium">{formatUsdt(row.estimated_withdraw_usdt)}</TableCell>
                    <TableCell>{eligibilityBadge(row)}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        disabled={!row.eligible || transferMutation.isPending}
                        onClick={() => setTransferTarget(row)}
                      >
                        <Send className="mr-1.5 h-3.5 w-3.5" />
                        Transfer
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </AdminSectionCard>

      <AdminSectionCard title="Transfer gecmisi" description="Son TRC20 cekim kayitlari">
        {historyLoading ? (
          <AdminLoading />
        ) : !history?.length ? (
          <AdminEmptyState title="Henuz transfer yok" />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tarih</TableHead>
                  <TableHead>Musteri</TableHead>
                  <TableHead>Tutar</TableHead>
                  <TableHead>Ag</TableHead>
                  <TableHead>Binance ID</TableHead>
                  <TableHead>Durum</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((row: FundTransferHistoryOut) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap text-xs">{formatDateTime(row.created_at)}</TableCell>
                    <TableCell>{row.customer_email ?? row.customer_id}</TableCell>
                    <TableCell className="tabular-nums font-medium">{formatUsdt(row.amount_usdt)}</TableCell>
                    <TableCell>{row.network}</TableCell>
                    <TableCell className="font-mono text-xs">{row.binance_withdraw_id ?? "—"}</TableCell>
                    <TableCell>
                      {row.status === "success" ? (
                        <Badge variant="success">Basarili</Badge>
                      ) : row.status === "failed" ? (
                        <Badge variant="destructive" title={row.error_message ?? undefined}>
                          Basarisiz
                        </Badge>
                      ) : (
                        <Badge variant="secondary">{row.status}</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </AdminSectionCard>

      <ConfirmDialog
        open={transferTarget != null}
        onOpenChange={(open) => !open && setTransferTarget(null)}
        title="TRC20 transferi onayla"
        description={
          transferTarget ? (
            <div className="space-y-2 text-sm">
              <p>
                <strong>{transferTarget.email}</strong> hesabindan tahmini{" "}
                <strong>{formatUsdt(transferTarget.estimated_withdraw_usdt)} USDT</strong> cekilecek.
              </p>
              <p>
                Hedef: <span className="font-mono text-xs">{transferTarget.destination_address}</span>
              </p>
              <p className="text-muted-foreground">
                Futures bakiyesi once spot&apos;a aktarilir, ardindan TRC20 aginda admin cuzdanina gonderilir. Acik pozisyon
                olmamali ve API anahtarinda withdraw + IP izni acik olmalidir.
              </p>
            </div>
          ) : null
        }
        confirmLabel={transferMutation.isPending ? "Gonderiliyor..." : "Transferi baslat"}
        isLoading={transferMutation.isPending}
        onConfirm={() => {
          if (transferTarget) transferMutation.mutate(transferTarget.customer_id);
        }}
      />
    </div>
  );
}
