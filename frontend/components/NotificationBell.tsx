"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";
import type { NotificationFeed } from "@/lib/types";
import { useT } from "./I18nProvider";

const KIND_ICON: Record<string, string> = {
  alert: "⚠️", review: "🔍", coaching: "🎯", appeal: "⚖️",
};

/** Bildirim merkezi zili: birleşik uyarı/aksiyon akışı + okundu işaretle. */
export default function NotificationBell({ collapsed }: { collapsed?: boolean }) {
  const t = useT();
  const pathname = usePathname();
  const [feed, setFeed] = useState<NotificationFeed | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => { api.notifications().then(setFeed).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load, pathname]);
  useEffect(() => {
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  const count = feed?.unread_count ?? 0;

  async function markAll() {
    try { await api.notificationsReadAll(); load(); } catch { /* yoksay */ }
  }

  return (
    <>
      <button
        className="relative grid h-8 w-8 shrink-0 place-items-center rounded-lg text-lg hover:bg-[var(--surface-2)]"
        onClick={() => setOpen((o) => !o)}
        title={t("notif.title")}
        aria-label={t("notif.title")}
      >
        🔔
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid min-w-[16px] place-items-center rounded-full bg-[var(--status-critical)] px-1 text-[10px] font-bold leading-4 text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="fixed left-2 top-14 z-50 max-h-[70vh] w-80 overflow-y-auto rounded-xl border border-hairline bg-surface shadow-lg">
            <div className="flex items-center justify-between border-b border-hairline px-3 py-2">
              <span className="text-sm font-semibold">{t("notif.title")}</span>
              {count > 0 && (
                <button className="text-xs text-series hover:underline" onClick={markAll}>
                  {t("notif.markAll")}
                </button>
              )}
            </div>
            {!feed || feed.items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted">{t("notif.empty")}</p>
            ) : (
              <div className="divide-y divide-hairline">
                {feed.items.map((n, i) => (
                  <Link
                    key={`${n.kind}-${n.ref_id}-${i}`}
                    href={n.link}
                    onClick={() => setOpen(false)}
                    className="flex gap-2 px-3 py-2.5 text-sm hover:bg-grid/50"
                  >
                    <span aria-hidden className="shrink-0">{KIND_ICON[n.kind] ?? "🔔"}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-ink2">{n.title}</span>
                      <span className="block truncate text-xs text-muted">{n.message}</span>
                      <span className="block text-[10px] text-muted">{fmtDate(n.created_at)}</span>
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
