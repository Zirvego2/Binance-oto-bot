"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Loader2, ShieldBan, CalendarPlus, Trash2 } from "lucide-react";

import { platformAdminApi } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";
import { ApiError } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import {
  AdminInfoRow,
  AdminLinkButton,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  botStatusBadge,
} from "@/components/admin/admin-ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("tr-TR");
}

function statusBadge(status: string) {
  if (status === "approved") return <Badge variant="success">Onayli</Badge>;
  if (status === "blocked") return <Badge variant="destructive">Engelli</Badge>;
  return <Badge variant="warning">Onay Bekliyor</Badge>;
}

function membershipStatusBadge(active: boolean, daysRemaining: number | null) {
  if (!active) return <Badge variant="destructive">Suresi doldu</Badge>;
  if (daysRemaining != null && daysRemaining <= 7) return <Badge variant="warning">{daysRemaining} gun kaldi</Badge>;
  return <Badge variant="success">Aktif</Badge>;
}

export default function AdminCustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = params.id;
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [notes, setNotes] = React.useState("");
  const [blockedReason, setBlockedReason] = React.useState("");
  const [approvalPlanId, setApprovalPlanId] = React.useState("6m");
  const [extendPlanId, setExtendPlanId] = React.useState("6m");
  const [extendNote, setExtendNote] = React.useState("");
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [deleteConfirmEmail, setDeleteConfirmEmail] = React.useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["platform", "customer", customerId],
    queryFn: () => platformAdminApi.customer(customerId),
    enabled: Boolean(customerId),
  });

  const { data: membershipPlans } = useQuery({
    queryKey: ["platform", "membership-plans"],
    queryFn: () => platformAdminApi.membershipPlans(),
  });

  React.useEffect(() => {
    if (data) {
      setNotes(data.notes ?? "");
      setBlockedReason(data.blocked_reason ?? "");
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: {
      approval_status: string;
      blocked_reason?: string | null;
      notes?: string | null;
      is_active?: boolean | null;
      membership_plan_id?: string | null;
    }) => platformAdminApi.updateApproval(customerId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform"] });
    },
  });

  const extendMutation = useMutation({
    mutationFn: () =>
      platformAdminApi.extendMembership(customerId, {
        membership_plan_id: extendPlanId,
        note: extendNote || null,
      }),
    onSuccess: () => {
      push({ title: "Uyelik uzatildi", variant: "success" });
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

  const deleteMutation = useMutation({
    mutationFn: () => platformAdminApi.deleteCustomer(customerId),
    onSuccess: (result) => {
      push({ title: "Musteri silindi", description: result.message, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["platform"] });
      router.replace("/admin/customers");
    },
    onError: (error) => {
      push({
        title: "Musteri silinemedi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  if (isLoading || !data) {
    return <AdminLoading />;
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title={data.full_name?.trim() || data.email}
        description={data.email}
        badge={statusBadge(data.approval_status)}
        breadcrumbs={[
          { label: "Admin", href: "/admin" },
          { label: "Musteriler", href: "/admin/customers" },
          { label: data.email },
        ]}
        actions={
          <AdminLinkButton href="/admin/customers" size="sm" variant="outline">
            <ArrowLeft className="h-4 w-4" />
            Listeye Don
          </AdminLinkButton>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <AdminSectionCard title="Uyelik" description="Kullanim suresi ve paket bilgisi">
          <AdminInfoRow
            label="Durum"
            value={membershipStatusBadge(data.membership_active, data.membership_days_remaining)}
          />
          <AdminInfoRow label="Paket" value={data.membership_plan || "—"} />
          <AdminInfoRow label="Baslangic" value={formatDate(data.membership_starts_at)} />
          <AdminInfoRow label="Bitis" value={formatDate(data.membership_expires_at)} />
          <AdminInfoRow
            label="Kalan Gun"
            value={data.membership_days_remaining != null ? String(data.membership_days_remaining) : "—"}
          />
        </AdminSectionCard>

        <AdminSectionCard title="Operasyon Durumu" description="Bot ve pozisyon ozeti">
          <AdminInfoRow label="Bot Durumu" value={botStatusBadge(data.bot_run_state, data.bot_enabled)} />
          <AdminInfoRow label="Calisma Modu" value={(data.bot_mode ?? "—").toUpperCase()} />
          <AdminInfoRow label="Acik Pozisyon" value={String(data.open_positions_count)} />
          <AdminInfoRow
            label="Oturum"
            value={data.is_online ? <Badge variant="success">Cevrimici</Badge> : <Badge variant="secondary">Offline</Badge>}
          />
        </AdminSectionCard>

        <AdminSectionCard title="Hesap Bilgileri" description="Kimlik ve oturum detaylari">
          <AdminInfoRow label="Telefon" value={data.phone || "—"} />
          <AdminInfoRow label="Il / Ilce" value={`${data.city || "—"} / ${data.district || "—"}`} />
          <AdminInfoRow label="Durum" value={statusBadge(data.approval_status)} />
          <AdminInfoRow label="Hesap Aktif" value={data.is_active ? "Evet" : "Hayir"} />
          <AdminInfoRow label="Plan" value={data.plan || "starter"} />
          <AdminInfoRow label="Kayit Tarihi" value={formatDate(data.created_at)} />
          <AdminInfoRow label="Onay Tarihi" value={formatDate(data.approved_at)} />
          <AdminInfoRow label="Son Giris" value={formatDate(data.last_login_at)} />
          <AdminInfoRow label="Son IP" value={data.last_login_ip || "—"} />
          <AdminInfoRow label="Firebase UID" value={<span className="font-mono text-xs">{data.firebase_uid || "—"}</span>} />
          <AdminInfoRow label="Aktif Oturum Sayisi" value={String(data.active_session_count)} />
        </AdminSectionCard>

        <AdminSectionCard title="Entegrasyonlar" description="API baglantilari ve senkronizasyon">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant={data.has_binance ? "success" : "secondary"}>Binance {data.has_binance ? "Bagli" : "Yok"}</Badge>
              <Badge variant={data.has_telegram ? "success" : "secondary"}>Telegram {data.has_telegram ? "Bagli" : "Yok"}</Badge>
              <Badge variant={data.has_openai ? "success" : "secondary"}>OpenAI {data.has_openai ? "Bagli" : "Yok"}</Badge>
            </div>
            <div className="rounded-lg border border-border/60 bg-muted/15 px-3 py-2.5 text-xs text-muted-foreground">
              Firestore:{" "}
              <span className="font-medium text-foreground">{data.firestore_synced ? "Senkronize" : "Bekliyor"}</span>
              {data.migration_mode ? ` · Mod: ${data.migration_mode}` : ""}
            </div>
          </div>
        </AdminSectionCard>
      </div>

      <AdminSectionCard title="Uyelik Uzat" description="Yeni odeme sonrasi sure ekleyin">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Paket</Label>
            <Select value={extendPlanId} onValueChange={setExtendPlanId}>
              <SelectTrigger>
                <SelectValue placeholder="Paket secin" />
              </SelectTrigger>
              <SelectContent>
                {(membershipPlans ?? []).map((plan) => (
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
        <div className="mt-4 border-t border-border/50 pt-4">
          <Button disabled={extendMutation.isPending} onClick={() => extendMutation.mutate()}>
            {extendMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarPlus className="h-4 w-4" />}
            Uyeligi Uzat
          </Button>
        </div>
      </AdminSectionCard>

      <AdminSectionCard title="Yonetici Islemleri" description="Onay, engelleme ve ic notlar">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Onay Paketi</Label>
            <Select value={approvalPlanId} onValueChange={setApprovalPlanId}>
              <SelectTrigger>
                <SelectValue placeholder="Paket secin" />
              </SelectTrigger>
              <SelectContent>
                {(membershipPlans ?? []).map((plan) => (
                  <SelectItem key={plan.id} value={plan.id}>
                    {plan.label} ({plan.price_usdt}$)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="notes">Ic Not</Label>
            <Input id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Yalnizca yoneticiler gorur..." />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="blockedReason">Engelleme Nedeni</Label>
            <Input
              id="blockedReason"
              value={blockedReason}
              onChange={(e) => setBlockedReason(e.target.value)}
              placeholder="Engellenirse musteriye gosterilir"
            />
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-border/50 pt-5">
          <Button
            disabled={mutation.isPending}
            onClick={() =>
              mutation.mutate({
                approval_status: "approved",
                notes: notes || null,
                blocked_reason: null,
                membership_plan_id: approvalPlanId,
              })
            }
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Hesabi Onayla
          </Button>
          <Button
            variant="destructive"
            disabled={mutation.isPending}
            onClick={() =>
              mutation.mutate({
                approval_status: "blocked",
                notes: notes || null,
                blocked_reason: blockedReason || "Hesap yonetici tarafindan engellendi.",
                is_active: false,
              })
            }
          >
            <ShieldBan className="h-4 w-4" />
            Engelle
          </Button>
          <Button
            variant="outline"
            disabled={mutation.isPending}
            onClick={() =>
              mutation.mutate({
                approval_status: "pending",
                notes: notes || null,
                blocked_reason: null,
              })
            }
          >
            Onayi Geri Al
          </Button>
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="Tehlikeli Bolge"
        description="Musteri hesabini ve tum tenant verisini kalici olarak siler. Bu islem geri alinamaz."
      >
        <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
          <Trash2 className="h-4 w-4" />
          Musteriyi Kalici Sil
        </Button>
      </AdminSectionCard>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={(open) => {
          setDeleteOpen(open);
          if (!open) setDeleteConfirmEmail("");
        }}
        title="Musteriyi kalici sil"
        destructive
        confirmLabel={deleteMutation.isPending ? "Siliniyor..." : "Kalici Sil"}
        isLoading={deleteMutation.isPending}
        disabled={deleteConfirmEmail.trim().toLowerCase() !== data.email.toLowerCase()}
        onConfirm={() => deleteMutation.mutate()}
        description={
          <>
            <strong>{data.email}</strong> hesabi, pozisyonlari, islemleri, ayarlari ve profil baglantilari tamamen
            silinecek.
          </>
        }
      >
        <div className="space-y-2">
          <Label htmlFor="deleteConfirmEmailDetail">Onay icin e-posta adresini yazin</Label>
          <Input
            id="deleteConfirmEmailDetail"
            value={deleteConfirmEmail}
            onChange={(e) => setDeleteConfirmEmail(e.target.value)}
            placeholder={data.email}
            autoComplete="off"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
