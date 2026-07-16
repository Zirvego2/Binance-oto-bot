"use client";



import * as React from "react";

import Link from "next/link";

import { useQuery } from "@tanstack/react-query";

import {

  Activity,

  AlertCircle,

  Bot,

  Clock,

  Layers,

  ShieldCheck,

  TrendingUp,

  UserPlus,

  Users,

  Wallet,

  type LucideIcon,

} from "lucide-react";



import { platformAdminApi } from "@/lib/api";

import {

  AdminActivityFeed,
  AdminCapacityBar,
  AdminLinkButton,
  AdminLoading,

  AdminPageHeader,

  AdminRegistrationChart,

  AdminSectionCard,

  AdminStatCard,

} from "@/components/admin/admin-ui";

import { Badge } from "@/components/ui/badge";



export default function AdminOverviewPage() {

  const { data, isLoading } = useQuery({

    queryKey: ["platform", "overview"],

    queryFn: platformAdminApi.overview,

    refetchInterval: 60_000,

  });



  const { data: activity } = useQuery({

    queryKey: ["platform", "activity"],

    queryFn: () => platformAdminApi.activity(20),

    refetchInterval: 60_000,

  });



  if (isLoading || !data) {

    return <AdminLoading />;

  }



  const readinessPct =

    data.approved_customers > 0

      ? Math.round((data.trading_ready_customers / data.approved_customers) * 100)

      : 0;



  const stats: Array<{

    title: string;

    value: string | number;

    icon: LucideIcon;

    hint?: string;

    tone?: "default" | "success" | "warning" | "danger";

  }> = [

    { title: "Toplam Musteri", value: data.total_customers, icon: Users },

    {

      title: "Onay Bekleyen",

      value: data.pending_customers,

      icon: Clock,

      hint: "Kayit sonrasi yonetici onayi",

      tone: data.pending_customers > 0 ? "warning" : "default",

    },

    { title: "Onayli Musteri", value: data.approved_customers, icon: ShieldCheck, tone: "success" },

    { title: "Islem Hazir", value: data.trading_ready_customers, icon: Wallet, hint: "Onayli + Binance bagli", tone: "success" },

    { title: "Bot Calisiyor", value: data.customers_bot_running, icon: Bot, hint: "Aktif tarama/emir" },

    { title: "Acik Pozisyon", value: data.total_open_positions, icon: Layers, hint: "Tum musteriler toplami" },

    { title: "Cevrimici", value: data.customers_online, icon: Activity, tone: "success" },

    { title: "Son 7 Gun Kayit", value: data.new_customers_7d, icon: UserPlus, hint: `Son 30 gun: ${data.new_customers_30d}` },

    { title: "Binance Bagli", value: data.customers_with_binance, icon: Wallet },

  ];



  return (

    <div className="space-y-8">

      <AdminPageHeader

        title="Platform Ozeti"

        description="100 musteriye kadar olceklendirilmis yonetim konsolu — kayit, entegrasyon ve bot operasyonlari."

        badge={<Badge variant="outline">Canli</Badge>}

        actions={
          <>
            <AdminLinkButton href="/admin/customers" variant="outline">
              Musteri Yonetimi
            </AdminLinkButton>
            <AdminLinkButton href="/admin/earnings">Kazanc Raporlari</AdminLinkButton>
          </>
        }

      />



      <div className="grid gap-4 lg:grid-cols-3">

        <div className="lg:col-span-2">

          <AdminCapacityBar current={data.total_customers} capacity={data.platform_capacity} />

        </div>

        <AdminSectionCard title="Operasyonel Hazirlik" description="Onayli musterilerin islem icin hazir olma orani">

          <div className="flex items-center justify-between">

            <div>

              <p className="text-3xl font-semibold tabular-nums">{readinessPct}%</p>

              <p className="mt-1 text-xs text-muted-foreground">

                {data.trading_ready_customers} / {data.approved_customers} onayli musteri Binance bagli

              </p>

            </div>

            <div className="text-right text-xs text-muted-foreground">

              <p>Telegram: {data.customers_with_telegram}</p>

              <p>OpenAI: {data.customers_with_openai}</p>

              <p>Aktif oturum: {data.active_sessions}</p>

            </div>

          </div>

        </AdminSectionCard>

      </div>



      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">

        {stats.map((stat) => (

          <AdminStatCard key={stat.title} {...stat} />

        ))}

      </div>



      <div className="grid gap-4 lg:grid-cols-2">

        <AdminSectionCard title="Kayit Trendi" description="Son 7 gun — yeni musteri kayitlari">

          <AdminRegistrationChart data={data.registration_trend_7d ?? []} />

        </AdminSectionCard>



        <AdminSectionCard title="Son Aktiviteler" description="Platform geneli audit kayitlari">

          <AdminActivityFeed items={activity ?? []} />

        </AdminSectionCard>

      </div>



      {data.pending_customers > 0 && (

        <AdminSectionCard

          title="Acil Islem Gerektiren"

          description="Onay bekleyen musteriler platforma erisemeden bekliyor."

          actions={<Badge variant="warning">{data.pending_customers} bekleyen</Badge>}

        >

          <div className="flex flex-wrap items-center justify-between gap-4">

            <div className="flex items-start gap-3">

              <div className="rounded-lg bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">

                <AlertCircle className="h-5 w-5" />

              </div>

              <div>

                <p className="text-sm font-medium">Onay kuyrugunda musteriler var</p>

                <p className="text-xs text-muted-foreground">

                  100 musteri hedefine yaklasirken onay surecini hizli tutun.

                </p>

              </div>

            </div>

            <AdminLinkButton href="/admin/customers?status=pending" size="sm">
              Onay Kuyrugunu Ac
            </AdminLinkButton>

          </div>

        </AdminSectionCard>

      )}



      <AdminSectionCard title="Hizli Erisim" description="Sik kullanilan yonetim islemleri">

        <div className="grid gap-3 sm:grid-cols-3">

          <Link

            href="/admin/customers"

            className="rounded-lg border border-border/70 bg-muted/10 p-4 transition-colors hover:border-primary/30 hover:bg-primary/5"

          >

            <Users className="mb-2 h-5 w-5 text-primary" />

            <p className="text-sm font-medium">Musteri Listesi</p>

            <p className="mt-1 text-xs text-muted-foreground">Sayfali arama ve filtreleme</p>

          </Link>

          <Link

            href="/admin/earnings"

            className="rounded-lg border border-border/70 bg-muted/10 p-4 transition-colors hover:border-primary/30 hover:bg-primary/5"

          >

            <TrendingUp className="mb-2 h-5 w-5 text-primary" />

            <p className="text-sm font-medium">Kazanc Analizi</p>

            <p className="mt-1 text-xs text-muted-foreground">Musteri bazli PnL siralamasi</p>

          </Link>

          <Link

            href="/admin/customers?status=pending"

            className="rounded-lg border border-border/70 bg-muted/10 p-4 transition-colors hover:border-primary/30 hover:bg-primary/5"

          >

            <Clock className="mb-2 h-5 w-5 text-primary" />

            <p className="text-sm font-medium">Onay Bekleyenler</p>

            <p className="mt-1 text-xs text-muted-foreground">{data.pending_customers} musteri bekliyor</p>

          </Link>

        </div>

      </AdminSectionCard>

    </div>

  );

}


