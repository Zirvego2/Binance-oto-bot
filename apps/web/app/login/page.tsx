"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Bot, Loader2 } from "lucide-react";

import { ApiError } from "@/lib/api-client";
import { customerRegister, customerSignIn } from "@/lib/firebase-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

const loginSchema = z.object({
  email: z.string().min(1, "E-posta gerekli").email("Gecerli bir e-posta girin"),
  password: z.string().min(6, "Sifre en az 6 karakter olmali"),
});

const registerSchema = z.object({
  fullName: z.string().min(2, "Ad soyad en az 2 karakter olmali"),
  phone: z.string().min(10, "Gecerli telefon numarasi girin"),
  city: z.string().min(2, "Il gerekli"),
  district: z.string().min(2, "Ilce gerekli"),
  email: z.string().min(1, "E-posta gerekli").email("Gecerli bir e-posta girin"),
  password: z.string().min(6, "Sifre en az 6 karakter olmali"),
});

type LoginFormValues = z.infer<typeof loginSchema>;
type RegisterFormValues = z.infer<typeof registerSchema>;

export default function LoginPage() {
  return (
    <React.Suspense fallback={null}>
      <LoginForm />
    </React.Suspense>
  );
}

function LoginForm() {
  const searchParams = useSearchParams();
  const [mode, setMode] = React.useState<"login" | "register">("login");
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const loginForm = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  React.useEffect(() => {
    const email = searchParams.get("email");
    const password = searchParams.get("password");
    if (email) loginForm.setValue("email", email);
    if (password) loginForm.setValue("password", password);
  }, [searchParams, loginForm]);

  const onLogin = async (values: LoginFormValues) => {
    setServerError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);
    try {
      await customerSignIn(values.email, values.password);
      const next = searchParams.get("next") ?? "/dashboard";
      window.location.replace(next);
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : "Giris yapilamadi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const onRegister = async (values: RegisterFormValues) => {
    setServerError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);
    try {
      const res = await customerRegister({
        email: values.email,
        password: values.password,
        full_name: values.fullName,
        phone: values.phone,
        city: values.city,
        district: values.district,
      });
      setSuccessMessage(res.message);
      setMode("login");
      loginForm.setValue("email", values.email);
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : "Kayit yapilamadi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <DisclaimerBanner />
      <div className="flex flex-1 items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Bot className="h-6 w-6" />
            </div>
            <h1 className="text-lg font-semibold text-foreground">{APP_NAME}</h1>
            <p className="text-xs text-muted-foreground">{APP_TAGLINE}</p>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex rounded-md border border-border p-1">
              <button
                type="button"
                className={`flex-1 rounded px-2 py-1.5 text-xs font-medium ${mode === "login" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
                onClick={() => setMode("login")}
              >
                Giris
              </button>
              <button
                type="button"
                className={`flex-1 rounded px-2 py-1.5 text-xs font-medium ${mode === "register" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
                onClick={() => setMode("register")}
              >
                Kayit Ol
              </button>
            </div>

            {mode === "login" ? (
              <form className="flex flex-col gap-4" onSubmit={loginForm.handleSubmit(onLogin)}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="email">E-posta</Label>
                  <Input id="email" type="email" autoComplete="username" {...loginForm.register("email")} />
                  {loginForm.formState.errors.email && (
                    <p className="text-xs text-destructive">{loginForm.formState.errors.email.message}</p>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="password">Sifre</Label>
                  <Input id="password" type="password" autoComplete="current-password" {...loginForm.register("password")} />
                  {loginForm.formState.errors.password && (
                    <p className="text-xs text-destructive">{loginForm.formState.errors.password.message}</p>
                  )}
                </div>
                {serverError && <ErrorBox message={serverError} />}
                {successMessage && <SuccessBox message={successMessage} />}
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Giris Yap
                </Button>
                <p className="text-center text-[11px] text-muted-foreground">
                  Kayit sonrasi admin onayi gerekir. Onaydan sonra giris yapabilirsiniz.
                </p>
              </form>
            ) : (
              <form className="flex flex-col gap-3" onSubmit={registerForm.handleSubmit(onRegister)}>
                <Field label="Ad Soyad" id="fullName" error={registerForm.formState.errors.fullName?.message}>
                  <Input id="fullName" autoComplete="name" {...registerForm.register("fullName")} />
                </Field>
                <Field label="Telefon" id="phone" error={registerForm.formState.errors.phone?.message}>
                  <Input id="phone" type="tel" placeholder="05xx xxx xx xx" autoComplete="tel" {...registerForm.register("phone")} />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Il" id="city" error={registerForm.formState.errors.city?.message}>
                    <Input id="city" {...registerForm.register("city")} />
                  </Field>
                  <Field label="Ilce" id="district" error={registerForm.formState.errors.district?.message}>
                    <Input id="district" {...registerForm.register("district")} />
                  </Field>
                </div>
                <Field label="E-posta" id="regEmail" error={registerForm.formState.errors.email?.message}>
                  <Input id="regEmail" type="email" autoComplete="email" {...registerForm.register("email")} />
                </Field>
                <Field label="Sifre" id="regPassword" error={registerForm.formState.errors.password?.message}>
                  <Input id="regPassword" type="password" autoComplete="new-password" {...registerForm.register("password")} />
                </Field>
                {serverError && <ErrorBox message={serverError} />}
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Kayit Ol
                </Button>
                <p className="text-center text-[11px] text-muted-foreground">
                  Kayit olunca hesabiniz admin onayina duser. Onay verilene kadar panele erisemezsiniz.
                </p>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Field({
  label,
  id,
  error,
  children,
}: {
  label: string;
  id: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      {message}
    </div>
  );
}

function SuccessBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
      {message}
    </div>
  );
}
