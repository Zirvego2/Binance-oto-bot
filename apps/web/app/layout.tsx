import type { Metadata, Viewport } from "next";

import { QueryProvider } from "@/components/providers/query-provider";
import { ToastProvider } from "@/components/ui/toast-provider";
import { APP_DESCRIPTION, APP_PAGE_TITLE } from "@/lib/branding";

import "./globals.css";

export const metadata: Metadata = {
  title: APP_PAGE_TITLE,
  description: APP_DESCRIPTION,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0e17",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className="dark">
      <body>
        <QueryProvider>
          <ToastProvider>{children}</ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
