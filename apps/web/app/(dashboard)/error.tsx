"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Panel hatasi:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 p-4 text-center">
      <AlertTriangle className="h-8 w-8 text-destructive" />
      <p className="text-sm font-medium text-foreground">Panel yuklenemedi</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        {error.message || "Beklenmeyen bir hata olustu."} Sayfayi yenileyin veya birkac saniye sonra tekrar deneyin.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button size="sm" onClick={() => reset()}>
          Yeniden dene
        </Button>
        <Button size="sm" variant="secondary" onClick={() => window.location.assign("/dashboard")}>
          Panele don
        </Button>
      </div>
    </div>
  );
}
