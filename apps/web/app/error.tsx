"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Next.js App Router hata siniri (error boundary): bu segment altinda
 * beklenmeyen bir hata firlatilirsa (network hatasi, render hatasi vb.)
 * kullaniciya COKUS/BOS SAYFA yerine anlamli bir mesaj + "yeniden dene"
 * secenegi gosterilir.
 */
export default function GlobalErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Uygulama hatasi:", error);
  }, [error]);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 p-4 text-center">
      <AlertTriangle className="h-8 w-8 text-destructive" />
      <p className="text-sm font-medium text-foreground">Beklenmeyen bir hata olustu</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        {error.message || "Sayfa yuklenirken bir sorun olustu."} Backend servisinin calistigindan emin olup yeniden
        deneyebilirsiniz.
      </p>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => reset()}>
          Yeniden dene
        </Button>
        <Button size="sm" variant="secondary" onClick={() => (window.location.href = "/dashboard")}>
          Panele don
        </Button>
      </div>
    </div>
  );
}
