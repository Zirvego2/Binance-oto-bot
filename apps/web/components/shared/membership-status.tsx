"use client";

import { CalendarClock, AlertTriangle } from "lucide-react";

import type { AdminOut } from "@/types/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

function formatExpiryDate(value: string | null | undefined) {
  if (!value) return null;
  return new Date(value).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function MembershipStatusBanner({ admin }: { admin: AdminOut | undefined }) {
  if (!admin?.membership_expires_at) return null;

  const days = admin.membership_days_remaining ?? 0;
  const active = admin.membership_active !== false;
  const expiryLabel = formatExpiryDate(admin.membership_expires_at);

  if (!active) {
    return (
      <div className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">Uyelik suresi doldu</p>
          <p className="text-xs opacity-90">
            {expiryLabel ? `${expiryLabel} tarihinde sona erdi.` : ""} Yenilemek icin yonetici ile iletisime gecin.
          </p>
        </div>
      </div>
    );
  }

  const isWarning = days <= 7;

  return (
    <Card
      className={cn(
        "mb-4 border shadow-sm",
        isWarning ? "border-amber-500/30 bg-amber-500/5" : "border-primary/20 bg-primary/5",
      )}
    >
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
              isWarning ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-primary/15 text-primary",
            )}
          >
            {isWarning ? <AlertTriangle className="h-5 w-5" /> : <CalendarClock className="h-5 w-5" />}
          </div>
          <div>
            <p className="text-sm font-medium">Uyelik Durumu</p>
            <p className="mt-0.5 text-2xl font-semibold tabular-nums">
              {days} <span className="text-base font-medium text-muted-foreground">gun kaldi</span>
            </p>
            {expiryLabel ? (
              <p className="mt-1 text-xs text-muted-foreground">Bitis tarihi: {expiryLabel}</p>
            ) : null}
          </div>
        </div>
        <Badge variant={isWarning ? "warning" : "success"} className="px-2.5 py-1 text-xs">
          {isWarning ? "Yakinda bitecek" : "Aktif uyelik"}
        </Badge>
      </CardContent>
    </Card>
  );
}

export function MembershipTopbarBadge({ admin }: { admin: AdminOut | undefined }) {
  if (!admin?.membership_expires_at || admin.membership_active === false) return null;
  const days = admin.membership_days_remaining;
  if (days == null) return null;

  return (
    <Badge
      variant={days <= 7 ? "warning" : "outline"}
      className="hidden shrink-0 px-1.5 py-0 text-[10px] lg:inline-flex"
    >
      <CalendarClock className="mr-1 h-2.5 w-2.5" />
      {days} gun
    </Badge>
  );
}
