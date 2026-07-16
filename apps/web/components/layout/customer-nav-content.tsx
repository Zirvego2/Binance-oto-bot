"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot } from "lucide-react";

import { cn } from "@/lib/utils";
import { CUSTOMER_NAV_SECTIONS, type CustomerNavItem } from "@/components/layout/customer-nav";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  onNavigate,
  compact,
}: CustomerNavItem & { active: boolean; onNavigate?: () => void; compact?: boolean }) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cn(
        "group flex items-center gap-2 rounded-md font-medium transition-all",
        compact ? "px-2.5 py-2 text-sm" : "px-2.5 py-1.5 text-xs",
        active
          ? "bg-primary text-primary-foreground shadow-sm"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
      )}
    >
      <Icon
        className={cn(
          "shrink-0",
          compact ? "h-4 w-4" : "h-3.5 w-3.5",
          active ? "opacity-100" : "opacity-70 group-hover:opacity-100"
        )}
      />
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function CustomerNavBrand({ compact }: { compact?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2", compact ? "px-4 py-4" : "px-3 py-3")}>
      <div
        className={cn(
          "flex items-center justify-center rounded-lg bg-primary/15 text-primary shadow-sm",
          compact ? "h-9 w-9" : "h-8 w-8"
        )}
      >
        <Bot className={compact ? "h-5 w-5" : "h-4 w-4"} />
      </div>
      <div className="min-w-0">
        <p className={cn("truncate font-semibold tracking-tight text-primary", compact ? "text-sm" : "text-xs")}>
          {APP_NAME}
        </p>
        <p className="truncate text-[9px] uppercase tracking-wider text-muted-foreground">Musteri Paneli</p>
      </div>
    </div>
  );
}

export function CustomerNavContent({
  onNavigate,
  compact,
  showFooter = true,
}: {
  onNavigate?: () => void;
  compact?: boolean;
  showFooter?: boolean;
}) {
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname?.startsWith(`${href}/`);

  return (
    <>
      <nav className={cn("flex-1 overflow-y-auto scrollbar-thin", compact ? "space-y-4 px-3 py-3" : "space-y-3 px-2.5 py-2.5")}>
        {CUSTOMER_NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <p
              className={cn(
                "font-semibold uppercase tracking-wider text-muted-foreground",
                compact ? "mb-1.5 px-2 text-[10px]" : "mb-1 px-1.5 text-[9px]"
              )}
            >
              {section.title}
            </p>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLink key={item.href} {...item} active={isActive(item.href)} onNavigate={onNavigate} compact={compact} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {showFooter ? (
        <div className={cn("border-t border-border/60", compact ? "p-3" : "p-2.5")}>
          <div className="rounded-md border border-border/60 bg-muted/20 px-2 py-1.5">
            <p className="text-[11px] font-medium">{APP_NAME}</p>
            <p className="text-[9px] text-muted-foreground">{APP_TAGLINE}</p>
          </div>
        </div>
      ) : null}
    </>
  );
}
