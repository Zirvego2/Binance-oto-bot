"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldAlert, WifiOff } from "lucide-react";

import { useCurrentAdmin } from "@/hooks/use-auth";
import { authApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

export function PlatformAdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data, isLoading, error, refetch, isFetching } = useCurrentAdmin();
  const isUnauthorized = error instanceof ApiError && error.status === 401;
  const isForbidden = error instanceof ApiError && error.status === 403;

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isUnauthorized) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
        <ShieldAlert className="h-8 w-8 text-primary" />
        <p className="text-sm font-medium">Platform yonetici oturumu gerekli</p>
        <Button size="sm" onClick={() => router.replace("/admin/login")}>
          Giris sayfasina git
        </Button>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
        <WifiOff className="h-8 w-8 text-destructive" />
        <p className="text-sm font-medium">Sunucuya baglanilamadi</p>
        <Button size="sm" onClick={() => refetch()} disabled={isFetching}>
          Yeniden dene
        </Button>
      </div>
    );
  }

  if (data.role !== "platform_admin") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
        <ShieldAlert className="h-8 w-8 text-destructive" />
        <p className="text-sm font-medium">Bu alana erisim yetkiniz yok</p>
        <Button size="sm" variant="secondary" onClick={() => router.replace("/dashboard")}>
          Musteri paneline don
        </Button>
      </div>
    );
  }

  if (isForbidden) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
        <ShieldAlert className="h-8 w-8 text-destructive" />
        <p className="text-sm font-medium">Erisim reddedildi</p>
      </div>
    );
  }

  return <>{children}</>;
}

export function usePlatformAdminLogout() {
  return React.useCallback(async () => {
    await authApi.logout();
    window.location.replace("/admin/login");
  }, []);
}
