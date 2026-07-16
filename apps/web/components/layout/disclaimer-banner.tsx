"use client";

import * as React from "react";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

import { cn } from "@/lib/utils";

export function DisclaimerBanner() {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <div className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] leading-snug text-amber-300 sm:px-3">
      <div className="flex items-start gap-1.5">
        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className={cn(!expanded && "line-clamp-1 md:line-clamp-none")}>
            <strong>Risk Uyarisi:</strong> Bu sistem kazanc garantisi vermez. Kripto para vadeli islem (futures) ticareti
            yuksek risk icerir; yatirdiginiz sermayenin tamamini kaybedebilirsiniz. Tum kararlar ve sonuclar kullaniciya
            aittir.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="inline-flex shrink-0 items-center gap-0.5 rounded px-1 py-0.5 text-[10px] font-medium text-amber-200 hover:bg-amber-500/10 md:hidden"
          aria-expanded={expanded}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" />
              Kapat
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              Oku
            </>
          )}
        </button>
      </div>
    </div>
  );
}
