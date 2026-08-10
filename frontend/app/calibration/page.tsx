"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";
import type { CalibrationReport, CalibrationSession, Criterion } from "@/lib/types";

export default function CalibrationPage() {
  const t = useT();
  const [sessions, setSessions] = useState<CalibrationSession[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [evaluating, setEvaluating] = useState<CalibrationSession | null>(null);
  const [newCallId, setNewCallId] = useState("");
  const [newSchedule, setNewSchedule] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        api.listCalibrationSessions(),
        api.listCriteria(),
      ]);
      setSessions(s);
      setCriteria(c.filter((x) => x.is_active));
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function create() {
    const id = parseInt(newCallId, 10);
    if (!Number.isFinite(id)) { setMsg(t("calib.callNo")); return; }
    setBusy(true); setMsg("");
    try {
      await api.createCalibrationSession({ call_id: id, scheduled_at: newSchedule ? new Date(newSchedule).toISOString() : null });
      setNewCallId(""); setNewSchedule(""); await load();
    }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function close(s: CalibrationSession) {
    setBusy(true);
    try { setReport(await api.closeCalibrationSession(s.id)); await load(); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function showReport(s: CalibrationSession) {
    setBusy(true); setMsg("");
    try { setReport(await api.calibrationReport(s.id)); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">{t("calib.title")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink2">{t("calib.desc")}</p>
      </div>

      {msg && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-warning)" }}>{msg}</p>}

      <div className="card flex flex-wrap items-end gap-2 p-3">
        <label className="text-xs text-ink2">
          {t("calib.callNo")}
          <input className="input mt-1 block w-32" placeholder={t("cal.egCallId")} value={newCallId}
            onChange={(e) => setNewCallId(e.target.value)} />
        </label>
        <label className="text-xs text-ink2">
          📅 {t("calib.schedule")}
          <input type="datetime-local" className="input mt-1 block" value={newSchedule}
            onChange={(e) => setNewSchedule(e.target.value)} />
        </label>
        <button className="btn btn-primary" disabled={busy} onClick={create}>＋ {t("calib.openSession")}</button>
        
      </div>

      {sessions.length === 0 ? (
        <p className="card p-8 text-center text-sm text-muted">{t("calib.noSessions")}</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="card flex flex-wrap items-center gap-3 p-3 text-sm">
              <span className={`badge ${s.status === "open" ? "badge-warning" : "badge-good"}`}>
                <span className="dot" aria-hidden />{s.status === "open" ? t("workflow.open") : t("common.close")}
              </span>
              <span className="font-medium">{s.title}</span>
              {s.scheduled_at && new Date(s.scheduled_at) > new Date() && (
                <span className="badge badge-info" title={fmtDate(s.scheduled_at)}>📅 {t("calib.planned")}: {fmtDate(s.scheduled_at)}</span>
              )}
              <Link href={`/calls/${s.call_id}`} className="text-series hover:underline">
                Çağrı #{s.call_id}
              </Link>
              <span className="text-xs text-muted">{s.evaluation_count}</span>
              <span className="text-xs text-muted">{fmtDate(s.created_at)}</span>
              <span className="ml-auto flex gap-2">
                {s.status === "open" && !s.my_evaluation_id && (
                  <button className="btn btn-primary !py-0.5 text-xs" onClick={() => setEvaluating(s)}>
                    {t("calib.evaluate")}
                  </button>
                )}
                {s.status === "open" && s.my_evaluation_id && (
                  <span className="badge badge-info">{t("calib.evaluated")}</span>
                )}
                {s.status === "open" && (
                  <button className="btn !py-0.5 text-xs" disabled={busy} onClick={() => close(s)}>
                    {t("calib.closeReport")}
                  </button>
                )}
                {s.status === "closed" && (
                  <button className="btn !py-0.5 text-xs" onClick={() => showReport(s)}>{t("calib.report")}</button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {evaluating && (
        <EvaluateForm
          session={evaluating} criteria={criteria}
          onDone={() => { setEvaluating(null); load(); }}
          onCancel={() => setEvaluating(null)}
        />
      )}

      {report && <ReportView report={report} onClose={() => setReport(null)} />}
    </div>
  );
}

function EvaluateForm({ session, criteria, onDone, onCancel }: {
  session: CalibrationSession; criteria: Criterion[];
  onDone: () => void; onCancel: () => void;
}) {
  const t = useT();
  const [scores, setScores] = useState<Record<number, number>>(
    Object.fromEntries(criteria.map((c) => [c.id, 5])),
  );
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    setBusy(true); setErr("");
    try {
      await api.submitEvaluation(session.id, {
        call_id: session.call_id,
        scores: criteria.map((c) => ({ criterion_id: c.id, score: scores[c.id] ?? 5 })),
        notes,
      });
      onDone();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="card p-4">
      <h2 className="font-semibold">{t("cal.independentEval")} — {t("wf.callNo")} #{session.call_id}</h2>
      <p className="mt-1 text-xs text-muted">{t("cal.evalHint")}</p>
      <div className="mt-3 space-y-2">
        {criteria.map((c) => (
          <div key={c.id} className="flex items-center gap-3">
            <span className="w-56 text-sm">{c.name}</span>
            <input type="range" min={0} max={10} className="flex-1" value={scores[c.id] ?? 5}
              onChange={(e) => setScores({ ...scores, [c.id]: Number(e.target.value) })} />
            <span className="w-8 text-right font-semibold tabular-nums">{scores[c.id] ?? 5}</span>
          </div>
        ))}
      </div>
      <textarea className="input mt-3 w-full text-sm" rows={2} placeholder={t("cal.generalNote")}
        value={notes} onChange={(e) => setNotes(e.target.value)} />
      {err && <p className="mt-2 text-sm text-[var(--status-critical)]">{err}</p>}
      <div className="mt-3 flex gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={submit}>
          {busy ? t("cal.submitting") : t("cal.submitEval")}
        </button>
        <button className="btn" onClick={onCancel}>{t("cal.cancel")}</button>
      </div>
    </div>
  );
}

function ReportView({ report: r, onClose }: { report: CalibrationReport; onClose: () => void }) {
  const t = useT();
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{t("cal.report")} — {t("wf.callNo")} #{r.call_id}</h2>
        <button className="btn !py-0.5 text-xs" onClick={onClose}>{t("cal.close")}</button>
      </div>

      {r.agreement_pct == null ? (
        <p className="mt-3 text-sm text-muted">
          {t("cal.needTwo")} ({r.evaluator_count}).
        </p>
      ) : (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className={`badge ${r.meets_target ? "badge-good" : "badge-critical"}`}>
              <span className="dot" aria-hidden />
              {t("cal.agreement")} %{r.agreement_pct} {r.meets_target ? t("cal.targetMet") : `(${t("cal.target")} %${r.target})`}
            </span>
            <span className="text-sm text-ink2">{r.evaluator_count} {t("cal.experts")}</span>
            {r.ai_total != null && <span className="text-sm text-ink2">{t("cal.aiTotal")}: <b>{r.ai_total}</b></span>}
            {r.human_avg_total != null && <span className="text-sm text-ink2">{t("cal.humanAvgTotal")}: <b>{r.human_avg_total}</b></span>}
          </div>

          {r.most_divergent && (
            <p className="mt-2 bg-grid/50 p-2.5 text-sm">
              ⚠️ {t("cal.mostDivergent")}: <b>{r.most_divergent}</b> — {t("cal.divergentHint")}
            </p>
          )}

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase text-muted">
                  <th className="px-2 py-2">{t("cal.colCriterion")}</th>
                  <th className="px-2 py-2">{t("cal.expertScores")}</th>
                  <th className="px-2 py-2">{t("cal.colFark")}</th>
                  <th className="px-2 py-2">{t("cal.colOrt")}</th>
                  <th className="px-2 py-2">AI</th>
                  <th className="px-2 py-2">{t("cal.agreement")}</th>
                </tr>
              </thead>
              <tbody>
                {r.criteria.map((c) => (
                  <tr key={c.criterion_id} className="border-b border-hairline last:border-0">
                    <td className="px-2 py-2 font-medium">{c.criterion_name}</td>
                    <td className="px-2 py-2 text-xs text-ink2">
                      {c.scores.map((s) => `${s.evaluator}: ${s.score}`).join(" · ")}
                    </td>
                    <td className="px-2 py-2 tabular-nums font-semibold"
                      style={{ color: c.agreed ? "var(--ink)" : "var(--status-critical)" }}>
                      {c.spread}
                    </td>
                    <td className="px-2 py-2 tabular-nums">{c.avg}</td>
                    <td className="px-2 py-2 tabular-nums text-muted">{c.ai_score ?? "—"}</td>
                    <td className="px-2 py-2">{c.agreed ? "✓" : "✕"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
