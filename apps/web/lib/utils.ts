import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Sunucudan string olarak gelen Decimal degerlerini guvenle sayiya cevirir. */
export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export function formatUsdt(value: string | number | null | undefined, digits = 2): string {
  return `${toNumber(value).toLocaleString("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} USDT`;
}

/** USDT tutarini Turk Lirasi olarak formatlar (kur gerekir). */
export function formatTry(
  usdtValue: string | number | null | undefined,
  usdtTryRate: string | number | null | undefined,
  digits = 2,
): string | null {
  const rate = toNumber(usdtTryRate);
  if (rate <= 0) return null;
  const tryAmount = toNumber(usdtValue) * rate;
  return `${tryAmount.toLocaleString("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} ₺`;
}

export function formatNumber(value: string | number | null | undefined, digits = 4): string {
  return toNumber(value).toLocaleString("tr-TR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function formatPct(value: string | number | null | undefined, digits = 2): string {
  return `%${toNumber(value).toLocaleString("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

/** Backend/SQLite UTC datetime — suffix yoksa UTC kabul edilir. */
export function parseApiUtcDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const normalized =
    trimmed.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(trimmed) ? trimmed : `${trimmed}Z`;
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(value: string | null | undefined): string {
  const d = parseApiUtcDate(value);
  if (!d) return value ?? "-";
  try {
    return d.toLocaleString("tr-TR", { hour12: false });
  } catch {
    return value ?? "-";
  }
}

export function formatDateTimeShort(value: string | null | undefined): string {
  const d = parseApiUtcDate(value);
  if (!d) return value ?? "-";
  try {
    return d.toLocaleString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return value ?? "-";
  }
}

export function pnlColorClass(value: string | number | null | undefined): string {
  const n = toNumber(value);
  if (n > 0) return "text-success";
  if (n < 0) return "text-destructive";
  return "text-muted-foreground";
}

/** Acilis zamani son N dakika icindeyse pozisyon "yeni" sayilir. */
export function isPositionNew(openedAt: string | null | undefined, withinMinutes = 10): boolean {
  const opened = parseApiUtcDate(openedAt);
  if (!opened) return false;
  return Date.now() - opened.getTime() < withinMinutes * 60 * 1000;
}
