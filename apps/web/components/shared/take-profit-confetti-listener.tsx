"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useDashboardWs } from "@/hooks/use-dashboard-ws";
import { settingsApi, tradesApi } from "@/lib/api";
import { fireTakeProfitConfetti } from "@/lib/confetti";
import { parseApiUtcDate } from "@/lib/utils";
import type { TradeOut } from "@/types/api";

async function fetchRecentClosedTrades() {
  return tradesApi.list({
    page: 1,
    page_size: 15,
    sort_by: "closed_at",
    sort_dir: "desc",
  });
}

function isTakeProfitClose(trade: TradeOut): boolean {
  return trade.close_reason?.toUpperCase() === "TAKE_PROFIT";
}

export function TakeProfitConfettiListener() {
  const queryClient = useQueryClient();
  const { data: wsData } = useDashboardWs();

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
    staleTime: 15_000,
  });

  const enabled = Boolean(settings?.take_profit_confetti_enabled);
  const seenIdsRef = React.useRef<Set<string>>(new Set());
  const watchSinceRef = React.useRef<Date | null>(null);
  const prevPositionIdsRef = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    if (enabled) {
      if (watchSinceRef.current === null) {
        watchSinceRef.current = new Date();
      }
      return;
    }
    watchSinceRef.current = null;
    seenIdsRef.current.clear();
    prevPositionIdsRef.current.clear();
  }, [enabled]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    if (params.get("konfeti") === "1") {
      const timer = window.setTimeout(() => fireTakeProfitConfetti(), 300);
      return () => window.clearTimeout(timer);
    }

    if (!enabled) return;
    if (sessionStorage.getItem("tp-confetti-session-demo")) return;
    sessionStorage.setItem("tp-confetti-session-demo", "1");
    const timer = window.setTimeout(() => fireTakeProfitConfetti(), 900);
    return () => window.clearTimeout(timer);
  }, [enabled]);

  const processTrades = React.useCallback(
    (items: TradeOut[]) => {
      if (!enabled || !watchSinceRef.current) return;

      const watchSince = watchSinceRef.current;
      let fired = false;

      for (const trade of items) {
        if (seenIdsRef.current.has(trade.id)) continue;

        const closedAt = parseApiUtcDate(trade.closed_at);
        seenIdsRef.current.add(trade.id);

        if (!closedAt || closedAt < watchSince) continue;
        if (!isTakeProfitClose(trade)) continue;

        if (!fired) {
          fireTakeProfitConfetti();
          fired = true;
        }
      }

      if (seenIdsRef.current.size > 300) {
        seenIdsRef.current = new Set(items.map((trade) => trade.id));
      }
    },
    [enabled],
  );

  const { data: polledTrades } = useQuery({
    queryKey: ["trades", "take-profit-confetti"],
    queryFn: fetchRecentClosedTrades,
    refetchInterval: enabled ? 1_500 : false,
    enabled,
    throwOnError: false,
  });

  React.useEffect(() => {
    if (polledTrades?.items) {
      processTrades(polledTrades.items);
    }
  }, [polledTrades, processTrades]);

  React.useEffect(() => {
    if (!enabled || !wsData?.open_positions) return;

    const currentIds = new Set(wsData.open_positions.map((p) => p.id));
    const prevIds = prevPositionIdsRef.current;

    if (prevIds.size > 0) {
      const closedCount = [...prevIds].filter((id) => !currentIds.has(id)).length;
      if (closedCount > 0) {
        void queryClient
          .fetchQuery({ queryKey: ["trades", "take-profit-confetti"], queryFn: fetchRecentClosedTrades })
          .then((data) => {
            processTrades(data.items);
          })
          .catch(() => {
            // Sessizce yoksay — konfeti opsiyonel, paneli kirletmemeli
          });
      }
    }

    prevPositionIdsRef.current = currentIds;
  }, [enabled, wsData?.open_positions, queryClient, processTrades]);

  return null;
}
