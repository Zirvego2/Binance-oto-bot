"use client";

import { CustomerNavBrand, CustomerNavContent } from "@/components/layout/customer-nav-content";

export function Sidebar() {
  return (
    <aside className="hidden h-full min-h-0 w-52 shrink-0 flex-col border-r border-border/80 bg-card/95 backdrop-blur-sm md:flex">
      <div className="shrink-0 border-b border-border/60">
        <CustomerNavBrand />
      </div>
      <div className="flex min-h-0 flex-1 flex-col">
        <CustomerNavContent />
      </div>
    </aside>
  );
}
