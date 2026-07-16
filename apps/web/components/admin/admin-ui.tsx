"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronRight, Loader2, type LucideIcon } from "lucide-react";
import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];
type ButtonSize = VariantProps<typeof buttonVariants>["size"];

export function AdminLinkButton({
  href,
  children,
  variant = "default",
  size = "default",
  className,
}: {
  href: string;
  children: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}) {
  return (
    <Link href={href} className={cn(buttonVariants({ variant, size }), className)}>
      {children}
    </Link>
  );
}

export function AdminLoading({ label = "Yukleniyor..." }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
      {label}
    </div>
  );
}

export function AdminPageHeader({
  title,
  description,
  badge,
  breadcrumbs,
  actions,
}: {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  breadcrumbs?: Array<{ label: string; href?: string }>;
  actions?: React.ReactNode;
}) {
  return (
    <div className="space-y-3 border-b border-border/60 pb-5">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={`${crumb.label}-${idx}`}>
              {idx > 0 && <ChevronRight className="h-3 w-3 shrink-0 opacity-50" />}
              {crumb.href ? (
                <Link href={crumb.href} className="transition-colors hover:text-primary">
                  {crumb.label}
                </Link>
              ) : (
                <span className="font-medium text-foreground">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {badge}
          </div>
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function AdminStatCard({
  title,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const toneStyles = {
    default: "border-border/70 bg-card",
    success: "border-emerald-500/20 bg-emerald-500/5",
    warning: "border-amber-500/20 bg-amber-500/5",
    danger: "border-destructive/20 bg-destructive/5",
  } as const;

  const iconStyles = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    warning: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    danger: "bg-destructive/15 text-destructive",
  } as const;

  return (
    <Card className={cn("shadow-sm transition-shadow hover:shadow-md", toneStyles[tone])}>
      <CardContent className="flex items-start justify-between gap-3 p-5">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
          {hint && <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{hint}</p>}
        </div>
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", iconStyles[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}

export function AdminSectionCard({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
  noPadding,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  noPadding?: boolean;
}) {
  return (
    <Card className={cn("overflow-hidden border-border/80 shadow-sm", className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 border-b border-border/50 bg-muted/15 pb-4">
        <div>
          <CardTitle className="text-base font-semibold">{title}</CardTitle>
          {description && <CardDescription className="mt-1">{description}</CardDescription>}
        </div>
        {actions}
      </CardHeader>
      <CardContent className={cn(noPadding ? "p-0" : "pt-5", contentClassName)}>{children}</CardContent>
    </Card>
  );
}

export function AdminFilterTabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-muted/20 p-1">
      {tabs.map((tab) => (
        <Button
          key={tab.id}
          size="sm"
          variant={value === tab.id ? "default" : "ghost"}
          className={cn("h-8 px-3", value !== tab.id && "text-muted-foreground")}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && (
            <Badge variant="secondary" className="ml-1.5 h-5 min-w-5 px-1 text-[10px]">
              {tab.count}
            </Badge>
          )}
        </Button>
      ))}
    </div>
  );
}

export function AdminInfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/40 py-2.5 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="max-w-[60%] text-right text-sm font-medium">{value}</span>
    </div>
  );
}

export function AdminEmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <p className="font-medium text-foreground">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}

export function AdminCapacityBar({
  current,
  capacity,
  label = "Platform kapasitesi",
}: {
  current: number;
  capacity: number;
  label?: string;
}) {
  const pct = capacity > 0 ? Math.min(100, Math.round((current / capacity) * 100)) : 0;
  const tone = pct >= 90 ? "bg-destructive" : pct >= 70 ? "bg-amber-500" : "bg-primary";

  return (
    <div className="rounded-xl border border-border/70 bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {current}
            <span className="text-base font-normal text-muted-foreground"> / {capacity} musteri</span>
          </p>
        </div>
        <Badge variant={pct >= 90 ? "destructive" : pct >= 70 ? "warning" : "secondary"}>{pct}% dolu</Badge>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {capacity - current} bos slot · 100+ musteri icin olceklendirme plani onerilir
      </p>
    </div>
  );
}

export function AdminRegistrationChart({ data }: { data: Array<{ date: string; count: number }> }) {
  const rows = data ?? [];
  const max = Math.max(1, ...rows.map((d) => d.count));

  return (
    <div className="flex h-32 items-end justify-between gap-2">
      {rows.map((day) => {
        const height = Math.max(8, Math.round((day.count / max) * 100));
        const label = new Date(day.date).toLocaleDateString("tr-TR", { weekday: "short" });
        return (
          <div key={day.date} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-[10px] font-medium tabular-nums text-muted-foreground">{day.count}</span>
            <div className="flex w-full items-end justify-center" style={{ height: "80px" }}>
              <div
                className="w-full max-w-[36px] rounded-t-md bg-primary/80 transition-all"
                style={{ height: `${height}%` }}
                title={`${day.date}: ${day.count} kayit`}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

const ACTION_LABELS: Record<string, string> = {
  LOGIN: "Giris yapti",
  CUSTOMER_REGISTER: "Kayit oldu",
  UPDATE_SETTINGS: "Ayar guncelledi",
  BOT_START: "Botu baslatti",
  BOT_STOP: "Botu durdurdu",
  RESET_SETTINGS_DEFAULTS: "Varsayilan ayarlara dondu",
};

export function AdminActivityFeed({
  items,
}: {
  items: Array<{
    id: string;
    action: string;
    customer_email: string | null;
    created_at: string;
  }>;
}) {
  if (items.length === 0) {
    return <AdminEmptyState title="Henuz aktivite yok" />;
  }

  return (
    <div className="divide-y divide-border/50">
      {items.map((item) => (
        <div key={item.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p className="text-sm">
              <span className="font-medium">{item.customer_email || "Sistem"}</span>
              <span className="text-muted-foreground"> · {ACTION_LABELS[item.action] || item.action}</span>
            </p>
          </div>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {new Date(item.created_at).toLocaleString("tr-TR")}
          </span>
        </div>
      ))}
    </div>
  );
}

export function AdminPagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 px-5 py-3 text-sm">
      <p className="text-muted-foreground">
        {from}-{to} / {total} kayit
      </p>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Onceki
        </Button>
        <span className="px-2 text-xs tabular-nums text-muted-foreground">
          {page} / {totalPages}
        </span>
        <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Sonraki
        </Button>
      </div>
    </div>
  );
}

export function botStatusBadge(runState: string | null | undefined, enabled: boolean) {
  if (runState === "RUNNING") return <Badge variant="success">Bot Calisiyor</Badge>;
  if (enabled) return <Badge variant="warning">Hazir (Durdu)</Badge>;
  return <Badge variant="secondary">Bot Kapali</Badge>;
}

