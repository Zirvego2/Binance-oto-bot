import { PlatformAdminGuard } from "@/components/layout/platform-admin-guard";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export default function AdminGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <PlatformAdminGuard>
      <div className="flex h-screen overflow-hidden bg-muted/20">
        <AdminSidebar />
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <header className="flex h-12 shrink-0 items-center border-b border-border/60 bg-background/80 px-6 backdrop-blur-sm">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Platform Yonetim Merkezi
            </p>
          </header>
          <main className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-7xl p-4 md:p-6 lg:p-8">{children}</div>
          </main>
        </div>
      </div>
    </PlatformAdminGuard>
  );
}
