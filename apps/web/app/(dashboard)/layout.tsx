import { AuthGuard } from "@/components/layout/auth-guard";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { TakeProfitConfettiListener } from "@/components/shared/take-profit-confetti-listener";

export default function DashboardGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <TakeProfitConfettiListener />
      <div className="customer-shell flex h-[100dvh] flex-col">
        <DisclaimerBanner />
        <DashboardShell>{children}</DashboardShell>
      </div>
    </AuthGuard>
  );
}
