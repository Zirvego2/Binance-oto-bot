"use client";

import { useQuery } from "@tanstack/react-query";

import { authApi } from "@/lib/api";

/**
 * Oturum durumunu kontrol eder. NOT: ``throwOnError`` KASITLI olarak
 * kullanilmaz — API kisa sureli erisilemez olsa bile (ag hatasi, backend
 * yeniden baslatiliyor vb.) React'in tum agaci "unmount" etmesine (bos/beyaz
 * sayfa) izin VERILMEZ; hata durumu ``AuthGuard`` icinde nazikce ele alinir.
 */
export function useCurrentAdmin() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
    staleTime: 60_000,
  });
}
