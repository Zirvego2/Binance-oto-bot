"use client";

import { Loader2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

export type SettingsResetScope = "general" | "position" | "impulse" | "all";

type ResetDefaultsButtonProps = {
  scope: SettingsResetScope;
  onReset: () => void;
  isPending?: boolean;
  disabled?: boolean;
  label?: string;
};

const CONFIRM_MESSAGES: Record<SettingsResetScope, string> = {
  general:
    "Genel ayarlar varsayilan degerlere dondurulecek. Mod ve bot acik/kapali durumu degismez. Devam edilsin mi?",
  position:
    "Pozisyon ayarlari varsayilan degerlere dondurulecek. Mod ve bot acik/kapali durumu degismez. Devam edilsin mi?",
  impulse:
    "BTC Impuls ayarlari varsayilan degerlere dondurulecek. Devam edilsin mi?",
  all: "Tum panel ayarlari (genel + pozisyon + impuls) varsayilan degerlere dondurulecek. Mod ve bot durumu degismez. Devam edilsin mi?",
};

export function ResetDefaultsButton({
  scope,
  onReset,
  isPending = false,
  disabled = false,
  label = "Varsayilan ayarlara don",
}: ResetDefaultsButtonProps) {
  const handleClick = () => {
    if (!window.confirm(CONFIRM_MESSAGES[scope])) return;
    onReset();
  };

  return (
    <Button type="button" variant="outline" onClick={handleClick} disabled={disabled || isPending}>
      {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
      {label}
    </Button>
  );
}

export const FIREBASE_SAVED_TOAST = "Musteri ayarlari Firebase'e kaydedildi.";
