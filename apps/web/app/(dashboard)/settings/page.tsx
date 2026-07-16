"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Save } from "lucide-react";

import { settingsApi, systemApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { fireTakeProfitConfetti } from "@/lib/confetti";
import type { BotSettingsOut, BotSettingsUpdate } from "@/types/api";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast-provider";
import { FIREBASE_SAVED_TOAST, ResetDefaultsButton } from "@/components/settings/reset-defaults-button";
import {
  numericField,
  SettingsField,
  SettingsSection,
  SettingsToggleField,
} from "@/components/settings/settings-form-parts";

const settingsSchema = z.object({
  scan_interval_seconds: numericField({ min: 5, max: 3600 }),
  min_24h_volume_usdt: numericField({ min: 0 }),
  max_spread_pct: numericField({ min: 0.001 }),
  max_funding_rate_pct: numericField({ min: 0.001 }),
  max_volatility_atr_pct: numericField({ min: 0.001 }),
  min_signal_score: numericField({ min: 0, max: 100 }),
  top_n_symbols_by_volume: numericField({ min: 1, max: 200 }),
  long_enabled: z.boolean(),
  short_enabled: z.boolean(),
  auto_trading_enabled: z.boolean(),
  market_direction_filter_enabled: z.boolean(),
  take_profit_confetti_enabled: z.boolean(),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

function toFormValues(settings: BotSettingsOut): SettingsFormValues {
  return {
    scan_interval_seconds: settings.scan_interval_seconds,
    min_24h_volume_usdt: Number(settings.min_24h_volume_usdt),
    max_spread_pct: Number(settings.max_spread_pct),
    max_funding_rate_pct: Number(settings.max_funding_rate_pct),
    max_volatility_atr_pct: Number(settings.max_volatility_atr_pct),
    min_signal_score: Number(settings.min_signal_score),
    top_n_symbols_by_volume: settings.top_n_symbols_by_volume,
    long_enabled: settings.long_enabled,
    short_enabled: settings.short_enabled,
    auto_trading_enabled: settings.auto_trading_enabled,
    market_direction_filter_enabled: settings.market_direction_filter_enabled,
    take_profit_confetti_enabled: settings.take_profit_confetti_enabled ?? true,
  };
}

function toUpdatePayload(values: SettingsFormValues): BotSettingsUpdate {
  return {
    scan_interval_seconds: values.scan_interval_seconds,
    min_24h_volume_usdt: String(values.min_24h_volume_usdt),
    max_spread_pct: String(values.max_spread_pct),
    max_funding_rate_pct: String(values.max_funding_rate_pct),
    max_volatility_atr_pct: String(values.max_volatility_atr_pct),
    min_signal_score: String(values.min_signal_score),
    top_n_symbols_by_volume: values.top_n_symbols_by_volume,
    long_enabled: values.long_enabled,
    short_enabled: values.short_enabled,
    auto_trading_enabled: values.auto_trading_enabled,
    market_direction_filter_enabled: values.market_direction_filter_enabled,
    take_profit_confetti_enabled: values.take_profit_confetti_enabled,
  };
}

export default function SettingsPage() {
  const { push } = useToast();
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isDirty },
  } = useForm<SettingsFormValues>({ resolver: zodResolver(settingsSchema) });

  React.useEffect(() => {
    if (settings) reset(toFormValues(settings));
  }, [settings, reset]);

  const updateMutation = useMutation({
    mutationFn: (values: SettingsFormValues) => settingsApi.update(toUpdatePayload(values)),
    onSuccess: (updated) => {
      push({ title: "Ayarlar kaydedildi", description: "Musteri ayarlari Firebase'e senkronize edildi.", variant: "success" });
      queryClient.setQueryData(["settings"], updated);
      reset(toFormValues(updated));
    },
    onError: (error) =>
      push({ title: "Ayarlar kaydedilemedi", description: error instanceof ApiError ? error.message : undefined, variant: "error" }),
  });

  const resetMutation = useMutation({
    mutationFn: () => settingsApi.resetDefaults("general"),
    onSuccess: (updated) => {
      push({ title: "Varsayilan ayarlara donuldu", description: FIREBASE_SAVED_TOAST, variant: "success" });
      queryClient.setQueryData(["settings"], updated);
      reset(toFormValues(updated));
    },
    onError: (error) =>
      push({
        title: "Varsayilan ayarlar yuklenemedi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  if (isLoading || !settings) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const onSubmit = (values: SettingsFormValues) => updateMutation.mutate(values);

  return (
    <div>
      <PageHeader
        title="Genel Ayarlar"
        description={`Tarama, sinyal filtreleri ve otomasyon — mod: ${settings.mode.toUpperCase()}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ResetDefaultsButton
              scope="general"
              onReset={() => resetMutation.mutate()}
              isPending={resetMutation.isPending}
              disabled={updateMutation.isPending}
            />
            <Button onClick={handleSubmit(onSubmit)} disabled={!isDirty || updateMutation.isPending || resetMutation.isPending}>
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Kaydet
            </Button>
          </div>
        }
      />

      <div className="mb-4 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
        Kaydettiginiz ayarlar yalnizca sizin hesabiniza ozeldir ve Firebase&apos;e senkronize edilir. Marjin, TP/SL, DCA, olta ve risk limitleri icin{" "}
        <Link href="/pozisyon-ayarlari" className="font-semibold text-primary underline-offset-2 hover:underline">
          Pozisyon Ayarlari
        </Link>{" "}
        sayfasini kullanin.
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SettingsSection title="Tarama & Zamanlama" description="Strateji motorunun ne siklikta calisacagi">
          <SettingsField label="Tarama Araligi (saniye)" error={errors.scan_interval_seconds?.message}>
            <Input type="number" step="1" {...register("scan_interval_seconds")} />
          </SettingsField>
          <SettingsField label="Min. 24s Hacim (USDT)" error={errors.min_24h_volume_usdt?.message}>
            <Input type="number" step="1" {...register("min_24h_volume_usdt")} />
          </SettingsField>
          <SettingsField label="Hacme Gore Ilk N Sembol" error={errors.top_n_symbols_by_volume?.message}>
            <Input type="number" step="1" {...register("top_n_symbols_by_volume")} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Sinyal Filtreleri" description="Piyasa kosulu esikleri">
          <SettingsField label="Maks. Spread (%)" error={errors.max_spread_pct?.message}>
            <Input type="number" step="0.001" {...register("max_spread_pct")} />
          </SettingsField>
          <SettingsField label="Maks. Funding Orani (%)" error={errors.max_funding_rate_pct?.message}>
            <Input type="number" step="0.001" {...register("max_funding_rate_pct")} />
          </SettingsField>
          <SettingsField label="Maks. Volatilite (ATR %)" error={errors.max_volatility_atr_pct?.message}>
            <Input type="number" step="0.001" {...register("max_volatility_atr_pct")} />
          </SettingsField>
          <SettingsField label="Min. Sinyal Skoru (0-100)" error={errors.min_signal_score?.message}>
            <Input type="number" step="1" {...register("min_signal_score")} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Panel Efektleri" description="Kar alindiginda gorsel geri bildirim">
          <div className="sm:col-span-2 space-y-3">
            <SettingsToggleField
              label="Kar al (TP) konfeti efekti"
              description="Pozisyon kar al ile kapandiginda ekranda konfeti patlar"
              checked={watch("take_profit_confetti_enabled")}
              onChange={(v) => setValue("take_profit_confetti_enabled", v, { shouldDirty: true })}
            />
            <Button type="button" variant="outline" size="sm" onClick={() => fireTakeProfitConfetti()}>
              Konfeti test et
            </Button>
          </div>
        </SettingsSection>

        <TelegramSection />

        <SettingsSection title="Islem Yonu ve Otomasyon" description="LONG/SHORT izinleri ve otomatik islem anahtari">
          <div className="flex flex-col gap-2 sm:col-span-2">
            <SettingsToggleField label="LONG pozisyonlara izin ver" checked={watch("long_enabled")} onChange={(v) => setValue("long_enabled", v, { shouldDirty: true })} />
            <SettingsToggleField label="SHORT pozisyonlara izin ver" checked={watch("short_enabled")} onChange={(v) => setValue("short_enabled", v, { shouldDirty: true })} />
            <SettingsToggleField
              label="Otomatik islem acma aktif"
              checked={watch("auto_trading_enabled")}
              onChange={(v) => setValue("auto_trading_enabled", v, { shouldDirty: true })}
            />
            <SettingsToggleField
              label="BTC piyasa yonu filtresi (LONG piyasa → sadece LONG, SHORT → sadece SHORT)"
              checked={watch("market_direction_filter_enabled")}
              onChange={(v) => setValue("market_direction_filter_enabled", v, { shouldDirty: true })}
            />
          </div>
        </SettingsSection>
      </form>
    </div>
  );
}

function TelegramSection() {
  const { push } = useToast();
  const testMutation = useMutation({
    mutationFn: () => systemApi.telegramTest(),
    onSuccess: (res) => {
      push({
        title: res.ok ? "Telegram OK" : "Telegram Hatasi",
        description: res.message,
        variant: res.ok ? "success" : "error",
      });
    },
    onError: (err: ApiError) => {
      push({ title: "Telegram testi basarisiz", description: err.message, variant: "error" });
    },
  });

  return (
    <SettingsSection
      title="Telegram Bildirimleri"
      description="Pozisyon acilis/kapanis ve kar-zarar mesajlari Telegram'a gider (.env dosyasindan ayarlanir)"
    >
      <div className="sm:col-span-2 space-y-3 text-sm text-muted-foreground">
        <p>1. Telegram&apos;da <strong>@BotFather</strong> ile bot olusturun ve token alin.</p>
        <p>2. Bota <strong>/start</strong> yazin; chat_id icin bot token ile getUpdates API&apos;sine bakin.</p>
        <p>3. Proje kokundeki <code className="rounded bg-secondary px-1">.env</code> dosyasina token ve chat_id ekleyin.</p>
        <p>4. Botu yeniden baslatin (<code className="rounded bg-secondary px-1">scripts\start_bot.ps1</code>).</p>
        <Button type="button" variant="outline" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
          {testMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Telegram Test Mesaji Gonder
        </Button>
      </div>
    </SettingsSection>
  );
}
