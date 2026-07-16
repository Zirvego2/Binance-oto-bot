"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Save, SlidersHorizontal } from "lucide-react";

import { settingsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { BotSettingsOut, BotSettingsUpdate } from "@/types/api";
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
  SettingsToggleField,
} from "@/components/settings/settings-form-parts";

const positionSettingsSchema = z.object({
  margin_per_trade_usdt: numericField({ min: 0.01 }),
  leverage: numericField({ min: 1, max: 20 }),
  take_profit_roi_pct: numericField({ min: 0.01 }),
  stop_loss_roi_pct: numericField({ min: 0.01 }),
  loss_add_enabled: z.boolean(),
  loss_add_trigger_roi_pct: numericField({ min: 0.01, max: 100 }),
  loss_add_max_count: numericField({ min: 0, max: 15 }),
  trailing_stop_enabled: z.boolean(),
  trailing_stop_activation_roi_pct: numericField({ min: 0.01 }),
  trailing_stop_callback_rate_pct: numericField({ min: 0.01 }),
  max_open_positions: numericField({ min: 1, max: 50 }),
  max_open_positions_per_symbol: numericField({ min: 1, max: 5 }),
  daily_max_loss_usdt: numericField({ min: 0.01 }),
  max_consecutive_losses: numericField({ min: 1, max: 20 }),
  min_liquidation_distance_pct: numericField({ min: 0.01 }),
  max_slippage_pct: numericField({ min: 0.01 }),
  post_trade_cooldown_minutes: numericField({ min: 0, max: 1440 }),
  limit_entry_enabled: z.boolean(),
  limit_entry_offset_pct: numericField({ min: 0, max: 5 }),
  limit_entry_timeout_minutes: numericField({ min: 1, max: 1440 }),
  limit_entry_max_pending: numericField({ min: 1, max: 20 }),
});

type PositionSettingsFormValues = z.infer<typeof positionSettingsSchema>;

function toFormValues(settings: BotSettingsOut): PositionSettingsFormValues {
  return {
    margin_per_trade_usdt: Number(settings.margin_per_trade_usdt),
    leverage: settings.leverage,
    take_profit_roi_pct: Number(settings.take_profit_roi_pct),
    stop_loss_roi_pct: Number(settings.stop_loss_roi_pct),
    loss_add_enabled: settings.loss_add_enabled,
    loss_add_trigger_roi_pct: Number(settings.loss_add_trigger_roi_pct ?? 25),
    loss_add_max_count: settings.loss_add_max_count,
    trailing_stop_enabled: settings.trailing_stop_enabled,
    trailing_stop_activation_roi_pct: Number(settings.trailing_stop_activation_roi_pct),
    trailing_stop_callback_rate_pct: Number(settings.trailing_stop_callback_rate_pct),
    max_open_positions: settings.max_open_positions,
    max_open_positions_per_symbol: settings.max_open_positions_per_symbol,
    daily_max_loss_usdt: Number(settings.daily_max_loss_usdt),
    max_consecutive_losses: settings.max_consecutive_losses,
    min_liquidation_distance_pct: Number(settings.min_liquidation_distance_pct),
    max_slippage_pct: Number(settings.max_slippage_pct),
    post_trade_cooldown_minutes: settings.post_trade_cooldown_minutes,
    limit_entry_enabled: settings.limit_entry_enabled,
    limit_entry_offset_pct: Number(settings.limit_entry_offset_pct),
    limit_entry_timeout_minutes: settings.limit_entry_timeout_minutes,
    limit_entry_max_pending: settings.limit_entry_max_pending ?? 3,
  };
}

function toUpdatePayload(values: PositionSettingsFormValues): BotSettingsUpdate {
  return {
    margin_per_trade_usdt: String(values.margin_per_trade_usdt),
    leverage: values.leverage,
    take_profit_roi_pct: String(values.take_profit_roi_pct),
    stop_loss_roi_pct: String(values.stop_loss_roi_pct),
    loss_add_enabled: values.loss_add_enabled,
    loss_add_trigger_roi_pct: String(values.loss_add_trigger_roi_pct),
    loss_add_max_count: values.loss_add_max_count,
    trailing_stop_enabled: values.trailing_stop_enabled,
    trailing_stop_activation_roi_pct: String(values.trailing_stop_activation_roi_pct),
    trailing_stop_callback_rate_pct: String(values.trailing_stop_callback_rate_pct),
    max_open_positions: values.max_open_positions,
    max_open_positions_per_symbol: values.max_open_positions_per_symbol,
    daily_max_loss_usdt: String(values.daily_max_loss_usdt),
    max_consecutive_losses: values.max_consecutive_losses,
    min_liquidation_distance_pct: String(values.min_liquidation_distance_pct),
    max_slippage_pct: String(values.max_slippage_pct),
    post_trade_cooldown_minutes: values.post_trade_cooldown_minutes,
    limit_entry_enabled: values.limit_entry_enabled,
    limit_entry_offset_pct: String(values.limit_entry_offset_pct),
    limit_entry_timeout_minutes: values.limit_entry_timeout_minutes,
    limit_entry_max_pending: values.limit_entry_max_pending,
  };
}

