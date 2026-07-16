"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarPlus,
  CheckCircle2,
  Loader2,
  Search,
  UserX,
  XCircle,
} from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import {
  AdminEmptyState,
  AdminFilterTabs,
  AdminLoading,
  AdminPageHeader,
  AdminPagination,
  AdminSectionCard,
  AdminStatCard,
} from "@/components/admin/admin-ui";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast-provider";
import type { CustomerListItemOut, MembershipPlanOut } from "@/types/api";

type MembershipFilter = "all" | "active" | "expiring" | "expired" | "none";

const PAGE_SIZE = 20;

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("tr-TR");
}

function membershipStatusBadge(customer: CustomerListItemOut) {
  if (!customer.membership_expires_at) return <Badge variant="secondary">Tanimlanmamis</Badge>;
  if (!customer.membership_active) return <Badge variant="destructive">Suresi doldu</Badge>;
  const days = customer.membership_days_remaining ?? 0;
  if (days <= 7) return <Badge variant="warning">{days} gun kaldi</Badge>;
  return <Badge variant="success">Aktif</Badge>;
}

function planLabel(planId: string | null, plans: MembershipPlanOut[]) {
  if (!planId) return "—";
  return plans.find((p) => p.id === planId)?.label ?? planId;
}

export default function AdminMembershipsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { push } = useToast();

  const initialFilter = (searchParams.get("filter") as MembershipFilter | null) ?? "all";
  const [filter, setFilter] = React.useState<MembershipFilter>(initialFilter);
  const [page, setPage] = React.useState(1);
  const [searchInput, setSearchInput] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [extendTarget, setExtendTarget] = React.useState<CustomerListItemOut | null>(null);
  const [extendPlanId, setExtendPlanId] = React.useState("6m");
  const [extendNote, setExtendNote] = React.useState("");

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["platform", "memberships", "overview"],
    queryFn: () => platformAdminApi.membershipOverview(),
    refetchInterval: 60_000,
  });

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["platform", "memberships", "customers", filter, page, search],
    queryFn: () =>
      platformAdminApi.customers({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        membership_filter: filter === "all" ? undefined : filter,
      }),
    refetchInterval: 60_000,
  });

  const extendMutation = useMutation({
    mutationFn: () =>
      platformAdminApi.extendMembership(extendTarget!.id, {
        membership_plan_id: extendPlanId,
        note: extendNote || null,
      }),
    onSuccess: () => {
      push({ title: "Uyelik uzatildi", variant: "success" });
      setExtendTarget(null);
      setExtendNote("");
      void queryClient.invalidateQueries({ queryKey: ["platform"] });
    },
    onError: (error) => {
      push({
        title: "Uyelik uzatilamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const applySearch = () => {
    setSearch(searchInput.trim());
    setPage(1);
  };

  const changeFilter = (next: MembershipFilter) => {
    setFilter(next);
    setPage(1);
    const params = new URLSearchParams(searchParams.toString());
    if (next === "all") params.delete("filter");
    else params.set("filter", next);
    router.replace(`/admin/memberships?${params.toString()}`);
  };

  const plans = overview?.plans ?? [];

  if (overviewLoading && !overview) {
    return <AdminLoading label="Uyelik verileri yukleniyor..." />;
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Uyelik Yonetimi"
        description="Musteri kullanim sureleri, paketler ve uzatma islemleri"
        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Uyelik Yonetimi" }]}
        actions={
          <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Yenile
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AdminStatCard
          title="Aktif Uyelik"
          value={overview?.active_count ?? 0}
          hint="Suresi devam eden musteriler"
          icon={CheckCircle2}
          tone="success"
        />
        <AdminStatCard
          title="7 Gun Icinde Bitecek"
          value={overview?.expiring_7d_count ?? 0}
          hint="Yenileme hatirlatmasi gerekenler"
          icon={AlertTriangle}
          tone="warning"
        />
        <AdminStatCard
          title="Suresi Dolmus"
          value={overview?.expired_count ?? 0}
          hint="Panele erisimi kapali musteriler"
          icon={XCircle}
          tone="danger"
        />
        <AdminStatCard
          title="Uyelik Tanimsiz"
          value={overview?.no_membership_count ?? 0}
          hint="Onay bekleyen veya sure atanmamis"
          icon={UserX}
          tone="default"
        />
      </div>

      <AdminSectionCard title="Paketler" description="Yeni onay ve uzatma islemlerinde kullanilir">
        <div className="grid gap-3 sm:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className="rounded-xl border border-border/70 bg-muted/10 px-4 py-3"
            >
              <p className="font-medium">{plan.label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{plan.price_usdt}$</p>
              <p className="mt-1 text-xs text-muted-foreground">{plan.duration_days} gun kullanim</p>
            </div>
          ))}
        </div>
      </AdminSectionCard>

      <AdminSectionCard title="Musteri Uyelikleri" description="Filtrele, arayin ve sure uzatin" noPadding contentClassName="p-0">
        <div className="space-y-4 border-b border-border/60 p-4">
          <AdminFilterTabs
            value={filter}
            onChange={changeFilter}
            tabs={[
              { id: "all" as const, label: "Tumu", count: overview?.total_customers },
              { id: "active" as const, label: "Aktif", count: overview?.active_count },
              { id: "expiring" as const, label: "Yakinda Bitecek", count: overview?.expiring_7d_count },
              { id: "expired" as const, label: "Dolmus", count: overview?.expired_count },
              { id: "none" as const, label: "Tanimsiz", count: overview?.no_membership_count },
            ]}
          />
          <div className="flex max-w-md gap-2">
            <Input
              placeholder="E-posta veya ad ara..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applySearch();
              }}
            />
            <Button type="button" variant="secondary" onClick={applySearch}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {isLoading && !data ? (
          <AdminLoading label="Musteriler yukleniyor..." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Musteri</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Paket</TableHead>
                  <TableHead>Baslangic</TableHead>
                  <TableHead>Bitis</TableHead>
                  <TableHead>Kalan</TableHead>
                  <TableHead className="text-right">Islem</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.items.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <AdminEmptyState title="Kayit bulunamadi" description="Filtreleri degistirmeyi deneyin." />
                    </TableCell>
                  </TableRow>
                )}
                {data?.items.map((customer) => (
                  <TableRow key={customer.id}>
                    <TableCell>
                      <Link href={`/admin/customers/${customer.id}`} className="font-medium text-primary hover:underline">
                        {customer.email}
                      </Link>
                      <p className="text-xs text-muted-foreground">{customer.full_name || "—"}</p>
                    </TableCell>
                    <TableCell>{membershipStatusBadge(customer)}</TableCell>
                    <TableCell className="text-sm">{planLabel(customer.membership_plan, plans)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(customer.membership_starts_at)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(customer.membership_expires_at)}</TableCell>
                    <TableCell className="text-sm tabular-nums">
                      {customer.membership_days_remaining != null ? `${customer.membership_days_remaining} gun` : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setExtendTarget(customer);
                            setExtendPlanId("6m");
                            setExtendNote("");
                          }}
                        >
                          <CalendarPlus className="h-3.5 w-3.5" />
                          Uzat
                        </Button>
                        <Button type="button" size="sm" variant="ghost" asChild>
                          <Link href={`/admin/customers/${customer.id}`}>Detay</Link>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {data && data.total > 0 && (
              <AdminPagination
                page={data.page}
                totalPages={data.total_pages}
                total={data.total}
                pageSize={data.page_size}
                onPageChange={setPage}
              />
            )}
          </>
        )}
      </AdminSectionCard>

      <ConfirmDialog
        open={extendTarget !== null}
        onOpenChange={(open) => {
          if (!open) setExtendTarget(null);
        }}
        title="Uyeligi uzat"
        description={
          extendTarget ? (
            <>
              <span className="font-medium">{extendTarget.email}</span> icin yeni sure eklenecek. Aktif uyelik varsa
              mevcut bitis tarihine eklenir.
            </>
          ) : undefined
        }
        confirmLabel="Uzat"
        isLoading={extendMutation.isPending}
        onConfirm={() => extendMutation.mutate()}
      >
        <div className="space-y-3 py-2">
          <div className="space-y-1.5">
            <Label>Paket</Label>
            <Select value={extendPlanId} onValueChange={setExtendPlanId}>
              <SelectTrigger>
                <SelectValue placeholder="Paket secin" />
              </SelectTrigger>
              <SelectContent>
                {plans.map((plan) => (
                  <SelectItem key={plan.id} value={plan.id}>
                    {plan.label} ({plan.price_usdt}$ / {plan.duration_days} gun)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Not (opsiyonel)</Label>
            <Input
              value={extendNote}
              onChange={(e) => setExtendNote(e.target.value)}
              placeholder="Orn. 100$ havale alindi"
            />
          </div>
        </div>
      </ConfirmDialog>
    </div>
  );
}
