"use client";

import * as React from "react";

import type { DashboardWsMessage } from "@/types/api";

const WS_BASE_URL_ENV = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000/api/v1";

/**
 * WebSocket constructor'i (fetch'in aksine) SADECE mutlak URL kabul eder.
 * Nginx arkasinda tek origin uzerinden calisirken NEXT_PUBLIC_WS_BASE_URL
 * bilerek goreli (orn. "/api/v1") verilebilir; bu durumda tarayicinin
 * su anki host'undan ve protokolunden (http->ws, https->wss) mutlak URL uretilir.
 */
function resolveWsBaseUrl(): string {
  if (WS_BASE_URL_ENV.startsWith("ws://") || WS_BASE_URL_ENV.startsWith("wss://")) {
    return WS_BASE_URL_ENV;
  }
  if (typeof window === "undefined") return WS_BASE_URL_ENV;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const path = WS_BASE_URL_ENV.startsWith("/") ? WS_BASE_URL_ENV : `/${WS_BASE_URL_ENV}`;
  return `${protocol}//${window.location.host}${path}`;
}

/**
 * Dashboard WebSocket akisina baglanir; baglanti kesilirse ustel geri cekilme
 * (exponential backoff) ile yeniden baglanmayi dener. Sunucu tarafindan
 * ~1 saniyede bir "snapshot" mesaji gonderilir (bkz. services/api/app/api/routes/realtime.py).
 */
export function useDashboardWs() {
  const [data, setData] = React.useState<DashboardWsMessage | null>(null);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    let socket: WebSocket | null = null;
    let retryDelay = 1000;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      socket = new WebSocket(`${resolveWsBaseUrl()}/ws/dashboard`);

      socket.onopen = () => {
        setConnected(true);
        retryDelay = 1000;
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as DashboardWsMessage;
          setData(parsed);
        } catch {
          // gecersiz mesaj, yoksay
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        retryTimeout = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 15_000);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      stopped = true;
      if (retryTimeout) clearTimeout(retryTimeout);
      socket?.close();
    };
  }, []);

  return { data, connected };
}
