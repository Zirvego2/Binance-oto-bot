import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  tryLabel?: string | null;
  icon?: LucideIcon;
  valueClassName?: string;
  hint?: string;
  hintClassName?: string;
}

export function StatCard({ label, value, tryLabel, icon: Icon, valueClassName, hint, hintClassName }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <p className={cn("text-xl font-semibold tabular-nums", valueClassName)}>{value}</p>
            {tryLabel ? (
              <p className="text-base font-semibold tabular-nums text-muted-foreground">{tryLabel}</p>
            ) : null}
          </div>
          {hint && <p className={cn("text-muted-foreground", hintClassName ?? "text-xs")}>{hint}</p>}
        </div>
        {Icon && (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary/60 text-muted-foreground">
            <Icon className="h-5 w-5" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
