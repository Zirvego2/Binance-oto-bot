"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Shadow Mode yalnizca platform admin panelindedir (/admin/shadow-mode). */
export default function ShadowModeRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return null;
}
