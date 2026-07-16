import { Badge } from "@/components/ui/badge";
import { isPositionNew } from "@/lib/utils";

export function SideBadge({ side }: { side: string | null | undefined }) {
  if (!side) return <span className="text-muted-foreground">-</span>;
  return <Badge variant={side === "LONG" ? "success" : "destructive"}>{side}</Badge>;
}

const STATUS_VARIANT: Record<string, "success" | "destructive" | "secondary" | "warning" | "outline"> = {
  OPEN: "success",
  CLOSED: "secondary",
  NEW: "outline",
  FILLED: "success",
  CANCELED: "secondary",
  REJECTED: "destructive",
  RUNNING: "success",
  STOPPED: "secondary",
  EMERGENCY_STOPPED: "destructive",
  SAFE_MODE: "warning",
  HEALTHY: "success",
  DEGRADED: "warning",
  UNHEALTHY: "destructive",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>;
}

export function NewPositionBadge({
  openedAt,
  status,
  withinMinutes = 10,
}: {
  openedAt: string | null | undefined;
  status?: string | null;
  withinMinutes?: number;
}) {
  if (status && status !== "OPEN") return null;
  if (!isPositionNew(openedAt, withinMinutes)) return null;
  return (
    <Badge variant="destructive" className="px-1.5 py-0 text-[10px] font-semibold uppercase tracking-wide">
      Yeni
    </Badge>
  );
}
