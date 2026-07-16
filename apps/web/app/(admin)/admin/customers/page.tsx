"use client";



import * as React from "react";

import Link from "next/link";

import { useRouter, useSearchParams } from "next/navigation";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Check, Download, Eye, Loader2, Search, ShieldBan, Trash2, X } from "lucide-react";



import { platformAdminApi } from "@/lib/api";

import type { ApprovalStatus, CustomerListItemOut } from "@/types/api";

import {

  AdminEmptyState,

  AdminFilterTabs,

  AdminLinkButton,

  AdminLoading,

  AdminPageHeader,

  AdminPagination,

  AdminSectionCard,

  botStatusBadge,

} from "@/components/admin/admin-ui";

import { Badge } from "@/components/ui/badge";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { useToast } from "@/components/ui/toast-provider";
import { ApiError } from "@/lib/api-client";
import { Label } from "@/components/ui/label";



const PAGE_SIZE = 20;



function statusBadge(status: ApprovalStatus) {

  if (status === "approved") return <Badge variant="success">Onayli</Badge>;

  if (status === "blocked") return <Badge variant="destructive">Engelli</Badge>;

  return <Badge variant="warning">Onay Bekliyor</Badge>;

}



function membershipBadge(customer: CustomerListItemOut) {
  if (!customer.membership_expires_at) return <Badge variant="secondary">—</Badge>;
  if (!customer.membership_active) return <Badge variant="destructive">Suresi doldu</Badge>;
  const days = customer.membership_days_remaining ?? 0;
  if (days <= 7) return <Badge variant="warning">{days} gun kaldi</Badge>;
  return <Badge variant="success">{days} gun</Badge>;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("tr-TR");
}



function exportCustomersCsv(customers: CustomerListItemOut[]) {

  const headers = ["email", "full_name", "approval_status", "bot_mode", "bot_run_state", "open_positions", "has_binance", "last_login_at"];

  const rows = customers.map((c) =>

    [

      c.email,

      c.full_name ?? "",

      c.approval_status,

      c.bot_mode ?? "",

      c.bot_run_state ?? "",

      String(c.open_positions_count),

      c.has_binance ? "yes" : "no",

      c.last_login_at ?? "",

    ]

      .map((v) => `"${String(v).replace(/"/g, '""')}"`)

      .join(",")

  );

  const csv = [headers.join(","), ...rows].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });

  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");

  a.href = url;

  a.download = `musteriler-${new Date().toISOString().slice(0, 10)}.csv`;

  a.click();

  URL.revokeObjectURL(url);

}



export default function AdminCustomersPage() {

  return (

    <React.Suspense fallback={<AdminLoading />}>

      <CustomersContent />

    </React.Suspense>

  );

}



