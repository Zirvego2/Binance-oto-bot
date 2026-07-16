"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  KeyRound,
  Link2,
  Loader2,
  Lock,
  Mail,
  MessageCircle,
  Save,
  Shield,
  ShieldCheck,
  Sparkles,
  Unlock,
  User,
  XCircle,
} from "lucide-react";

import { profileApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { cn, formatDateTime } from "@/lib/utils";
import type { ProfileConnectionsSummary, ProfileOut } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast-provider";
import { SettingsSection, SettingsToggleField } from "@/components/settings/settings-form-parts";

function profileInitials(profile: ProfileOut | undefined) {
  if (!profile) return "?";
  const name = profile.full_name?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      const first = parts[0] ?? "";
      const last = parts[parts.length - 1] ?? "";
      return `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();
    }
    return (parts[0] ?? "").slice(0, 2).toUpperCase();
  }
  return profile.email.slice(0, 2).toUpperCase();
}

function sourceLabel(source: string | null) {
  if (!source) return "—";
  if (source === "profile" || source === "firebase") return "Profil";
  if (source === "env") return "Sunucu";
  return source;
}

export default function ProfilePage() {
  const { push } = useToast();
  const queryClient = useQueryClient();

  const [unlockPassword, setUnlockPassword] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [binanceApiKey, setBinanceApiKey] = React.useState("");
  const [binanceApiSecret, setBinanceApiSecret] = React.useState("");
  const [telegramToken, setTelegramToken] = React.useState("");
  const [telegramChatId, setTelegramChatId] = React.useState("");
  const [telegramEnabled, setTelegramEnabled] = React.useState(false);
  const [openaiApiKey, setOpenaiApiKey] = React.useState("");

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
  });

  const unlocked = profile?.connections_unlocked ?? false;

  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ["profile", "connections"],
    queryFn: profileApi.getConnections,
    enabled: unlocked,
  });

  React.useEffect(() => {
    if (profile?.full_name !== undefined) setFullName(profile.full_name ?? "");
  }, [profile?.full_name]);

  React.useEffect(() => {
    if (!connections) return;
    setTelegramChatId(connections.telegram_chat_id ?? "");
    setTelegramEnabled(connections.telegram_notifications_enabled);
  }, [connections]);

  const unlockMutation = useMutation({
    mutationFn: () => profileApi.unlock(unlockPassword),
    onSuccess: (res) => {
      push({
        title: "Entegrasyon paneli acildi",
        description: `${Math.round(res.expires_in_seconds / 60)} dakika gecerli`,
        variant: "success",
      });
      setUnlockPassword("");
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      queryClient.invalidateQueries({ queryKey: ["profile", "connections"] });
    },
    onError: (error) =>
      push({
        title: "Dogrulama basarisiz",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  const lockMutation = useMutation({
    mutationFn: profileApi.lock,
    onSuccess: () => {
      push({ title: "Entegrasyon paneli kilitlendi", variant: "info" });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      queryClient.removeQueries({ queryKey: ["profile", "connections"] });
    },
  });

  const saveNameMutation = useMutation({
    mutationFn: () => profileApi.updateFullName(fullName.trim() || null),
    onSuccess: () => {
      push({ title: "Profil guncellendi", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) =>
      push({ title: "Kayit basarisiz", description: error instanceof ApiError ? error.message : undefined, variant: "error" }),
  });

  const saveConnectionsMutation = useMutation({
    mutationFn: () =>
      profileApi.saveConnections({
        binance_api_key: binanceApiKey.trim() ? binanceApiKey.trim() : undefined,
        binance_api_secret: binanceApiSecret.trim() ? binanceApiSecret.trim() : undefined,
        telegram_bot_token: telegramToken.trim() ? telegramToken.trim() : undefined,
        telegram_chat_id: telegramChatId.trim() || "",
        telegram_notifications_enabled: telegramEnabled,
        openai_api_key: openaiApiKey.trim() ? openaiApiKey.trim() : undefined,
      }),
    onSuccess: () => {
      push({
        title: "Entegrasyonlar kaydedildi",
        description: "Worker yeniden baslatildiginda yeni anahtarlar aktif olur.",
        variant: "success",
      });
      setBinanceApiKey("");
      setBinanceApiSecret("");
      setTelegramToken("");
      setOpenaiApiKey("");
      queryClient.invalidateQueries({ queryKey: ["profile", "connections"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      queryClient.invalidateQueries({ queryKey: ["binance"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) =>
      push({ title: "Kayit basarisiz", description: error instanceof ApiError ? error.message : undefined, variant: "error" }),
  });

  const testBinanceMutation = useMutation({
    mutationFn: profileApi.testBinance,
    onSuccess: (res) => {
      push({
        title: res.ok ? "Binance baglantisi dogrulandi" : "Binance testi basarisiz",
        description: res.message,
        variant: res.ok ? "success" : "error",
      });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        queryClient.invalidateQueries({ queryKey: ["profile"] });
        queryClient.invalidateQueries({ queryKey: ["binance"] });
      }
    },
  });

  const testTelegramMutation = useMutation({
    mutationFn: profileApi.testTelegram,
    onSuccess: (res) =>
      push({
        title: res.ok ? "Telegram testi basarili" : "Telegram testi basarisiz",
        description: res.message,
        variant: res.ok ? "success" : "error",
      }),
  });

  const discoverTelegramChatIdMutation = useMutation({
    mutationFn: () =>
      profileApi.discoverTelegramChatId(telegramToken.trim() ? telegramToken.trim() : undefined),
    onSuccess: (res) => {
      if (res.ok && res.chat_id) {
        setTelegramChatId(res.chat_id);
      }
      push({
        title: res.ok ? "Chat ID bulundu" : "Chat ID alinamadi",
        description: res.message,
        variant: res.ok ? "success" : "error",
      });
    },
    onError: (error) =>
      push({
        title: "Chat ID alinamadi",
        description: error instanceof ApiError ? error.message : undefined,
        variant: "error",
      }),
  });

  const canDiscoverTelegramChatId =
    Boolean(telegramToken.trim()) || Boolean(connections?.telegram_bot_token_masked);

  if (profileLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const configuredCount = [
    profile?.connections_summary.binance_configured,
    profile?.connections_summary.telegram_configured,
    profile?.connections_summary.openai_configured,
  ].filter(Boolean).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <ProfileHero profile={profile} configuredCount={configuredCount} unlocked={unlocked} />

      <Tabs defaultValue="account" className="space-y-4">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 p-1 sm:w-auto sm:inline-flex">
          <TabsTrigger value="account" className="gap-2 px-4 py-2">
            <User className="h-4 w-4" />
            Hesap Bilgileri
          </TabsTrigger>
          <TabsTrigger value="integrations" className="gap-2 px-4 py-2">
            <Link2 className="h-4 w-4" />
            API Entegrasyonlari
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account" className="mt-0 space-y-4">
          <Card className="border-border/80 shadow-sm">
            <CardHeader className="border-b border-border/60 bg-muted/20 pb-4">
              <CardTitle className="text-base font-semibold">Kimlik Bilgileri</CardTitle>
              <CardDescription>Kurumsal hesap profiliniz ve iletisim bilgileriniz</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-5 pt-6 sm:grid-cols-2">
              <FormField label="E-posta adresi" hint="Giris ve bildirimler bu adrese gonderilir">
                <Input value={profile?.email ?? ""} readOnly disabled className="bg-muted/30" />
              </FormField>
              <FormField label="Ad Soyad" hint="Panelde gorunen isim">
                <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ornek: Ali Yilmaz" />
              </FormField>
              <FormField label="Son oturum" hint="Son basarili giris zamani">
                <div className="flex h-9 items-center rounded-md border border-border/60 bg-muted/20 px-3 text-sm text-muted-foreground">
                  {formatDateTime(profile?.last_login_at) || "—"}
                </div>
              </FormField>
              <FormField label="Hesap tipi" hint="Platform erisim seviyesi">
                <div className="flex h-9 items-center gap-2">
                  <Badge variant="outline" className="font-normal capitalize">
                    {profile?.account_type ?? "customer"}
                  </Badge>
                </div>
              </FormField>
              <div className="sm:col-span-2 flex justify-end border-t border-border/60 pt-4">
                <Button onClick={() => saveNameMutation.mutate()} disabled={saveNameMutation.isPending}>
                  {saveNameMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Degisiklikleri Kaydet
                </Button>
              </div>
            </CardContent>
          </Card>

          {profile?.connections_summary && (
            <Card className="border-border/80 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold">Entegrasyon Ozeti</CardTitle>
                <CardDescription>Bagli servislerin genel durumu</CardDescription>
              </CardHeader>
              <CardContent>
                <IntegrationOverviewGrid summary={profile.connections_summary} />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="integrations" className="mt-0 space-y-4">
          {!unlocked ? (
            <Card className="overflow-hidden border-primary/20 shadow-sm">
              <div className="grid md:grid-cols-5">
                <div className="flex flex-col justify-center border-b border-border/60 bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-6 md:col-span-2 md:border-b-0 md:border-r">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15 text-primary">
                    <Shield className="h-6 w-6" />
                  </div>
                  <h2 className="text-lg font-semibold tracking-tight">Guvenli Erisim</h2>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    API anahtarlari ve hassas entegrasyon bilgileri sifre korumasi altindadir. Devam etmek icin profil
                    sifrenizi girin.
                  </p>
                </div>
                <div className="p-6 md:col-span-3">
                  <div className="mx-auto max-w-sm space-y-4">
                    <FormField label="Profil sifresi" hint="Hesap sifreniz ile ayni">
                      <Input
                        type="password"
                        value={unlockPassword}
                        onChange={(e) => setUnlockPassword(e.target.value)}
                        placeholder="••••••••"
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && unlockPassword) unlockMutation.mutate();
                        }}
                      />
                    </FormField>
                    <Button className="w-full" onClick={() => unlockMutation.mutate()} disabled={!unlockPassword || unlockMutation.isPending}>
                      {unlockMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
                      Entegrasyon Panelini Ac
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
                  <ShieldCheck className="h-4 w-4 shrink-0" />
                  <span>Guvenli oturum acik — API anahtarlari goruntulenebilir ve duzenlenebilir</span>
                </div>
                <Button variant="outline" size="sm" onClick={() => lockMutation.mutate()} disabled={lockMutation.isPending}>
                  <Lock className="h-4 w-4" />
                  Oturumu Kapat
                </Button>
              </div>

              {connectionsLoading ? (
                <div className="flex justify-center py-16">
                  <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  <SettingsSection
                    title="Binance Futures"
                    description="USDS-M Futures API baglantisi. Withdraw izni kapali olmalidir."
                  >
                    <IntegrationStatus ok={connections?.binance_configured ?? false} configuredLabel="Bagli" missingLabel="Yapilandirilmamis" />
                    <div className="sm:col-span-2 rounded-md border border-border/60 bg-muted/15 px-3 py-2 text-xs text-muted-foreground">
                      Kaynak: <span className="font-medium text-foreground">{sourceLabel(connections?.binance_source ?? null)}</span>
                      {connections?.binance_api_key_masked ? (
                        <>
                          {" "}
                          · Key: <span className="font-mono">{connections.binance_api_key_masked}</span>
                        </>
                      ) : null}
                    </div>
                    <FormField label="API Key">
                      <Input
                        type="password"
                        value={binanceApiKey}
                        onChange={(e) => setBinanceApiKey(e.target.value)}
                        placeholder={connections?.binance_api_key_masked ?? "Binance API Key"}
                        autoComplete="off"
                      />
                    </FormField>
                    <FormField label="API Secret">
                      <Input
                        type="password"
                        value={binanceApiSecret}
                        onChange={(e) => setBinanceApiSecret(e.target.value)}
                        placeholder={connections?.binance_api_secret_set ? "••••••••••••" : "Binance API Secret"}
                        autoComplete="off"
                      />
                    </FormField>
                    <div className="sm:col-span-2">
                      <Button variant="outline" size="sm" onClick={() => testBinanceMutation.mutate()} disabled={testBinanceMutation.isPending}>
                        {testBinanceMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                        Baglanti Testi
                      </Button>
                    </div>
                  </SettingsSection>

                  <SettingsSection title="Telegram Bildirimleri" description="Islem ve pozisyon bildirimleri icin bot yapilandirmasi">
                    <IntegrationStatus ok={connections?.telegram_configured ?? false} configuredLabel="Aktif" missingLabel="Eksik" />
                    <div className="sm:col-span-2">
                      <SettingsToggleField
                        label="Bildirimleri etkinlestir"
                        description="Pozisyon acilis/kapanis mesajlari"
                        checked={telegramEnabled}
                        onChange={setTelegramEnabled}
                      />
                    </div>
                    <FormField label="Bot Token">
                      <Input
                        type="password"
                        value={telegramToken}
                        onChange={(e) => setTelegramToken(e.target.value)}
                        placeholder={connections?.telegram_bot_token_masked ?? "123456:ABC..."}
                        autoComplete="off"
                      />
                    </FormField>
                    <FormField label="Chat ID">
                      <div className="flex gap-2">
                        <Input
                          className="flex-1"
                          value={telegramChatId}
                          onChange={(e) => setTelegramChatId(e.target.value)}
                          placeholder="-1001234567890"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="shrink-0"
                          disabled={!canDiscoverTelegramChatId || discoverTelegramChatIdMutation.isPending}
                          onClick={() => discoverTelegramChatIdMutation.mutate()}
                        >
                          {discoverTelegramChatIdMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Chat ID Cek"
                          )}
                        </Button>
                      </div>
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        Once Telegram&apos;da bota /start yazin, sonra &quot;Chat ID Cek&quot; tusuna basin.
                      </p>
                    </FormField>
                    <div className="sm:col-span-2">
                      <Button variant="outline" size="sm" onClick={() => testTelegramMutation.mutate()} disabled={testTelegramMutation.isPending}>
                        {testTelegramMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
                        Test Mesaji Gonder
                      </Button>
                    </div>
                  </SettingsSection>

                  <SettingsSection title="OpenAI" description="Yapay zeka destekli sinyal aciklamalari (opsiyonel)">
                    <IntegrationStatus ok={connections?.openai_configured ?? false} configuredLabel="Tanimli" missingLabel="Opsiyonel" />
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label className="flex items-center gap-1.5 text-sm">
                        <Sparkles className="h-3.5 w-3.5 text-primary" />
                        API Key
                      </Label>
                      <Input
                        type="password"
                        value={openaiApiKey}
                        onChange={(e) => setOpenaiApiKey(e.target.value)}
                        placeholder={connections?.openai_api_key_masked ?? "sk-..."}
                        autoComplete="off"
                      />
                    </div>
                  </SettingsSection>

                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/80 bg-card px-4 py-4 shadow-sm">
                    <Button onClick={() => saveConnectionsMutation.mutate()} disabled={saveConnectionsMutation.isPending}>
                      {saveConnectionsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                      Tum Entegrasyonlari Kaydet
                    </Button>
                  </div>

                  <SecurityNotice />
                </>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ProfileHero({
  profile,
  configuredCount,
  unlocked,
}: {
  profile: ProfileOut | undefined;
  configuredCount: number;
  unlocked: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm">
      <div className="bg-gradient-to-r from-primary/8 via-primary/4 to-transparent px-6 py-8 sm:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-primary/20 bg-background text-lg font-semibold text-primary shadow-sm">
              {profileInitials(profile)}
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Hesap Profili</p>
              <h1 className="mt-0.5 text-xl font-semibold tracking-tight sm:text-2xl">
                {profile?.full_name?.trim() || "Kullanici"}
              </h1>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Mail className="h-3.5 w-3.5" />
                {profile?.email}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="secondary" className="font-normal">
                  <Building2 className="mr-1 h-3 w-3" />
                  Kurumsal Hesap
                </Badge>
                <Badge variant={unlocked ? "success" : "outline"} className="font-normal">
                  {unlocked ? "Entegrasyon acik" : "Entegrasyon kilitli"}
                </Badge>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[220px]">
            <HeroStat label="Entegrasyon" value={`${configuredCount}/3`} />
            <HeroStat label="Son giris" value={profile?.last_login_at ? (formatDateTime(profile.last_login_at).split(" ")[0] ?? "—") : "—"} small />
          </div>
        </div>
      </div>
    </div>
  );
}

function HeroStat({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/80 px-3 py-2.5 backdrop-blur-sm">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-0.5 font-semibold tabular-nums text-foreground", small ? "text-sm" : "text-lg")}>{value}</p>
    </div>
  );
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm font-medium">{label}</Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function IntegrationOverviewGrid({ summary }: { summary: ProfileConnectionsSummary }) {
  const items = [
    { key: "binance", label: "Binance Futures", ok: summary.binance_configured, source: summary.binance_source, icon: Link2 },
    { key: "telegram", label: "Telegram", ok: summary.telegram_configured, source: summary.telegram_source, icon: MessageCircle },
    { key: "openai", label: "OpenAI", ok: summary.openai_configured, source: summary.openai_source, icon: Sparkles },
  ] as const;

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map(({ key, label, ok, source, icon: Icon }) => (
        <div
          key={key}
          className={cn(
            "flex flex-col gap-3 rounded-lg border p-4 transition-colors",
            ok ? "border-emerald-500/25 bg-emerald-500/5" : "border-border/70 bg-muted/10"
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-background shadow-sm">
              <Icon className="h-4 w-4 text-primary" />
            </div>
            {ok ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <XCircle className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium">{label}</p>
            <p className={cn("text-xs", ok ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground")}>
              {ok ? "Yapilandirildi" : "Eksik"}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">Kaynak: {sourceLabel(source)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function IntegrationStatus({ ok, configuredLabel, missingLabel }: { ok: boolean; configuredLabel: string; missingLabel: string }) {
  return (
    <div className="flex items-center gap-2 sm:col-span-2">
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" /> : <XCircle className="h-4 w-4 text-muted-foreground" />}
      <Badge variant={ok ? "success" : "secondary"}>{ok ? configuredLabel : missingLabel}</Badge>
    </div>
  );
}

function SecurityNotice() {
  return (
    <div className="flex gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm">
      <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <div className="space-y-1 text-muted-foreground">
        <p className="font-medium text-foreground">Guvenlik Politikasi</p>
        <p>
          API anahtarlari sifreli olarak saklanir. Binance anahtarinda yalnizca Futures islem izni verin; para cekme
          (withdraw) iznini asla acmayin. Degisikliklerden sonra worker servisini yeniden baslatin.
        </p>
      </div>
    </div>
  );
}
