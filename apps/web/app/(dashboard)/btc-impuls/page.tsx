"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Play, Radar, Save, Zap } from "lucide-react";

import { impulseApi, settingsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { ImpulseCandidateOut, ImpulseMode, ImpulseScanOut, ImpulseSettingsOut } from "@/types/api";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast-provider";
import { FIREBASE_SAVED_TOAST, ResetDefaultsButton } from "@/components/settings/reset-defaults-button";
import {
  numericField,
  SettingsField,
  SettingsSection,
} from "@/components/settings/settings-form-parts";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

const impulseSchema = z.object({
  impulse_mode: z.enum(["OFF", "MANUAL", "AUTO"]),
  impulse_btc_min_change_pct: numericField({ min: 0.05, max: 10 }),
  impulse_lookback_minutes: numericField({ min: 1, max: 30 }),
  impulse_extreme_min_score: numericField({ min: 0, max: 100 }),
  impulse_max_entries: numericField({ min: 1, max: 10 }),
  impulse_margin_usdt: numericField({ min: 0.01 }),
  impulse_leverage: numericField({ min: 0, max: 20 }),
  impulse_tp_roi_pct: numericField({ min: 0.01, max: 100 }),
  impulse_sl_roi_pct: numericField({ min: 0.01, max: 100 }),
  impulse_cooldown_minutes: numericField({ min: 0, max: 1440 }),
  impulse_top_n_scan: numericField({ min: 5, max: 100 }),
  impulse_rsi_overbought: numericField({ min: 50, max: 100 }),
  impulse_rsi_oversold: numericField({ min: 0, max: 50 }),
  impulse_check_interval_seconds: numericField({ min: 5, max: 300 }),
});

type FormValues = z.infer<typeof impulseSchema>;

function toFormValues(s: ImpulseSettingsOut): FormValues {
  return {
    impulse_mode: s.impulse_mode,
    impulse_btc_min_change_pct: Number(s.impulse_btc_min_change_pct),
    impulse_lookback_minutes: s.impulse_lookback_minutes,
    impulse_extreme_min_score: Number(s.impulse_extreme_min_score),
    impulse_max_entries: s.impulse_max_entries,
    impulse_margin_usdt: Number(s.impulse_margin_usdt),
    impulse_leverage: s.impulse_leverage,
    impulse_tp_roi_pct: Number(s.impulse_tp_roi_pct),
    impulse_sl_roi_pct: Number(s.impulse_sl_roi_pct),
    impulse_cooldown_minutes: s.impulse_cooldown_minutes,
    impulse_top_n_scan: s.impulse_top_n_scan,
    impulse_rsi_overbought: Number(s.impulse_rsi_overbought),
    impulse_rsi_oversold: Number(s.impulse_rsi_oversold),
    impulse_check_interval_seconds: s.impulse_check_interval_seconds,
  };
}

function toPayload(values: FormValues) {
  return {
    impulse_mode: values.impulse_mode as ImpulseMode,
    impulse_btc_min_change_pct: String(values.impulse_btc_min_change_pct),
    impulse_lookback_minutes: values.impulse_lookback_minutes,
    impulse_extreme_min_score: String(values.impulse_extreme_min_score),
    impulse_max_entries: values.impulse_max_entries,
    impulse_margin_usdt: String(values.impulse_margin_usdt),
    impulse_leverage: values.impulse_leverage,
    impulse_tp_roi_pct: String(values.impulse_tp_roi_pct),
    impulse_sl_roi_pct: String(values.impulse_sl_roi_pct),
    impulse_cooldown_minutes: values.impulse_cooldown_minutes,
    impulse_top_n_scan: values.impulse_top_n_scan,
    impulse_rsi_overbought: String(values.impulse_rsi_overbought),
    impulse_rsi_oversold: String(values.impulse_rsi_oversold),
    impulse_check_interval_seconds: values.impulse_check_interval_seconds,
  };
}

const MODE_LABELS: Record<ImpulseMode, string> = {
  OFF: "Kapali — sadece manuel buton",
  MANUAL: "Manuel — tarama ve islem butonlari",
  AUTO: "Otomatik — worker impulsu izler",
};

export default function BtcImpulsPage() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [scanResult, setScanResult] = React.useState<ImpulseScanOut | null>(null);
  const [manualSide, setManualSide] = React.useState<"" | "LONG" | "SHORT">("");

  const {
    data: settings,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["impulse-settings"],
    queryFn: () => impulseApi.settings(),
    refetchInterval: 15000,
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(impulseSchema),
    defaultValues: settings ? toFormValues(settings) : undefined,
  });

  React.useEffect(() => {
    if (settings) form.reset(toFormValues(settings));
  }, [settings, form]);

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => impulseApi.updateSettings(toPayload(values)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["impulse-settings"] });
      push({ title: "Impuls ayarlari kaydedildi", description: FIREBASE_SAVED_TOAST, variant: "success" });
    },
    onError: (err) => {
      push({
        title: "Kayit basarisiz",
        description: err instanceof ApiError ? err.message : "Bilinmeyen hata",
        variant: "error",
      });
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => settingsApi.resetDefaults("impulse"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["impulse-settings"] });
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      push({ title: "Varsayilan ayarlara donuldu", description: FIREBASE_SAVED_TOAST, variant: "success" });
    },
    onError: (err) => {
      push({
        title: "Varsayilan ayarlar yuklenemedi",
        description: err instanceof ApiError ? err.message : undefined,
        variant: "error",
      });
    },
  });

  const scanMutation = useMutation({
    mutationFn: () => impulseApi.scan(manualSide || undefined),
    onSuccess: (data) => {
      setScanResult(data);
      queryClient.invalidateQueries({ queryKey: ["impulse-settings"] });
      push({ title: data.message, variant: "info" });
    },
    onError: (err) => {
      push({
        title: "Tarama basarisiz",
        description: err instanceof ApiError ? err.message : "Bilinmeyen hata",
        variant: "error",
      });
    },
  });

  const executeMutation = useMutation({
    mutationFn: () =>
      impulseApi.execute({
        side: manualSide || undefined,
        max_entries: form.getValues("impulse_max_entries"),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["impulse-settings"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      push({
        title: data.message,
        description: data.opened.join(", ") || undefined,
        variant: data.opened.length > 0 ? "success" : "info",
      });
    },
    onError: (err) => {
      push({
        title: "Islem basarisiz",
        description: err instanceof ApiError ? err.message : "Bilinmeyen hata",
        variant: "error",
      });
    },
  });

  const mode = form.watch("impulse_mode");

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !settings) {
    return (
      <div className="space-y-4 p-6">
        <PageHeader
          title="BTC Impuls Islem"
          description="Sayfa yuklenemedi. API yeniden baslatilmis olmali."
        />
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
          <p className="font-medium">Baglanti hatasi</p>
          <p className="mt-1 text-muted-foreground">
            {error instanceof ApiError ? error.message : "Impuls ayarlari alinamadi. Botu yeniden baslatin."}
          </p>
          <Button className="mt-3" variant="outline" onClick={() => refetch()}>
            Tekrar Dene
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="BTC Impuls Islem"
        description="BTC ani hareketlerinde alt coinlerde lokal tepe/dip karsi islem. OFF modunda manuel butonla, AUTO modunda worker otomatik alir."
        actions={
          <ResetDefaultsButton
            scope="impulse"
            onReset={() => resetMutation.mutate()}
            isPending={resetMutation.isPending}
            disabled={saveMutation.isPending}
          />
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        <StatusCard
          label="Mod"
          value={MODE_LABELS[settings.impulse_mode]}
          highlight={settings.impulse_mode === "AUTO"}
        />
        <StatusCard
          label="Son BTC Degisim"
          value={
            settings.impulse_last_btc_change_pct != null
              ? `%${formatNumber(Number(settings.impulse_last_btc_change_pct), 2)}`
              : "—"
          }
          sub={settings.impulse_last_direction ?? undefined}
        />
        <StatusCard label="Son Acilan" value={String(settings.impulse_last_opened_count)} />
        <StatusCard
          label="Son Tarama"
          value={
            settings.impulse_last_scan_at
              ? new Date(settings.impulse_last_scan_at).toLocaleTimeString("tr-TR")
              : "—"
          }
        />
      </div>

      <div className="rounded-xl border border-border bg-card/50 p-4">
        <h2 className="mb-3 flex items-center gap-2 font-semibold">
          <Radar className="h-4 w-4 text-primary" />
          Manuel Kontrol
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          OFF veya MANUAL modda asagidaki butonlarla kendiniz tarayip pozisyon acabilirsiniz. AUTO modda worker
          ayarlara gore otomatik islem alir.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Zorla yon (opsiyonel)</p>
            <Select value={manualSide || "auto"} onValueChange={(v) => setManualSide(v === "auto" ? "" : (v as "LONG" | "SHORT"))}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="BTC impulsuna gore" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">BTC impulsuna gore</SelectItem>
                <SelectItem value="LONG">LONG (dip avcisi)</SelectItem>
                <SelectItem value="SHORT">SHORT (tepe avcisi)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" className="gap-2" disabled={scanMutation.isPending} onClick={() => scanMutation.mutate()}>
            {scanMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
            Tara
          </Button>
          <Button className="gap-2" disabled={executeMutation.isPending} onClick={() => executeMutation.mutate()}>
            {executeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Islem Al
          </Button>
        </div>

        {scanResult && (
          <div className="mt-4 space-y-2">
            <p className="text-sm">
              BTC: <strong>{scanResult.btc_direction}</strong> (%{formatNumber(scanResult.btc_change_pct, 2)}) →{" "}
              {scanResult.counter_side ?? "—"} | {scanResult.message}
              {scanResult.cooldown_active && (
                <span className="ml-2 text-amber-500">(Bekleme suresi aktif)</span>
              )}
            </p>
            <CandidatesTable candidates={scanResult.candidates} />
          </div>
        )}
      </div>

      <form
        className="space-y-6"
        onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
      >
        <SettingsSection title="Calisma Modu" description="Otomatik veya manuel impuls islem davranisi">
          <SettingsField label="Mod">
            <Select
              value={mode}
              onValueChange={(v) => form.setValue("impulse_mode", v as ImpulseMode, { shouldDirty: true })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="OFF">Kapali (Manuel)</SelectItem>
                <SelectItem value="MANUAL">Manuel</SelectItem>
                <SelectItem value="AUTO">Otomatik</SelectItem>
              </SelectContent>
            </Select>
          </SettingsField>
          <SettingsField label="Kontrol araligi (sn)">
            <Input type="number" step="1" {...form.register("impulse_check_interval_seconds", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Bekleme suresi (dk)">
            <Input type="number" step="1" {...form.register("impulse_cooldown_minutes", { valueAsNumber: true })} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="BTC Impuls Tespiti" description="Ani BTC hareketi esikleri">
          <SettingsField label="Min BTC degisim (%)">
            <Input type="number" step="0.05" {...form.register("impulse_btc_min_change_pct", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Geriye bakis (dk)">
            <Input type="number" step="1" {...form.register("impulse_lookback_minutes", { valueAsNumber: true })} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Pozisyon Parametreleri" description="Impuls islemlerine ozel marj ve ROI">
          <SettingsField label="Pozisyon basina marj (USDT)">
            <Input type="number" step="0.1" {...form.register("impulse_margin_usdt", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Kaldirac (0 = global)">
            <Input type="number" step="1" {...form.register("impulse_leverage", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Max pozisyon / olay">
            <Input type="number" step="1" {...form.register("impulse_max_entries", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Kar al ROI (%)">
            <Input type="number" step="0.1" {...form.register("impulse_tp_roi_pct", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Zarar durdur ROI (%)">
            <Input type="number" step="0.1" {...form.register("impulse_sl_roi_pct", { valueAsNumber: true })} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Aday Tarama" description="Alt coin lokal tepe/dip skorlama">
          <SettingsField label="Taranacak coin sayisi">
            <Input type="number" step="1" {...form.register("impulse_top_n_scan", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="Min ekstrem skor">
            <Input type="number" step="1" {...form.register("impulse_extreme_min_score", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="RSI asiri alim">
            <Input type="number" step="1" {...form.register("impulse_rsi_overbought", { valueAsNumber: true })} />
          </SettingsField>
          <SettingsField label="RSI asiri satim">
            <Input type="number" step="1" {...form.register("impulse_rsi_oversold", { valueAsNumber: true })} />
          </SettingsField>
        </SettingsSection>

        <Button type="submit" disabled={saveMutation.isPending || resetMutation.isPending} className="gap-2">
          {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Ayarlari Kaydet
        </Button>
      </form>
    </div>
  );
}

function StatusCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card/50 p-4",
        highlight && "border-primary/40 bg-primary/5"
      )}
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold leading-snug">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function CandidatesTable({ candidates }: { candidates: ImpulseCandidateOut[] }) {
  if (candidates.length === 0) {
    return <p className="text-sm text-muted-foreground">Aday bulunamadi.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border/60">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/60 bg-secondary/30 text-left text-xs text-muted-foreground">
            <th className="p-2">Sembol</th>
            <th className="p-2">Yon</th>
            <th className="p-2">Skor</th>
            <th className="p-2">RSI</th>
            <th className="p-2">Yakinlik</th>
            <th className="p-2">Hacim</th>
            <th className="p-2">Aciklama</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.symbol} className="border-t border-border/40">
              <td className="p-2 font-medium">{c.symbol}</td>
              <td className="p-2">{c.side}</td>
              <td className="p-2">{formatNumber(c.score, 1)}</td>
              <td className="p-2">{formatNumber(c.rsi, 1)}</td>
              <td className="p-2">%{formatNumber(c.proximity_pct, 2)}</td>
              <td className="p-2">x{formatNumber(c.volume_ratio, 2)}</td>
              <td className="p-2 text-xs text-muted-foreground">{c.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
