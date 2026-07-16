"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, WifiOff, Clock, ShieldBan, CalendarX2 } from "lucide-react";

import { useCurrentAdmin } from "@/hooks/use-auth";
import { firebaseSignOut } from "@/lib/firebase-auth";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data, isLoading, error, refetch, isFetching } = useCurrentAdmin();
  const isUnauthorized = error instanceof ApiError && error.status === 401;
  const isForbidden = error instanceof ApiError && error.status === 403;
  const [isSigningOut, setIsSigningOut] = React.useState(false);

  React.useEffect(() => {
    if (data?.role === "platform_admin") {
      router.replace("/admin");
    }
  }, [data, router]);

  React.useEffect(() => {
    if (!isUnauthorized || isSigningOut) {
      return;
    }

    let cancelled = false;
    setIsSigningOut(true);

    (async () => {
      // HttpOnly oturum cookie'sini temizle; aksi halde middleware cookie
      // gorup /login'e ulasmayi engelleyebilir (dashboard <-> login dongusu).
      try {
        await firebaseSignOut();
      } catch {
        // Oturum zaten gecersiz olabilir; cookie silme yaniti yine de doner.
      }
      if (!cancelled) {
        window.location.replace("/login?next=/dashboard");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isUnauthorized, isSigningOut]);

  if (isLoading || isUnauthorized || isSigningOut) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        {isUnauthorized || isSigningOut ? (
          <p className="text-xs text-muted-foreground">Oturum sonlandirildi, giris sayfasina yonlendiriliyor...</p>
        ) : null}
      </div>
    );
  }

  if (data?.approval_status === "pending") {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-6 text-center">
            <Clock className="mx-auto h-8 w-8 text-amber-400" />
            <p className="font-medium">Hesabiniz onay bekliyor</p>
            <p className="text-sm text-muted-foreground">
              Kaydiniz alindi. Yonetici onayindan sonra panele erisebilirsiniz. Onay sonrasi tekrar giris yapin.
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void firebaseSignOut().then(() => {
                  window.location.replace("/login");
                });
              }}
            >
              Cikis yap
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (data?.approval_status === "blocked") {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-6 text-center">
            <ShieldBan className="mx-auto h-8 w-8 text-destructive" />
            <p className="font-medium">Hesabiniz engellendi</p>
            <p className="text-sm text-muted-foreground">Destek ile iletisime gecin.</p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void firebaseSignOut().then(() => {
                  window.location.replace("/login");
                });
              }}
            >
              Cikis yap
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const membershipExpired = data?.membership_active === false;

  if (membershipExpired) {
    return (
      <div className="flex h-screen items-center justify-center p-4">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-6 text-center">
            <CalendarX2 className="mx-auto h-8 w-8 text-amber-400" />
            <p className="font-medium">Uyelik suresi doldu</p>
            <p className="text-sm text-muted-foreground">
              Hesabinizin kullanim suresi{" "}
              {new Date(data.membership_expires_at!).toLocaleDateString("tr-TR")} tarihinde sona erdi. Yenilemek icin
              yonetici ile iletisime gecin.
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void firebaseSignOut().then(() => {
                  window.location.replace("/login");
                });
              }}
            >
              Cikis yap
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isForbidden) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-2 p-4 text-center">
        <ShieldBan className="h-8 w-8 text-destructive" />
        <p className="text-sm font-medium">Panele erisim yetkiniz yok</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          {error instanceof ApiError ? error.message : "Hesap durumunuz panel erisimine uygun degil."}
        </p>
      </div>
    );
  }

  // Ag hatasi / backend gecici olarak erisilemez
  if (error || !data) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
        <WifiOff className="h-8 w-8 text-destructive" />
        <p className="text-sm font-medium text-foreground">Sunucuya baglanilamadi</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          API servisine erisilemedi. Backend servisinin calisir durumda oldugundan emin olun ve yeniden deneyin.
        </p>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Yeniden dene
          </Button>
          <Button size="sm" variant="secondary" onClick={() => router.replace("/login")}>
            Giris sayfasina git
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
