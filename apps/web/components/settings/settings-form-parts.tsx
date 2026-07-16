"use client";

import * as React from "react";
import { z } from "zod";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export const numericField = (opts: { min?: number; max?: number } = {}) =>
  z.coerce
    .number()
    .refine((v) => !Number.isNaN(v), "Gecerli bir sayi girin")
    .refine((v) => opts.min === undefined || v >= opts.min, `En az ${opts.min} olmalidir`)
    .refine((v) => opts.max === undefined || v <= opts.max, `En fazla ${opts.max} olmalidir`);

export function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</CardContent>
    </Card>
  );
}

export function SettingsField({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export function SettingsToggleField({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2.5">
      <div className="min-w-0">
        <Label className="cursor-pointer text-sm leading-snug">{label}</Label>
        {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} className="mt-0.5 shrink-0" />
    </div>
  );
}
