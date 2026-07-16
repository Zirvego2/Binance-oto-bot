"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  History,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Shield,
  Sparkles,
  TrendingUp,
  Users,
  CalendarClock,
  type LucideIcon,
  Wallet,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { usePlatformAdminLogout } from "@/components/layout/platform-admin-guard";
import { Button } from "@/components/ui/button";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
};

type NavSection = { title: string; items: NavItem[] };

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Yonetim",
    items: [
      { href: "/admin", label: "Platform Ozeti", icon: LayoutDashboard, exact: true },
      { href: "/admin/customers", label: "Musteri Yonetimi", icon: Users },
      { href: "/admin/memberships", label: "Uyelik Yonetimi", icon: CalendarClock },
      { href: "/admin/earnings", label: "Kazanc Raporlari", icon: TrendingUp },
      { href: "/admin/fund-transfers", label: "TRC20 Fon Toplama", icon: Wallet },
      { href: "/admin/trades", label: "Islem Gecmisi", icon: History },
    ],
  },
  {
    title: "Operasyon & Teknik",
    items: [
      { href: "/admin/logs", label: "Platform Loglari", icon: ScrollText },
      { href: "/admin/shadow-mode", label: "Shadow Mode", icon: Sparkles },
    ],
  },
];

function NavLink({ href, label, icon: Icon, active }: NavItem & { active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
        active
          ? "bg-primary text-primary-foreground shadow-sm"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
      )}
    >
      <Icon className={cn("h-4 w-4 shrink-0", active ? "opacity-100" : "opacity-70 group-hover:opacity-100")} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function AdminSidebar() {
  const pathname = usePathname();
  const logout = usePlatformAdminLogout();

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border/80 bg-card/95 backdrop-blur-sm">
      <div className="border-b border-border/60 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">Platform Admin</p>
            <p className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">Kurumsal Panel</p>
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 scrollbar-thin">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {section.title}
            </p>
            <nav className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLink key={item.href} {...item} active={isActive(item.href, item.exact)} />
              ))}
            </nav>
          </div>
        ))}
      </div>

      <div className="mt-auto border-t border-border/60 p-4">
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2.5">
          <Building2 className="h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">{APP_NAME}</p>
            <p className="text-[10px] text-muted-foreground">{APP_TAGLINE}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={() => void logout()}>
          <LogOut className="h-4 w-4" />
          Guvenli Cikis
        </Button>
      </div>
    </aside>
  );
}
