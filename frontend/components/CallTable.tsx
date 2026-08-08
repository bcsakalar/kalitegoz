"use client";

import Link from "next/link";
import type { CallListItem } from "@/lib/types";
import { fmtDate, fmtDuration } from "@/lib/api";
import { CategoryChip, ChannelChip, ScoreBadge, StatusChip } from "./Badges";
import { useT } from "@/components/I18nProvider";

export default function CallTable({ calls, selectable, selected, onToggle, onToggleAll }: {
  calls: CallListItem[];
  selectable?: boolean;
  selected?: Set<number>;
  onToggle?: (id: number) => void;
  onToggleAll?: () => void;
}) {
  const t = useT();
  if (calls.length === 0) {
    return (
      <p className="card p-8 text-center text-sm text-muted">{t("ct.empty")}</p>
    );
  }
  const allSel = selectable && calls.every((c) => selected?.has(c.id));
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
            {selectable && (
              <th className="px-3 py-2.5">
                <input type="checkbox" checked={!!allSel} onChange={onToggleAll} aria-label="tümünü seç" />
              </th>
            )}
            <th className="px-4 py-2.5">#</th>
            <th className="px-4 py-2.5">{t("ct.file")}</th>
            <th className="px-4 py-2.5">{t("ct.channel")}</th>
            <th className="px-4 py-2.5">{t("ct.agent")}</th>
            <th className="px-4 py-2.5">{t("ct.category")}</th>
            <th className="px-4 py-2.5">{t("ct.duration")}</th>
            <th className="px-4 py-2.5">{t("ct.score")}</th>
            <th className="px-4 py-2.5">{t("ct.status")}</th>
            <th className="px-4 py-2.5">{t("ct.date")}</th>
          </tr>
        </thead>
        <tbody>
          {calls.map((c) => (
            <tr key={c.id} className={`border-b border-hairline last:border-0 hover:bg-grid/40 ${selected?.has(c.id) ? "bg-series/5" : ""}`}>
              {selectable && (
                <td className="px-3 py-2.5">
                  <input type="checkbox" checked={!!selected?.has(c.id)} onChange={() => onToggle?.(c.id)} aria-label={`seç ${c.id}`} />
                </td>
              )}
              <td className="px-4 py-2.5 text-muted">{c.id}</td>
              <td className="px-4 py-2.5">
                <Link href={`/calls/${c.id}`} className="font-medium text-series hover:underline">
                  {c.filename}
                </Link>
                <span className="ml-1 space-x-1 align-middle">
                  {c.is_golden && <span title={t("golden.badge")} aria-hidden>⭐</span>}
                  {c.is_crisis && <span title={t("ct.crisis")} aria-hidden>🔴</span>}
                  {c.zeroed && <span title={t("wf.alert.zeroing")} aria-hidden>⛔</span>}
                  {c.is_repeat && (
                    <span title={`${t("ct.repeatOf")}: #${c.repeat_of_id})`} aria-hidden>🔁</span>
                  )}
                </span>
                {c.tags && c.tags.length > 0 && (
                  <span className="ml-1 space-x-1 align-middle">
                    {c.tags.slice(0, 3).map((tg) => (
                      <span key={tg} className="rounded bg-grid px-1.5 py-0.5 text-[10px] text-ink2">{tg}</span>
                    ))}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5"><ChannelChip channel={c.channel} /></td>
              <td className="px-4 py-2.5">{c.agent?.name ?? "—"}</td>
              <td className="px-4 py-2.5"><CategoryChip category={c.category} /></td>
              <td className="px-4 py-2.5 whitespace-nowrap tabular-nums">
                {c.duration_sec != null && c.duration_sec >= 300 ? (
                  <span className="inline-flex items-center gap-1 font-semibold text-series" title={t("ct.longCall")}>
                    ⏱ {fmtDuration(c.duration_sec)}
                  </span>
                ) : (
                  <span className="text-ink2">{fmtDuration(c.duration_sec)}</span>
                )}
              </td>
              <td className="px-4 py-2.5"><ScoreBadge score={c.total_score} zeroed={c.zeroed} /></td>
              <td className="px-4 py-2.5"><StatusChip status={c.status} /></td>
              <td className="px-4 py-2.5 whitespace-nowrap text-ink2">{fmtDate(c.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
