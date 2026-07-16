"use client";

import * as React from "react";

import { MobileBottomNav, MobileNavDrawer } from "@/components/layout/mobile-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const openMenu = React.useCallback(() => setMobileOpen(true), []);
  const toggleMenu = React.useCallback(() => setMobileOpen((prev) => !prev), []);

  return (
    <>
      <MobileNavDrawer open={mobileOpen} onOpenChange={setMobileOpen} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Topbar mobileMenuOpen={mobileOpen} onMobileMenuToggle={toggleMenu} />
          <main className="customer-panel min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3 pb-[calc(3.75rem+env(safe-area-inset-bottom))] md:p-4 md:pb-4 scrollbar-thin">
            {children}
          </main>
          <MobileBottomNav open={mobileOpen} onOpenMenu={openMenu} />
        </div>
      </div>
    </>
  );
}
