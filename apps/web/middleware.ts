import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE_NAME = process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME ?? "trading_bot_session";
const PUBLIC_PATHS = ["/login", "/admin/login"];

/**
 * Kaba (edge) yetkilendirme kontrolu: oturum cookie'sinin VARLIGINI kontrol eder.
 * Cookie'nin gecerliligi (suresi dolmus/iptal edilmis mi) sunucu tarafinda
 * API cagrilari sirasinda dogrulanir; 401 alindiginda istemci tarafi da
 * kullaniciyi /login'e yonlendirir (bkz. hooks/use-auth.ts + app/(dashboard)/layout.tsx).
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE_NAME)?.value);
  const isPublicPath = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const isAdminPath = pathname.startsWith("/admin") && !pathname.startsWith("/admin/login");

  if (!hasSession && !isPublicPath) {
    const loginUrl = new URL(isAdminPath ? "/admin/login" : "/login", request.url);
    if (!isAdminPath) {
      loginUrl.searchParams.set("next", pathname);
    }
    return NextResponse.redirect(loginUrl);
  }

  if (hasSession && pathname === "/login") {
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
