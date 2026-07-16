"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { MOBILE_BOTTOM_NAV } from "@/components/layout/customer-nav";
import { CustomerNavBrand, CustomerNavContent } from "@/components/layout/customer-nav-content";

export function MobileMenuButton({
  open,
  onClick,
  className,
}: {
  open: boolean;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? "Menuyu kapat" : "Menuyu ac"}
      aria-expanded={open}
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border/80 bg-card text-foreground transition hover:bg-muted/60 md:hidden",
        className
      )}
    >
      {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
    </button>
  );
}

export function MobileNavDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const pathname = usePathname();

  React.useEffect(() => {
    onOpenChange(false);
  }, [pathname, onOpenChange]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-[60] bg-black/60 backdrop-blur-[1px] transition-opacity md:hidden",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={() => onOpenChange(false)}
        aria-hidden={!open}
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] flex w-[min(88vw,300px)] flex-col border-r border-border/80 bg-card shadow-2xl transition-transform duration-300 ease-out md:hidden",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-hidden={!open}
      >
        <div className="flex items-center justify-between border-b border-border/60 pr-2">
          <CustomerNavBrand compact />
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="mr-2 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            aria-label="Menuyu kapat"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <CustomerNavContent compact onNavigate={() => onOpenChange(false)} />
      </aside>
    </>
  );
}

export function MobileBottomNav({
  open,
  onOpenMenu,
}: {
  open: boolean;
  onOpenMenu: () => void;
}) {
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname?.startsWith(`${href}/`);

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 border-t border-border/80 bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
      aria-label="Mobil alt menu"
    >
      <div className="grid h-14 grid-cols-5">
        {MOBILE_BOTTOM_NAV.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className={cn("h-4 w-4", active && "scale-110")} />
              <span className="truncate">{item.shortLabel ?? item.label}</span>
            </Link>
          );
        })}

        <button
          type="button"
          onClick={onOpenMenu}
          className={cn(
            "flex flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-medium transition-colors",
            open ? "text-primary" : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Menu className="h-4 w-4" />
          <span>Menu</span>
        </button>
      </div>
    </nav>
  );
}
