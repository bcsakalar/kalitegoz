"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { api, fmtDate } from "@/lib/api";
import type { Alert, Appeal, CalibrationRow, CoachingTask, ReviewAssignment } from "@/lib/types";

const ALERT_KEYS: Record<string, string> = {
  zeroing: "wf.alert.zeroing", crisis: "wf.alert.crisis", banned_word: "wf.alert.banned_word",
  low_score: "wf.alert.low_score", score_drop: "wf.alert.score_drop",
};
const REASON_KEYS: Record<string, string> = {
  random: "wf.reason.random", low_confidence: "wf.reason.low_confidence",
  critical: "wf.reason.critical", manual: "wf.reason.manual",
};
const SEV_CLS: Record<string, string> = { dusuk: "badge-neutral", orta: "badge-warning", yuksek: "badge-critical" };

export default function WorkflowPage() {
  const t = useT();
  const { me } = useAuth();
  const isStaff = me && me.role !== "agent";
  const isQuality = me && (me.role === "quality" || me.role === "admin");
  const isAgent = me?.role === "agent";

  const tabs = [
    ...(isStaff ? [{ id: "alerts", label: t("workflow.alerts") }] : []),
    ...(isStaff ? [{ id: "reviews", label: t("review.mine") }] : []),
    { id: "appeals", label: t("workflow.appeals") },
    { id: "coaching", label: t("workflow.coaching") },
    ...(isQuality ? [{ id: "calibration", label: t("workflow.calibrationTab") }] : []),
  ];
  const [tab, setTab] = useState(tabs[0]?.id ?? "appeals");

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t("workflow.title")}</h1>
      <div className="flex flex-wrap gap-1 border-b border-hairline">
        {tabs.map((tb) => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            className={`px-3 py-2 text-sm font-medium ${tab === tb.id ? "border-b-2 border-series text-ink" : "text-ink2"}`}>
            {tb.label}
          </button>
        ))}
      </div>
      {tab === "alerts" && <AlertsTab />}
      {tab === "reviews" && <ReviewsTab />}
      {tab === "appeals" && <AppealsTab canResolve={!!isQuality} isAgent={!!isAgent} />}
      {tab === "coaching" && <CoachingTab isAgent={!!isAgent} />}
      {tab === "calibration" && <CalibrationTab />}
    </div>
  );
}

/** Bana atanmış QA inceleme kuyruğu (Dalga 2b). */
function ReviewsTab() {
  const t = useT();
  const [rows, setRows] = useState<ReviewAssignment[]>([]);
  const load = useCallback(() => { api.myReviews(false).then(setRows).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  async function complete(id: number) { await api.completeReview(id); load(); }

  if (rows.length === 0) return <p className="card p-6 text-center text-sm text-muted">{t("review.empty")}</p>;
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.id} className={`card flex flex-wrap items-center gap-3 p-3 text-sm ${r.status === "completed" ? "opacity-60" : ""}`}>
          <span className="badge badge-neutral">{t(REASON_KEYS[r.reason] ?? r.reason)}</span>
          <Link href={`/calls/${r.call_id}`} className="flex-1 font-medium text-series hover:underline">{t("wf.callNo")} #{r.call_id}</Link>
          <span className="text-xs text-muted">{fmtDate(r.created_at)}</span>
          {r.status === "completed"
            ? <span className="badge badge-good"><span className="dot" aria-hidden />{t("review.done")}</span>
            : <button className="btn !py-1 text-xs" onClick={() => complete(r.id)}>{t("review.complete")}</button>}
        </div>
      ))}
    </div>
  );
}

