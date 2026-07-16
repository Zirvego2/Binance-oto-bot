"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { MarketAiResearchOut } from "@/types/api";
import { cn } from "@/lib/utils";
import type { ComponentType } from "react";
import {
  AlertTriangle,
  Brain,
  Clock,
  Lightbulb,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Minus,
} from "lucide-react";

const OUTLOOK_CONFIG = {
  BULLISH: { label: "Yükseliş Eğilimi", icon: TrendingUp, cls: "text-green-400 bg-green-500/10 border-green-500/30" },
  BEARISH: { label: "Düşüş Eğilimi", icon: TrendingDown, cls: "text-red-400 bg-red-500/10 border-red-500/30" },
  NEUTRAL: { label: "Nötr", icon: Minus, cls: "text-zinc-400 bg-zinc-500/10 border-zinc-500/30" },
  UNCERTAIN: { label: "Belirsiz", icon: AlertTriangle, cls: "text-amber-400 bg-amber-500/10 border-amber-500/30" },
} as const;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  data: MarketAiResearchOut | null;
  loading: boolean;
  onRefresh: () => void;
}

export function MarketAiResearchDialog({ open, onOpenChange, data, loading, onRefresh }: Props) {
  const outlook = data?.market_outlook ?? "UNCERTAIN";
  const cfg = OUTLOOK_CONFIG[outlook as keyof typeof OUTLOOK_CONFIG] ?? OUTLOOK_CONFIG.UNCERTAIN;
  const Icon = cfg.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            Yapay Zeka Piyasa Araştırması
          </DialogTitle>
          <DialogDescription>
            ChatGPT destekli profesyonel analiz — işlem emri vermez, yalnızca bilgilendirme amaçlıdır.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm">Piyasa verileri analiz ediliyor…</p>
            <p className="text-xs">BTC trendi, momentum ve rejim verileri değerlendiriliyor</p>
          </div>
        ) : !data ? null : data.status !== "OK" ? (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6">
            <p className="font-medium text-amber-400">{data.executive_summary}</p>
            {data.risk_factors.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                {data.risk_factors.map((r) => (
                  <li key={r}>• {r}</li>
                ))}
              </ul>
            )}
            <p className="mt-4 text-xs text-muted-foreground">
              `.env` dosyasına geçerli bir <code className="rounded bg-muted px-1">OPENAI_API_KEY</code> ekleyin ve API servisini yeniden başlatın.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium", cfg.cls)}>
                <Icon className="h-4 w-4" />
                {cfg.label}
              </span>
              <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                Güven: {data.confidence_pct}%
              </span>
              <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                Ufuk: {data.time_horizon}
              </span>
              {data.cached && (
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">Önbellek</span>
              )}
              {data.model && (
                <span className="text-xs text-muted-foreground">{data.model}</span>
              )}
            </div>

            <section className="rounded-xl border border-border bg-card/50 p-4">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="h-4 w-4 text-primary" />
                Yönetici Özeti
              </h3>
              <p className="text-sm leading-relaxed text-foreground/90">{data.executive_summary}</p>
            </section>

            <section className="rounded-xl border border-border bg-card/50 p-4">
              <h3 className="mb-2 text-sm font-semibold">BTC Analizi</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{data.btc_analysis}</p>
            </section>

            <section className="rounded-xl border border-border bg-card/50 p-4">
              <h3 className="mb-2 text-sm font-semibold">Altcoin Etkisi</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{data.altcoin_implications}</p>
            </section>

            {data.key_observations.length > 0 && (
              <SectionList title="Önemli Gözlemler" items={data.key_observations} icon={Lightbulb} />
            )}

            {data.opportunities.length > 0 && (
              <SectionList title="Fırsat Alanları" items={data.opportunities} icon={TrendingUp} positive />
            )}

            {data.risk_factors.length > 0 && (
              <SectionList title="Risk Faktörleri" items={data.risk_factors} icon={AlertTriangle} warn />
            )}

            {data.analyst_note && (
              <section className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                <h3 className="mb-2 text-sm font-semibold text-primary">Analist Notu</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{data.analyst_note}</p>
              </section>
            )}

            <div className="flex items-center justify-between border-t border-border pt-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {data.generated_at ? new Date(data.generated_at).toLocaleString("tr-TR") : "—"}
              </span>
              <button
                type="button"
                onClick={onRefresh}
                className="flex items-center gap-1 rounded-md border border-border px-2 py-1 hover:bg-secondary/50"
              >
                <RefreshCw className="h-3 w-3" />
                Yenile
              </button>
            </div>

            <p className="text-center text-[11px] text-muted-foreground">{data.disclaimer}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SectionList({
  title,
  items,
  icon: Icon,
  positive,
  warn,
}: {
  title: string;
  items: string[];
  icon: ComponentType<{ className?: string }>;
  positive?: boolean;
  warn?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border p-4",
        warn ? "border-red-500/20 bg-red-500/5" : positive ? "border-green-500/20 bg-green-500/5" : "border-border bg-card/50"
      )}
    >
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Icon className={cn("h-4 w-4", warn ? "text-red-400" : positive ? "text-green-400" : "text-primary")} />
        {title}
      </h3>
      <ul className="space-y-1.5 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="text-muted-foreground/60">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
