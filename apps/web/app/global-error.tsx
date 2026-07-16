"use client";

import { useEffect } from "react";

/**
 * Kok layout'un KENDISI hata firlatirsa devreye giren son savunma hatti.
 * (``app/error.tsx`` normal sayfa hatalarini yakalar; bu dosya SADECE
 * layout/root seviyesindeki hatalar icin gerekir ve kendi <html>/<body>
 * etiketlerini icermek ZORUNDADIR.)
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Kritik uygulama hatasi:", error);
  }, [error]);

  return (
    <html lang="tr" className="dark">
      <body>
        <div
          style={{
            display: "flex",
            height: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            padding: "1rem",
            textAlign: "center",
            background: "#0a0a0f",
            color: "#e5e7eb",
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <p style={{ fontSize: "0.875rem", fontWeight: 500 }}>Kritik bir hata olustu</p>
          <p style={{ maxWidth: "24rem", fontSize: "0.75rem", color: "#9ca3af" }}>
            {error.message || "Uygulama yuklenemedi."} Sayfayi yenileyin veya backend servislerinin calistigini
            kontrol edin.
          </p>
          <button
            onClick={() => reset()}
            style={{
              borderRadius: "0.375rem",
              background: "#6366f1",
              color: "white",
              padding: "0.5rem 1rem",
              fontSize: "0.875rem",
              border: "none",
              cursor: "pointer",
            }}
          >
            Yeniden dene
          </button>
        </div>
      </body>
    </html>
  );
}
