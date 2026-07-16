"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Building2, Loader2, Shield } from "lucide-react";

import { authApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { APP_NAME } from "@/lib/branding";

const schema = z.object({
  email: z.string().email("Gecerli e-posta girin"),
  password: z.string().min(1, "Sifre gerekli"),
});

type FormValues = z.infer<typeof schema>;

export default function AdminLoginPage() {
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login(values.email, values.password);
      if (res.admin.role !== "platform_admin") {
        await authApi.logout();
        setError("Bu hesap platform yoneticisi degil.");
        return;
      }
      window.location.replace("/admin");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Bu e-posta musteri hesabidir. Platform yonetici hesabi ile giris yapin.");
      } else {
        setError(err instanceof ApiError ? err.message : "Giris basarisiz");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary shadow-sm">
            <Shield className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Platform Yonetici Girisi</h1>
          <p className="mt-1 text-sm text-muted-foreground">Kurumsal yonetim konsoluna erisin</p>
        </div>

        <Card className="overflow-hidden border-border/80 shadow-lg">
          <div className="border-b border-border/60 bg-muted/20 px-6 py-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Building2 className="h-3.5 w-3.5" />
              {APP_NAME} · Admin Panel
            </div>
          </div>
          <CardContent className="p-6">
            <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)}>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Kurumsal E-posta</Label>
                <Input id="email" type="email" autoComplete="username" {...register("email")} />
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Sifre</Label>
                <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
              </div>
              {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
                  {error}
                </div>
              )}
              <Button type="submit" className="mt-1 w-full" disabled={loading}>
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Guvenli Giris
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