function AlertsTab() {
  const t = useT();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const load = useCallback(() => { api.listAlerts().then(setAlerts).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  async function markRead(id: number) { await api.readAlert(id); load(); }

  if (alerts.length === 0) return <p className="card p-6 text-center text-sm text-muted">{t("workflow.noAlerts")}</p>;
  return (
    <div className="space-y-2">
      {alerts.map((a) => (
        <div key={a.id} className={`card flex flex-wrap items-center gap-3 p-3 text-sm ${a.is_read ? "opacity-60" : ""}`}>
          <span className={`badge ${SEV_CLS[a.severity] ?? "badge-warning"}`}><span className="dot" aria-hidden />{t(ALERT_KEYS[a.type] ?? a.type)}</span>
          <span className="flex-1 text-ink">{a.message}</span>
          <span className="text-xs text-muted">{fmtDate(a.created_at)}</span>
          {a.call_id && <Link href={`/calls/${a.call_id}`} className="text-series hover:underline">#{a.call_id} →</Link>}
          {!a.is_read && <button className="btn !py-0.5 text-xs" onClick={() => markRead(a.id)}>{t("workflow.markRead")}</button>}
        </div>
      ))}
    </div>
  );
}

function AppealsTab({ canResolve, isAgent }: { canResolve: boolean; isAgent: boolean }) {
  const t = useT();
  const [appeals, setAppeals] = useState<Appeal[]>([]);
  const load = useCallback(() => { api.listAppeals().then(setAppeals).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  async function resolve(id: number, decision: string) {
    const note = prompt(decision === "accepted" ? t("wf.acceptReason") : t("wf.rejectReason")) ?? "";
    await api.resolveAppeal(id, { decision, resolution_note: note });
    load();
  }

  if (appeals.length === 0)
    return <p className="card p-6 text-center text-sm text-muted">
      {isAgent ? t("workflow.noAppealsAgent") : t("workflow.noAppeals")}
    </p>;
  return (
    <div className="space-y-2">
      {appeals.map((a) => (
        <div key={a.id} className="card p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`badge ${a.status === "open" ? "badge-warning" : a.status === "accepted" ? "badge-good" : "badge-critical"}`}>
              <span className="dot" aria-hidden />{a.status === "open" ? t("workflow.open") : a.status === "accepted" ? t("workflow.accepted") : t("workflow.rejected")}
            </span>
            <Link href={`/calls/${a.call_id}`} className="text-series hover:underline">{t("wf.callNo")} #{a.call_id}</Link>
            <span className="text-xs text-muted">{fmtDate(a.created_at)}</span>
            {canResolve && a.status === "open" && (
              <span className="ml-auto flex gap-2">
                <button className="btn btn-primary !py-0.5 text-xs" onClick={() => resolve(a.id, "accepted")}>{t("workflow.accepted")}</button>
                <button className="btn !py-0.5 text-xs" onClick={() => resolve(a.id, "rejected")}>{t("workflow.rejected")}</button>
              </span>
            )}
          </div>
          <p className="mt-2 text-ink2">{a.reason}</p>
          {a.resolution_note && <p className="mt-1 text-xs text-muted">Karar notu: {a.resolution_note}</p>}
        </div>
      ))}
    </div>
  );
}

function CoachingTab({ isAgent }: { isAgent: boolean }) {
  const t = useT();
  const [tasks, setTasks] = useState<CoachingTask[]>([]);
  const load = useCallback(() => { api.listCoaching().then(setTasks).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  async function complete(id: number) {
    const comment = prompt(t("wf.coachingComment")) ?? "";
    await api.completeCoaching(id, { agent_comment: comment });
    load();
  }

  if (tasks.length === 0)
    return <p className="card p-6 text-center text-sm text-muted">{t("workflow.noCoaching")}</p>;
  return (
    <div className="space-y-2">
      {tasks.map((task) => (
        <div key={task.id} className="card p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`badge ${task.status === "open" ? "badge-warning" : "badge-good"}`}>
              <span className="dot" aria-hidden />{task.status === "open" ? t("workflow.open") : t("workflow.done")}
            </span>
            <Link href={`/calls/${task.call_id}`} className="text-series hover:underline">#{task.call_id}</Link>
            <span className="text-xs text-muted">{fmtDate(task.created_at)}</span>
            {isAgent && task.status === "open" && (
              <button className="btn btn-primary ml-auto !py-0.5 text-xs" onClick={() => complete(task.id)}>{t("workflow.complete")}</button>
            )}
          </div>
          {task.note && <p className="mt-2 text-ink2">{task.note}</p>}
          {task.agent_comment && <p className="mt-1 text-xs text-muted">{task.agent_comment}</p>}
        </div>
      ))}
    </div>
  );
}

function CalibrationTab() {
  const t = useT();
  const [rows, setRows] = useState<CalibrationRow[]>([]);
  useEffect(() => { api.calibration().then(setRows).catch(() => {}); }, []);
  if (rows.length === 0)
    return <p className="card p-6 text-center text-sm text-muted">{t("wf.calibEmpty")}</p>;
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-4 py-2.5">{t("rubric.name")}</th>
            <th className="px-4 py-2.5">{t("wf.aiAvg")}</th>
            <th className="px-4 py-2.5">{t("wf.humanAvg")}</th>
            <th className="px-4 py-2.5">{t("wf.delta")}</th>
            <th className="px-4 py-2.5">{t("wf.overrideCount")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.criterion_name} className="border-b border-hairline last:border-0">
              <td className="px-4 py-2.5 font-medium">{r.criterion_name}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.ai_avg}</td>
              <td className="px-4 py-2.5 tabular-nums">{r.human_avg}</td>
              <td className="px-4 py-2.5 tabular-nums font-semibold" style={{ color: Math.abs(r.delta) >= 1.5 ? "var(--status-critical)" : "var(--ink)" }}>
                {r.delta > 0 ? "+" : ""}{r.delta}
              </td>
              <td className="px-4 py-2.5 tabular-nums">{r.override_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
