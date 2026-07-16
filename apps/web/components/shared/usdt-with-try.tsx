import { cn, formatTry, formatUsdt } from "@/lib/utils";

interface UsdtWithTryProps {
  usdt: string | number | null | undefined;
  usdtTryRate?: string | number | null | undefined;
  usdtDigits?: number;
  tryDigits?: number;
  className?: string;
  usdtClassName?: string;
  tryClassName?: string;
  size?: "sm" | "md" | "lg";
}

const usdtSizeClass: Record<NonNullable<UsdtWithTryProps["size"]>, string> = {
  sm: "text-xs font-semibold",
  md: "text-sm font-semibold",
  lg: "text-base font-semibold",
};

const trySizeClass: Record<NonNullable<UsdtWithTryProps["size"]>, string> = {
  sm: "text-[10px] font-medium",
  md: "text-xs font-semibold",
  lg: "text-sm font-semibold",
};

export function UsdtWithTry({
  usdt,
  usdtTryRate,
  usdtDigits = 2,
  tryDigits = 2,
  className,
  usdtClassName,
  tryClassName,
  size = "md",
}: UsdtWithTryProps) {
  const tryLabel = formatTry(usdt, usdtTryRate, tryDigits);

  return (
    <div className={cn("flex flex-wrap items-baseline gap-x-2 gap-y-0.5", className)}>
      <span className={cn("truncate tabular-nums", usdtSizeClass[size], usdtClassName)}>
        {formatUsdt(usdt, usdtDigits)}
      </span>
      {tryLabel ? (
        <span className={cn("truncate tabular-nums text-muted-foreground", trySizeClass[size], tryClassName)}>
          {tryLabel}
        </span>
      ) : null}
    </div>
  );
}
