"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import type { LeaderboardRow, Gamification } from "@/lib/types";

const PERIODS = [{ v: "week", k: "leaderboard.week" }, { v: "month", k: "leaderboard.month" }, { v: "all", k: "leaderboard.all" }];
const MEDALS = ["🥇", "🥈", "🥉"];

export default function LeaderboardPage() {
  const t = useT();
  const { me } = useAuth();
  const [rows, setRows] = useState<LeaderboardRow[] | null>(null);
  const [period, setPeriod] = useState("month");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setRows(await api.leaderboard(period)); } catch (e) { setError(String(e)); }
  }, [period]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t("leaderboard.title")}</h1>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button key={p.v} onClick={() => setPeriod(p.v)}
              className={`btn !py-1 text-xs ${period === p.v ? "btn-primary" : ""}`}>{t(p.k)}</button>
          ))}
        </div>
      </div>
      <p className="text-sm text-ink2">{t("leaderboard.desc")}</p>

      {me?.agent_id != null && <MyPerformance />}

      {error && <p className="card p-3 text-sm">{error}</p>}
      {!rows ? <p className="p-6 text-sm text-muted">{t("common.loading")}</p> : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">{t("calls.agent")}</th>
                <th className="px-4 py-2.5">{t("leaderboard.team")}</th>
                <th className="px-4 py-2.5">{t("nav.calls")}</th>
                <th className="px-4 py-2.5">{t("stat.crisis")}</th>
                <th className="px-4 py-2.5">{t("stat.avgScore")}</th>
                <th className="px-4 py-2.5">{t("leaderboard.points")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const mine = me?.agent_id === r.agent_id;
                return (
                  <tr key={r.agent_id} className={`border-b border-hairline last:border-0 ${mine ? "bg-[rgba(42,120,214,0.10)]" : "hover:bg-grid/40"}`}>
                    <td className="px-4 py-2.5 font-semibold">{MEDALS[i] ?? i + 1}</td>
                    <td className="px-4 py-2.5">
                      <Link href={`/agents/${r.agent_id}`} className="font-medium text-series hover:underline">{r.agent_name}</Link>
                      {mine && <span className="ml-1 text-xs text-muted">{t("leaderboard.you")}</span>}
                    </td>
                    <td className="px-4 py-2.5 text-ink2">{r.team_name ?? "—"}</td>
                    <td className="px-4 py-2.5 tabular-nums">{r.call_count}</td>
                    <td className="px-4 py-2.5 tabular-nums">{r.crisis_handled}</td>
                    <td className="px-4 py-2.5 tabular-nums">{r.avg_score.toFixed(1)}</td>
                    <td className="px-4 py-2.5 text-lg font-bold tabular-nums">{r.points.toFixed(1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Temsilcinin kendi performansı: puan + seri + aktif hedefler (Dalga 3c + 3d) */
function MyPerformance() {
  const t = useT();
  const [g, setG] = useState<Gamification | null>(null);
  useEffect(() => { api.myGamification().then(setG).catch(() => {}); }, []);
  if (!g) return null;
  return (
    <div className="card p-4">
      <h2 className="mb-3 text-sm font-semibold text-ink2">⭐ {t("gam.title")}</h2>
      <div className="flex flex-wrap gap-4">
        <div className="rounded-lg bg-series/10 px-4 py-2 text-center">
          <div className="text-2xl font-bold text-series">{g.points}</div>
          <div className="text-[10px] text-muted">{t("gam.points")}</div>
        </div>
        <div className="rounded-lg bg-grid/40 px-4 py-2 text-center">
          <div className="text-2xl font-bold">🔥 {g.streak}</div>
          <div className="text-[10px] text-muted">{t("gam.streak")} · {t("gam.streakUnit")}</div>
        </div>
        <div className="flex-1">
          <div className="mb-1 text-xs font-semibold text-ink2">{t("gam.challenges")}</div>
          {g.challenges.length === 0 ? (
            <p className="text-xs text-muted">{t("common.noData")}</p>
          ) : g.challenges.map((c) => (
            <div key={c.id} className="mb-1.5">
              <div className="flex items-center justify-between text-xs">
                <span>{c.completed ? "✅" : "⏳"} {c.title}</span>
                <span className="text-muted">{c.progress}/{c.target} · +{c.reward_points} {t("gam.reward")}</span>
              </div>
              <div className="mt-0.5 h-1.5 overflow-hidden rounded bg-grid/40">
                <div className="h-full bg-series" style={{ width: `${Math.min(100, (c.progress / c.target) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