function CustomersContent() {

  const searchParams = useSearchParams();

  const initialStatus = (searchParams.get("status") as ApprovalStatus | null) ?? undefined;

  const [statusFilter, setStatusFilter] = React.useState<ApprovalStatus | "all">(initialStatus ?? "all");

  const [search, setSearch] = React.useState("");

  const [debouncedSearch, setDebouncedSearch] = React.useState("");

  const [page, setPage] = React.useState(1);

  const queryClient = useQueryClient();
  const { push } = useToast();
  const [deleteTarget, setDeleteTarget] = React.useState<CustomerListItemOut | null>(null);
  const [deleteConfirmEmail, setDeleteConfirmEmail] = React.useState("");



  React.useEffect(() => {

    const t = setTimeout(() => {

      setDebouncedSearch(search);

      setPage(1);

    }, 300);

    return () => clearTimeout(t);

  }, [search]);



  React.useEffect(() => {

    setPage(1);

  }, [statusFilter]);



  const { data, isLoading, refetch, isFetching } = useQuery({

    queryKey: ["platform", "customers", statusFilter, debouncedSearch, page],

    queryFn: () =>

      platformAdminApi.customers({

        approval_status: statusFilter === "all" ? undefined : statusFilter,

        search: debouncedSearch.trim() || undefined,

        page,

        page_size: PAGE_SIZE,

      }),

  });



  const { data: overview } = useQuery({

    queryKey: ["platform", "overview"],

    queryFn: platformAdminApi.overview,

  });



  const mutation = useMutation({

    mutationFn: ({ id, approval_status }: { id: string; approval_status: ApprovalStatus }) =>

      platformAdminApi.updateApproval(id, { approval_status }),

    onSuccess: () => {

      void queryClient.invalidateQueries({ queryKey: ["platform"] });

    },

  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => platformAdminApi.deleteCustomer(id),
    onSuccess: (result) => {
      push({ title: "Musteri silindi", description: result.message, variant: "success" });
      setDeleteTarget(null);
      setDeleteConfirmEmail("");
      void queryClient.invalidateQueries({ queryKey: ["platform"] });
    },
    onError: (error) => {
      push({
        title: "Musteri silinemedi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });



  const tabs: Array<{ id: ApprovalStatus | "all"; label: string; count?: number }> = [

    { id: "all", label: "Tumu", count: overview?.total_customers },

    { id: "pending", label: "Onay Bekleyen", count: overview?.pending_customers },

    { id: "approved", label: "Onayli", count: overview?.approved_customers },

    { id: "blocked", label: "Engelli", count: overview?.blocked_customers },

  ];



  const customers = Array.isArray(data) ? data : (data?.items ?? []);
  const pageInfo = Array.isArray(data)
    ? { page: 1, total_pages: 1, total: customers.length, page_size: PAGE_SIZE }
    : data
      ? { page: data.page, total_pages: data.total_pages, total: data.total, page_size: data.page_size }
      : null;



  const handleExport = async () => {

    const all = await platformAdminApi.customers({

      approval_status: statusFilter === "all" ? undefined : statusFilter,

      search: debouncedSearch.trim() || undefined,

      page: 1,

      page_size: 100,

    });

    exportCustomersCsv(all.items);

  };



  return (

    <div className="space-y-6">

      <AdminPageHeader

        title="Musteri Yonetimi"

        description="Sayfali liste, arama ve CSV disa aktarma — 100+ musteri icin optimize edildi."

        badge={<Badge variant="outline">{pageInfo?.total ?? 0} kayit</Badge>}

        breadcrumbs={[{ label: "Admin", href: "/admin" }, { label: "Musteriler" }]}

        actions={

          <>

            <Button size="sm" variant="outline" onClick={() => void handleExport()}>

              <Download className="h-4 w-4" />

              CSV Indir

            </Button>

            <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={isFetching}>

              {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}

              Yenile

            </Button>

          </>

        }

      />



      <AdminSectionCard title="Musteri Listesi" description="Satira tiklayarak detay sayfasina gidebilirsiniz." noPadding>

        <div className="space-y-0 border-b border-border/50 px-5 py-4">

          <AdminFilterTabs tabs={tabs} value={statusFilter} onChange={setStatusFilter} />

          <div className="relative mt-3 max-w-md">

            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />

            <Input

              className="border-border/70 bg-background pl-9"

              placeholder="E-posta veya ad ile ara..."

              value={search}

              onChange={(e) => setSearch(e.target.value)}

            />

          </div>

        </div>



        {isLoading ? (

          <AdminLoading label="Musteriler yukleniyor..." />

        ) : (

          <>

            <Table>

              <TableHeader>

                <TableRow className="hover:bg-transparent">

                  <TableHead>Musteri</TableHead>

                  <TableHead>Durum</TableHead>

                  <TableHead>Uyelik</TableHead>

                  <TableHead>Bot</TableHead>

                  <TableHead>Pozisyon</TableHead>

                  <TableHead>Entegrasyon</TableHead>

                  <TableHead>Son Giris</TableHead>

                  <TableHead className="text-right">Islemler</TableHead>

                </TableRow>

              </TableHeader>

              <TableBody>

                {customers.map((customer) => (

                  <CustomerRow

                    key={customer.id}

                    customer={customer}

                    busy={mutation.isPending && mutation.variables?.id === customer.id}

                    onApprove={() => mutation.mutate({ id: customer.id, approval_status: "approved" })}

                    onBlock={() => mutation.mutate({ id: customer.id, approval_status: "blocked" })}

                    onDelete={() => {
                      setDeleteTarget(customer);
                      setDeleteConfirmEmail("");
                    }}

                  />

                ))}

                {customers.length === 0 && (

                  <TableRow>

                    <TableCell colSpan={8}>

                      <AdminEmptyState title="Musteri bulunamadi" description="Filtreleri degistirmeyi deneyin." />

                    </TableCell>

                  </TableRow>

                )}

              </TableBody>

            </Table>

            {pageInfo && pageInfo.total > 0 && (

              <AdminPagination

                page={pageInfo.page}

                totalPages={pageInfo.total_pages}

                total={pageInfo.total}

                pageSize={pageInfo.page_size}

                onPageChange={setPage}

              />

            )}

          </>

        )}

      </AdminSectionCard>

      <ConfirmDialog
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteConfirmEmail("");
          }
        }}
        title="Musteriyi kalici sil"
        destructive
        confirmLabel={deleteMutation.isPending ? "Siliniyor..." : "Kalici Sil"}
        isLoading={deleteMutation.isPending}
        disabled={deleteConfirmEmail.trim().toLowerCase() !== deleteTarget?.email.toLowerCase()}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        description={
          deleteTarget ? (
            <span>
              <strong>{deleteTarget.email}</strong> hesabi ve tum verileri (pozisyon, islem, ayar, profil) geri
              alinamaz sekilde silinecek.
            </span>
          ) : null
        }
      >
        <div className="space-y-2">
          <Label htmlFor="deleteConfirmEmail">Onay icin e-posta adresini yazin</Label>
          <Input
            id="deleteConfirmEmail"
            value={deleteConfirmEmail}
            onChange={(e) => setDeleteConfirmEmail(e.target.value)}
            placeholder={deleteTarget?.email ?? ""}
            autoComplete="off"
          />
        </div>
      </ConfirmDialog>

    </div>

  );

}



function CustomerRow({

  customer,

  busy,

  onApprove,

  onBlock,

  onDelete,

}: {

  customer: CustomerListItemOut;

  busy: boolean;

  onApprove: () => void;

  onBlock: () => void;

  onDelete: () => void;

}) {

  const router = useRouter();

  const detailHref = `/admin/customers/${customer.id}`;



  return (

    <TableRow

      className="cursor-pointer"

      onClick={() => router.push(detailHref)}

      onKeyDown={(e) => {

        if (e.key === "Enter" || e.key === " ") {

          e.preventDefault();

          router.push(detailHref);

        }

      }}

      tabIndex={0}

      role="link"

      aria-label={`${customer.email} musteri detayi`}

    >

      <TableCell>

        <div className="space-y-0.5">

          <span className="font-medium text-primary">{customer.email}</span>

          <p className="text-xs text-muted-foreground">{customer.full_name || "Ad belirtilmemis"}</p>

        </div>

      </TableCell>

      <TableCell>{statusBadge(customer.approval_status)}</TableCell>

      <TableCell>
        <div className="space-y-0.5">
          {membershipBadge(customer)}
          {customer.membership_expires_at ? (
            <p className="text-[10px] text-muted-foreground">
              {new Date(customer.membership_expires_at).toLocaleDateString("tr-TR")}
            </p>
          ) : null}
        </div>
      </TableCell>

      <TableCell>

        <div className="space-y-1">

          {botStatusBadge(customer.bot_run_state, customer.bot_enabled)}

          {customer.bot_mode && (

            <p className="text-[10px] uppercase text-muted-foreground">{customer.bot_mode}</p>

          )}

        </div>

      </TableCell>

      <TableCell>

        <Badge variant={customer.open_positions_count > 0 ? "outline" : "secondary"}>

          {customer.open_positions_count} acik

        </Badge>

      </TableCell>

      <TableCell>

        <div className="flex flex-wrap gap-1">

          {customer.has_binance && <Badge variant="outline">Binance</Badge>}

          {customer.has_telegram && <Badge variant="outline">TG</Badge>}

          {!customer.has_binance && !customer.has_telegram && (

            <span className="text-xs text-muted-foreground">—</span>

          )}

        </div>

      </TableCell>

      <TableCell className="text-xs text-muted-foreground">{formatDate(customer.last_login_at)}</TableCell>

      <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>

        <div className="flex justify-end gap-1">

          <AdminLinkButton href={detailHref} size="sm" variant="ghost" className="h-8 w-8 p-0">

            <Eye className="h-4 w-4" />

          </AdminLinkButton>

          {customer.approval_status !== "approved" && (

            <Button size="sm" variant="secondary" disabled={busy} onClick={onApprove}>

              <Check className="h-4 w-4" />

            </Button>

          )}

          {customer.approval_status !== "blocked" && (

            <Button size="sm" variant="destructive" disabled={busy} onClick={onBlock}>

              <ShieldBan className="h-4 w-4" />

            </Button>

          )}

          {customer.approval_status === "blocked" && (

            <Button size="sm" variant="secondary" disabled={busy} onClick={onApprove}>

              <X className="h-4 w-4" />

            </Button>

          )}

          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={onDelete}
            title="Musteriyi kalici sil"
          >
            <Trash2 className="h-4 w-4" />
          </Button>

        </div>

      </TableCell>

    </TableRow>

  );

}