export default function PozisyonAyarlariPage() {
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
  } = useForm<PositionSettingsFormValues>({ resolver: zodResolver(positionSettingsSchema) });

  React.useEffect(() => {
    if (settings) reset(toFormValues(settings));
  }, [settings, reset]);

  const updateMutation = useMutation({
    mutationFn: (values: PositionSettingsFormValues) => settingsApi.update(toUpdatePayload(values)),
    onSuccess: (updated) => {
      push({ title: "Pozisyon ayarlari kaydedildi", description: FIREBASE_SAVED_TOAST, variant: "success" });
      queryClient.setQueryData(["settings"], updated);
      reset(toFormValues(updated));
    },
    onError: (error) =>
      push({
        title: "Kaydedilemedi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  const resetMutation = useMutation({
    mutationFn: () => settingsApi.resetDefaults("position"),
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

  const onSubmit = (values: PositionSettingsFormValues) => updateMutation.mutate(values);
  const onInvalid = () =>
    push({
      title: "Form gecersiz",
      description: "Kirmizi isaretli alanlari kontrol edin.",
      variant: "error",
    });

  return (
    <div>
      <PageHeader
        title="Pozisyon Ayarlari"
        description={`Marjin, TP/SL, DCA, olta ve risk limitleri — mod: ${settings.mode.toUpperCase()}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ResetDefaultsButton
              scope="position"
              onReset={() => resetMutation.mutate()}
              isPending={resetMutation.isPending}
              disabled={updateMutation.isPending}
            />
            <Button
              onClick={handleSubmit(onSubmit, onInvalid)}
              disabled={!isDirty || updateMutation.isPending || resetMutation.isPending}
            >
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Kaydet
            </Button>
          </div>
        }
      />

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-border/80 bg-card/40 px-4 py-3 text-sm text-muted-foreground">
        <SlidersHorizontal className="h-4 w-4 shrink-0 text-primary" />
        <span>
          Tarama, sinyal filtreleri ve Telegram icin{" "}
          <Link href="/settings" className="font-medium text-primary underline-offset-2 hover:underline">
            Genel Ayarlar
          </Link>
        </span>
      </div>

      <form onSubmit={handleSubmit(onSubmit, onInvalid)} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SettingsSection title="Pozisyon Boyutlandirma" description="Islem basina teminat ve kaldirac">
          <SettingsField label="Islem Basina Teminat (USDT)" error={errors.margin_per_trade_usdt?.message}>
            <Input type="number" step="0.01" {...register("margin_per_trade_usdt")} />
          </SettingsField>
          <SettingsField label={`Kaldirac (1-${settings.max_allowed_leverage}x)`} error={errors.leverage?.message}>
            <Select
              value={String(watch("leverage") ?? settings.leverage)}
              onValueChange={(v) => setValue("leverage", Number(v), { shouldDirty: true })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Kaldirac secin" />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: settings.max_allowed_leverage }, (_, i) => i + 1).map((x) => (
                  <SelectItem key={x} value={String(x)}>
                    {x}x
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Kar Al / Zarar Durdur" description="ROI (teminat uzerinden) tabanli hedefler">
          <SettingsField label="Take-Profit ROI (%)" error={errors.take_profit_roi_pct?.message}>
            <Input type="number" step="0.1" {...register("take_profit_roi_pct")} />
          </SettingsField>
          <SettingsField label="Stop-Loss ROI (%) — nihai kapanis" error={errors.stop_loss_roi_pct?.message}>
            <Input type="number" step="0.1" {...register("stop_loss_roi_pct")} />
          </SettingsField>
          <div className="sm:col-span-2">
            <SettingsToggleField
              label="Zarar esiginde ekleme (DCA) aktif"
              checked={watch("loss_add_enabled")}
              onChange={(v) => setValue("loss_add_enabled", v, { shouldDirty: true })}
            />
          </div>
          <SettingsField label="Ekleme esigi ROI (%)" error={errors.loss_add_trigger_roi_pct?.message}>
            <Input type="number" step="0.1" {...register("loss_add_trigger_roi_pct")} disabled={!watch("loss_add_enabled")} />
          </SettingsField>
          <SettingsField label="Maks. ekleme sayisi" error={errors.loss_add_max_count?.message}>
            <Input type="number" step="1" {...register("loss_add_max_count")} disabled={!watch("loss_add_enabled")} />
          </SettingsField>
          <p className="sm:col-span-2 text-xs text-muted-foreground">
            Ornek: -{watch("loss_add_trigger_roi_pct") || "25"}% ROI&apos;de ekleme, -{watch("stop_loss_roi_pct") || "50"}% ROI&apos;de tamamen kapat.
          </p>
        </SettingsSection>

        <SettingsSection title="Trailing Stop" description="Karda iken zirveden geri cekilince otomatik cikis">
          <div className="sm:col-span-2">
            <SettingsToggleField
              label="Trailing stop aktif"
              checked={watch("trailing_stop_enabled")}
              onChange={(v) => setValue("trailing_stop_enabled", v, { shouldDirty: true })}
            />
          </div>
          <SettingsField label="Aktivasyon ROI (%)" error={errors.trailing_stop_activation_roi_pct?.message}>
            <Input type="number" step="0.1" {...register("trailing_stop_activation_roi_pct")} disabled={!watch("trailing_stop_enabled")} />
          </SettingsField>
          <SettingsField label="Geri cekilme orani (%)" error={errors.trailing_stop_callback_rate_pct?.message}>
            <Input type="number" step="0.1" {...register("trailing_stop_callback_rate_pct")} disabled={!watch("trailing_stop_enabled")} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Risk & Limitler" description="Acik pozisyon sayisi, gunluk zarar ve guvenlik mesafeleri">
          <SettingsField label="Maks. Acik Pozisyon (toplam)" error={errors.max_open_positions?.message}>
            <Input type="number" step="1" {...register("max_open_positions")} />
            <p className="mt-1 text-xs text-muted-foreground">
              Yalnizca dolmus (OPEN) pozisyonlar sayilir. Bekleyen olta limit emirleri bu limite dahil edilmez.
            </p>
          </SettingsField>
          <SettingsField label="Maks. Acik Pozisyon (sembol basina)" error={errors.max_open_positions_per_symbol?.message}>
            <Input type="number" step="1" {...register("max_open_positions_per_symbol")} />
          </SettingsField>
          <SettingsField label="Gunluk Maks. Zarar (USDT)" error={errors.daily_max_loss_usdt?.message}>
            <Input type="number" step="0.01" {...register("daily_max_loss_usdt")} />
          </SettingsField>
          <SettingsField label="Maks. Ardisik Zarar Sayisi" error={errors.max_consecutive_losses?.message}>
            <Input type="number" step="1" {...register("max_consecutive_losses")} />
          </SettingsField>
          <SettingsField label="Min. Likidasyon Uzakligi (%)" error={errors.min_liquidation_distance_pct?.message}>
            <Input type="number" step="0.1" {...register("min_liquidation_distance_pct")} />
          </SettingsField>
          <SettingsField label="Maks. Kayma (Slippage) (%)" error={errors.max_slippage_pct?.message}>
            <Input type="number" step="0.01" {...register("max_slippage_pct")} />
          </SettingsField>
          <SettingsField label="Islem Sonrasi Bekleme (dakika)" error={errors.post_trade_cooldown_minutes?.message}>
            <Input type="number" step="1" {...register("post_trade_cooldown_minutes")} />
          </SettingsField>
        </SettingsSection>

        <SettingsSection title="Olta (Limit Giris)" description="Market yerine limit emir ile giris">
          <div className="sm:col-span-2">
            <SettingsToggleField
              label="Olta limit modu aktif"
              checked={watch("limit_entry_enabled")}
              onChange={(v) => setValue("limit_entry_enabled", v, { shouldDirty: true })}
            />
          </div>
          <SettingsField label="Offset — piyasadan uzaklik (%)" error={errors.limit_entry_offset_pct?.message}>
            <Input type="number" step="0.01" {...register("limit_entry_offset_pct")} disabled={!watch("limit_entry_enabled")} />
          </SettingsField>
          <SettingsField label="Zaman asimi (dakika)" error={errors.limit_entry_timeout_minutes?.message}>
            <Input type="number" step="1" {...register("limit_entry_timeout_minutes")} disabled={!watch("limit_entry_enabled")} />
          </SettingsField>
          <SettingsField label="Maks. bekleyen olta emri" error={errors.limit_entry_max_pending?.message}>
            <Input type="number" step="1" {...register("limit_entry_max_pending")} disabled={!watch("limit_entry_enabled")} />
          </SettingsField>
          <p className="sm:col-span-2 text-xs text-muted-foreground">
            LONG: fiyatin %{watch("limit_entry_offset_pct") || "0"} altina limit. SHORT: ustune limit. Dolmazsa{" "}
            {watch("limit_entry_timeout_minutes") || "60"} dk sonra iptal. Ayni anda en fazla{" "}
            {watch("limit_entry_max_pending") || "3"} bekleyen olta emri olabilir; dolu pozisyon limitine sayilmaz.
          </p>
        </SettingsSection>
      </form>
    </div>
  );
}
