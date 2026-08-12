"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useLiveAlerts } from "./LiveAlertsProvider";
import { useT } from "./I18nProvider";

const AUTO_DISMISS_MS = 8000;

const SEVERITY_COLOR: Record<string, string> = {
  yuksek: "var(--status-critical)",
  orta: "var(--status-warning)",
  dusuk: "var(--status-good)",
};

/** Canli alarm bildirimi. WebSocket'ten alarm geldiginde sag altta belirir. */
export default function AlertToast() {
  const { incoming, dismissIncoming } = useLiveAlerts();
  const t = useT();

  useEffect(() => {
    if (!incoming) return;
    const id = setTimeout(dismissIncoming, AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [incoming, dismissIncoming]);

  if (!incoming) return null;

  const color = SEVERITY_COLOR[incoming.severity] ?? "var(--status-warning)";

  return (
    <div
      role="status"
      aria-live="polite"
      className="card fixed bottom-4 right-4 z-50 w-[min(22rem,calc(100vw-2rem))] p-3 shadow-lg"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex items-start gap-2">
        <span aria-hidden className="text-base">🔔</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold" style={{ color }}>
              {t("alerts.new")}
            </span>
            <span className="text-[10px] uppercase text-muted">{incoming.type}</span>
          </div>
          <p className="mt-0.5 break-words text-xs text-ink-2">{incoming.message}</p>
          {incoming.call_id && (
            <Link
              href={`/calls/${incoming.call_id}`}
              onClick={dismissIncoming}
              className="mt-1.5 inline-block text-xs font-medium text-series underline"
            >
              {t("alerts.open_call")}
            </Link>
          )}
        </div>
        <button
          onClick={dismissIncoming}
          className="shrink-0 text-muted hover:text-ink"
          aria-label={t("common.close")}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
