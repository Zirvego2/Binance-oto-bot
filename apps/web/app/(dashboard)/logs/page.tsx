"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Loglar yalnizca platform admin panelindedir (/admin/logs). */
export default function LogsRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return null;
}
