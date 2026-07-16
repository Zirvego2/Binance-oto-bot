"use client";

import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, LogOut, Phone, Sparkles, Wifi, WifiOff, Cpu, CalendarClock } from "lucide-react";

import { authApi, botApi, dashboardApi } from "@/lib/api";
import { firebaseSignOut } from "@/lib/firebase-auth";
import { MobileMenuButton } from "@/components/layout/mobile-nav";
import { MembershipTopbarBadge } from "@/components/shared/membership-status";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast-provider";
import { APP_NAME, APP_NAME_UPPER, APP_TAGLINE } from "@/lib/branding";

const MODE_LABEL: Record<string, string> = { paper: "PAPER", demo: "DEMO", live: "LIVE" };

export function Topbar({
  mobileMenuOpen = false,
  onMobileMenuToggle,
}: {
  mobileMenuOpen?: boolean;
  onMobileMenuToggle?: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { push } = useToast();

  const { data: admin } = useQuery({ queryKey: ["auth", "me"], queryFn: authApi.me, retry: false });
  const { data: status } = useQuery({
    queryKey: ["bot", "status"],
    queryFn: botApi.status,
    refetchInterval: 10_000,
  });
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    refetchInterval: (query) => ((query.state.data as { worker_connected?: boolean } | undefined)?.worker_connected === false ? 5_000 : 10_000),
  });

  const handleLogout = async () => {
    try {
      await firebaseSignOut();
    } catch {
      // yoksay: cookie zaten temizlenmis olabilir
    }
    queryClient.clear();
    push({ title: "Cikis yapildi", variant: "info" });
    router.replace("/login");
    router.refresh();
  };

  const mode = status?.mode ?? "paper";
  const modeVariant = mode === "live" ? "destructive" : mode === "demo" ? "warning" : "secondary";
  const isConnected = dashboard?.binance_connected || mode === "paper";
  const workerOk = dashboard?.worker_connected ?? status?.worker_connected ?? false;

  return (
    <header className="shrink-0 border-b border-border bg-card/40">
      <div className="flex min-h-11 items-center gap-2 px-2 py-1.5 sm:px-3 md:min-h-10">
        <MobileMenuButton open={mobileMenuOpen} onClick={() => onMobileMenuToggle?.()} />

        <div className="flex min-w-0 flex-1 items-center gap-2 md:hidden">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-primary">{APP_NAME}</p>
            <p className="truncate text-[10px] text-muted-foreground">{admin?.email ?? "Musteri Paneli"}</p>
          </div>
        </div>

        <div className="hidden min-w-0 flex-wrap items-center gap-2 md:flex">
          <Badge variant={modeVariant as never} className="px-1.5 py-0 text-[10px]">
            {MODE_LABEL[mode] ?? mode.toUpperCase()}
          </Badge>
          <Badge variant={status?.run_state === "RUNNING" ? "success" : "outline"} className="px-1.5 py-0 text-[10px]">
            {status?.run_state === "RUNNING"
              ? "CALISIYOR"
              : status?.run_state === "EMERGENCY_STOPPED"
                ? "ACIL DURDURULDU"
                : status?.run_state === "SAFE_MODE"
                  ? "GUVENLI MOD"
                  : "DURDURULDU"}
          </Badge>
          <Badge variant={workerOk ? "success" : "destructive"} className="gap-0.5 px-1.5 py-0 text-[10px]">
            <Cpu className="h-2.5 w-2.5" />
            {workerOk ? "WORKER AKTIF" : "WORKER DURDU"}
          </Badge>
          <span className="hidden items-center gap-1 text-[10px] text-muted-foreground lg:flex">
            {isConnected ? <Wifi className="h-3 w-3 text-success" /> : <WifiOff className="h-3 w-3 text-destructive" />}
            {mode === "paper" ? "Piyasa verisi aktif" : isConnected ? "Binance baglantisi aktif" : "Binance baglantisi yok"}
          </span>
        </div>

        <div className="hidden min-w-0 flex-1 justify-center px-2 lg:flex">
          <a
            href="tel:+905309052018"
            className="group relative max-w-xl overflow-hidden rounded-md border border-primary/35 bg-gradient-to-r from-primary/15 via-primary/5 to-transparent px-3 py-1 shadow-[0_0_16px_hsl(45_93%_47%/0.1)] transition hover:border-primary/55 hover:from-primary/20"
          >
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_50%,hsl(45_93%_47%/0.15),transparent_55%)]" />
            <div className="relative flex items-center gap-2">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-primary/20 text-primary ring-1 ring-primary/30">
                <Bot className="h-3 w-3" />
              </div>
              <div className="min-w-0 text-left">
                <p className="bg-gradient-to-r from-primary to-amber-200 bg-clip-text text-xs font-bold tracking-wide text-transparent">
                  {APP_NAME_UPPER}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  <span className="font-medium text-foreground/90">{APP_TAGLINE}</span>
                  <span className="hidden xl:inline"> · 7/24 otomatik Binance Futures</span>
                </p>
              </div>
              <div className="hidden shrink-0 flex-col items-end border-l border-primary/20 pl-2 xl:flex">
                <span className="text-[9px] font-medium uppercase tracking-wider text-primary">Ucretsiz bilgi</span>
                <span className="flex items-center gap-0.5 text-xs font-bold tabular-nums text-foreground group-hover:text-primary">
                  <Phone className="h-3 w-3" />
                  0530 905 2018
                </span>
              </div>
            </div>
          </a>
        </div>

        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          <a
            href="tel:+905309052018"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary md:hidden"
            aria-label="Destek hattini ara"
          >
            <Phone className="h-3.5 w-3.5" />
          </a>
          {admin && <MembershipTopbarBadge admin={admin} />}
          {admin && <span className="hidden text-xs text-muted-foreground lg:inline">{admin.email}</span>}
          <Button variant="ghost" size="sm" className="h-8 w-8 px-0 sm:h-7 sm:w-auto sm:px-2" onClick={handleLogout}>
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Cikis</span>
          </Button>
        </div>
      </div>

      <div className="flex gap-1.5 overflow-x-auto border-t border-border/50 px-2 py-1.5 scrollbar-thin md:hidden">
        <Badge variant={modeVariant as never} className="shrink-0 px-1.5 py-0 text-[10px]">
          {MODE_LABEL[mode] ?? mode.toUpperCase()}
        </Badge>
        <Badge variant={status?.run_state === "RUNNING" ? "success" : "outline"} className="shrink-0 px-1.5 py-0 text-[10px]">
          {status?.run_state === "RUNNING" ? "CALISIYOR" : "DURDURULDU"}
        </Badge>
        <Badge variant={workerOk ? "success" : "destructive"} className="shrink-0 gap-0.5 px-1.5 py-0 text-[10px]">
          <Cpu className="h-2.5 w-2.5" />
          {workerOk ? "WORKER" : "WORKER YOK"}
        </Badge>
        <Badge variant="outline" className="shrink-0 gap-0.5 px-1.5 py-0 text-[10px]">
          {isConnected ? <Wifi className="h-2.5 w-2.5 text-success" /> : <WifiOff className="h-2.5 w-2.5 text-destructive" />}
          {mode === "paper" ? "Veri OK" : isConnected ? "Binance OK" : "Binance YOK"}
        </Badge>
        {admin?.membership_expires_at && admin.membership_active !== false && admin.membership_days_remaining != null ? (
          <Badge variant={admin.membership_days_remaining <= 7 ? "warning" : "outline"} className="shrink-0 gap-0.5 px-1.5 py-0 text-[10px]">
            <CalendarClock className="h-2.5 w-2.5" />
            {admin.membership_days_remaining} gun
          </Badge>
        ) : null}
        <a
          href="tel:+905309052018"
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
        >
          <Sparkles className="h-2.5 w-2.5" />
          0530 905 2018
        </a>
      </div>
    </header>
  );
}
