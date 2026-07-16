"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { botApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast-provider";

const LIVE_MODE_CONFIRMATION = "CANLI FUTURES İŞLEMİNİ AÇ";

function ControlRow({
  label,
  description,
  checked,
  disabled,
  pending,
  onCheckedChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  disabled?: boolean;
  pending?: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="min-w-0 flex-1">
        <Label className="text-base font-medium">{label}</Label>
        {description ? <p className="mt-0.5 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {pending ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
        <Switch checked={checked} disabled={disabled || pending} onCheckedChange={onCheckedChange} />
      </div>
    </div>
  );
}

export default function BotControlPage() {
  const { push } = useToast();
  const queryClient = useQueryClient();
  const { data: status, isLoading } = useQuery({
    queryKey: ["bot", "status"],
    queryFn: botApi.status,
    refetchInterval: 5_000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["bot"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["settings"] });
  };

  const startMutation = useMutation({
    mutationFn: botApi.start,
    onSuccess: () => {
      push({ title: "Bot acildi", variant: "success" });
      invalidate();
    },
    onError: (error) =>
      push({
        title: "Bot acilamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  const stopMutation = useMutation({
    mutationFn: botApi.stop,
    onSuccess: () => {
      push({ title: "Bot kapandi", variant: "info" });
      invalidate();
    },
    onError: (error) =>
      push({
        title: "Bot kapatilamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  const changeModeMutation = useMutation({
    mutationFn: (targetMode: "demo" | "live") =>
      botApi.changeMode(
        targetMode,
        targetMode === "live" ? LIVE_MODE_CONFIRMATION : null,
        targetMode === "live",
      ),
    onSuccess: (result) => {
      push({ title: result.message, variant: "success" });
      invalidate();
    },
    onError: (error) => {
      const problems =
        error instanceof ApiError && typeof error.errors === "object" && error.errors !== null
          ? (error.errors as { detail?: { problems?: string[] } }).detail?.problems
          : undefined;
      push({
        title: "Mod degistirilemedi",
        description: problems?.length ? problems.join(" | ") : error instanceof ApiError ? error.message : undefined,
        variant: "error",
      });
    },
  });

  const botOn = Boolean(status?.bot_enabled || status?.run_state === "RUNNING");
  const mode = status?.mode ?? "demo";
  const isDemo = mode === "demo";
  const isLive = mode === "live";
  const modeBusy = changeModeMutation.isPending;
  const botBusy = startMutation.isPending || stopMutation.isPending;
  const mustStopForMode = botOn;

  const handleBotToggle = (checked: boolean) => {
    if (checked) startMutation.mutate();
    else stopMutation.mutate();
  };

  const handleDemoToggle = (checked: boolean) => {
    if (checked && !isDemo) changeModeMutation.mutate("demo");
    else if (!checked && isDemo) changeModeMutation.mutate("live");
  };

  const handleLiveToggle = (checked: boolean) => {
    if (checked && !isLive) changeModeMutation.mutate("live");
    else if (!checked && isLive) changeModeMutation.mutate("demo");
  };

  return (
    <div>
      <PageHeader title="Bot Kontrol" description="Botu acin veya kapatin; demo veya canli mod secin" />

      <Card className="max-w-lg">
        <CardContent className="divide-y px-6">
          <ControlRow
            label="Bot"
            description={botOn ? "Calisiyor" : "Kapali"}
            checked={botOn}
            pending={botBusy}
            disabled={isLoading}
            onCheckedChange={handleBotToggle}
          />

          <ControlRow
            label="Demo Mod"
            description={mustStopForMode ? "Mod degistirmek icin once botu kapatın" : "Testnet / demo hesap"}
            checked={isDemo}
            pending={modeBusy}
            disabled={isLoading || mustStopForMode}
            onCheckedChange={handleDemoToggle}
          />

          <ControlRow
            label="Canli Mod"
            description={mustStopForMode ? "Mod degistirmek icin once botu kapatın" : "Gercek futures islemleri"}
            checked={isLive}
            pending={modeBusy}
            disabled={isLoading || mustStopForMode}
            onCheckedChange={handleLiveToggle}
          />
        </CardContent>
      </Card>

      {status?.safe_mode_reason ? (
        <p className="mt-4 max-w-lg rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {status.safe_mode_reason}
        </p>
      ) : null}
    </div>
  );
}
