/**
 * Backend FastAPI servisi ile iletisim kuran fetch tabanli istemci.
 *
 * - Oturum cookie'si (HttpOnly) tarayici tarafindan otomatik gonderilir
 *   (credentials: "include").
 * - Durum degistiren istekler (POST/PUT/PATCH/DELETE) icin double-submit
 *   CSRF korumasi: "csrf_token" cookie'sinin degeri "X-CSRF-Token" header'i
 *   olarak da gonderilir.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  errors?: unknown;

  constructor(status: number, message: string, errors?: unknown) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const isAbsolute = API_BASE_URL.startsWith("http://") || API_BASE_URL.startsWith("https://");
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  const url = isAbsolute ? new URL(`${API_BASE_URL}${path}`) : new URL(`${API_BASE_URL}${path}`, origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") {
    const csrfToken = readCookie("csrf_token");
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response?.headers) {
    throw new ApiError(0, "Sunucudan gecersiz yanit alindi");
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail !== null && "message" in (detail as Record<string, unknown>)
          ? String((detail as Record<string, unknown>).message)
          : `Istek basarisiz oldu (HTTP ${response.status})`;
    throw new ApiError(response.status, message, typeof payload === "object" ? payload : undefined);
  }

  return payload as T;
}

export const apiClient = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
    request<T>(path, { method: "GET", query, signal }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", body, query }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
