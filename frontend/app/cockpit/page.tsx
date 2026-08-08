"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import DistBars from "@/components/DistBars";
import StatTile from "@/components/StatTile";
import { api, CATEGORY_LABELS, fmtDuration, VIOLATION_LABELS } from "@/lib/api";
import type {
  SupervisorCockpit, TopicsResult, CoachingEffectiveness, ReviewStats, EmergingTopic,
  ExecSummary, CorrelationInsight, TargetProgress, ChurnSummary, AppealAnalytics,
} from "@/lib/types";

export default function CockpitPage() {
  const t = useT();
  const [c, setC] = useState<SupervisorCockpit | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.cockpit().then(setC).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="card p-6 text-sm">{t("common.error")}: {error}</p>;
  if (!c) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold">{t("cockpit.title")}</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label={t("cockpit.avgQuality")} value={c.avg_score != null ? c.avg_score.toFixed(1) : "—"} hint="0–100" />
        <StatTile label={t("stat.csat")} value={c.avg_csat != null ? `${c.avg_csat}/5` : "—"} />
        <StatTile
          label={c.fcr_is_real ? t("cockpit.fcrReal") : t("cockpit.fcrEst")}
          value={c.fcr_estimate != null ? `%${c.fcr_estimate}` : "—"}
          hint={`${t("cockpit.repeatCalls")}: ${c.repeat_calls}`}
        />
        <StatTile label={t("cockpit.aht")} value={fmtDuration(c.avg_handle_sec)} hint="AHT" />
        <StatTile label={t("stat.crisis")} value={String(c.crisis_calls)} />
        <StatTile label={t("stat.zeroed")} value={String(c.zeroed_calls)} />
        <StatTile label={t("cockpit.repeatCalls")} value={String(c.repeat_calls)} hint="7d" />
        <Link href="/workflow" className="block">
          <StatTile label={t("cockpit.unreadAlerts")} value={String(c.unread_alerts)} hint={`${t("nav.workflow")} →`} />
        </Link>
      </div>

      <ExecSummaryPanel />

      <div className="grid gap-5 lg:grid-cols-2">
        <TargetsPanel />
        <CorrelationsPanel />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChurnPanel />
        <AppealsPanel />
      </div>

      <EmergingPanel />

      <TopicsPanel />

      <div className="grid gap-5 lg:grid-cols-2">
        <CoachingEffectPanel />
        <ReviewPanel />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <DistBars title={t("cockpit.violationDist")}
          items={Object.entries(c.violation_dist).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: VIOLATION_LABELS[k] ?? k, value: v }))} />
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-ink2">{t("cockpit.teamBoard")}</h3>
          <div className="mt-2 space-y-1">
            {c.agents.slice(0, 12).map((a, i) => (
              <Link key={a.agent_id} href={`/agents/${a.agent_id}`}
                className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-grid/50">
                <span className="w-5 text-right font-semibold text-muted">{i + 1}</span>
                <span className="flex-1 font-medium">{a.agent_name}</span>
                <span className="text-xs text-muted">{a.call_count}</span>
                <span className="font-semibold tabular-nums">{a.avg_score.toFixed(1)}</span>
              </Link>
            ))}
            {c.agents.length === 0 && <p className="py-4 text-center text-sm text-muted">{t("common.noData")}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Churn/retention panosu: kayıp riski dağılımı + yüksek riskli takip listesi. */
function ChurnPanel() {
  const t = useT();
  const [d, setD] = useState<ChurnSummary | null>(null);
  useEffect(() => { api.churn(30).then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">📉 {t("churn.title")}</h3>
      <p className="mb-2 text-xs text-muted">{t("churn.desc")}</p>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold text-[var(--status-critical)] tabular-nums">{d.high}</div><div className="text-[10px] text-muted">{t("risk.yuksek")}</div></div>
        <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold text-[var(--status-warn)] tabular-nums">{d.medium}</div><div className="text-[10px] text-muted">{t("risk.orta")}</div></div>
        <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold text-[var(--status-ok)] tabular-nums">{d.low}</div><div className="text-[10px] text-muted">{t("risk.dusuk")}</div></div>
      </div>
      {d.retention_list.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold text-ink2">{t("churn.retention")} (%{d.high_rate})</p>
          <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
            {d.retention_list.map((c) => (
              <Link key={c.id} href={`/calls/${c.id}`} className="flex items-center gap-2 rounded-lg px-2 py-1 text-xs hover:bg-grid/50">
                <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--status-critical)]" />
                <span className="flex-1 truncate">{c.agent_name ?? "—"} · {CATEGORY_LABELS[c.category ?? ""] ?? c.category}</span>
                <span className="tabular-nums text-muted">{c.total_score ?? "—"}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** İtiraz analitiği: overturn oranı = AI kalibrasyon sinyali. */
function AppealsPanel() {
  const t = useT();
  const [d, setD] = useState<AppealAnalytics | null>(null);
  useEffect(() => { api.appealAnalytics(90).then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">⚖️ {t("appeals.title")}</h3>
      <p className="mb-2 text-xs text-muted">{t("appeals.desc")}</p>
      {d.total === 0 ? (
        <p className="py-6 text-center text-sm text-muted">{t("appeals.empty")}</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 text-center lg:grid-cols-4">
            <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">{d.total}</div><div className="text-[10px] text-muted">{t("appeals.total")}</div></div>
            <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">{d.open}</div><div className="text-[10px] text-muted">{t("appeals.open")}</div></div>
            <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold text-[var(--status-warn)] tabular-nums">%{d.overturn_rate}</div><div className="text-[10px] text-muted">{t("appeals.overturn")}</div></div>
            <div className="rounded-lg bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">{d.avg_resolution_days ?? "—"}</div><div className="text-[10px] text-muted">{t("appeals.avgDays")}</div></div>
          </div>
          <p className="mt-2 text-xs text-muted">✅ {d.accepted} {t("appeals.accepted")} · ❌ {d.rejected} {t("appeals.rejected")}</p>
        </>
      )}
    </div>
  );
}

/** Yönetici özeti: dönemin metriklerinden LLM ile kısa yönetici brifingi. */
function ExecSummaryPanel() {
  const t = useT();
  const [d, setD] = useState<ExecSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const gen = useCallback(async () => {
    setBusy(true); setErr("");
    try { setD(await api.execSummary(30)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }, []);
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink2">🧭 {t("exec.title")}</h3>
          <p className="mt-0.5 text-xs text-muted">{t("exec.desc")}</p>
        </div>
        <button className="btn btn-primary !py-1 text-xs" disabled={busy} onClick={gen}>
          {busy ? t("exec.generating") : `✨ ${t("exec.generate")}`}
        </button>
      </div>
      {err && <p className="mt-2 text-xs text-danger">{t("common.error")}: {err}</p>}
      {d && (
        <div className="mt-3 space-y-3">
          <p className="rounded-lg bg-series/10 p-3 text-sm font-medium leading-relaxed">{d.headline}</p>
          <div className="grid gap-3 md:grid-cols-3">
            {([["exec.wins", "✅", d.wins], ["exec.risks", "⚠️", d.risks], ["exec.actions", "🎯", d.actions]] as const).map(([k, ic, arr]) => (
              <div key={k} className="rounded-lg bg-grid/40 p-3">
                <div className="mb-1 text-xs font-semibold text-ink2">{ic} {t(k)}</div>
                <ul className="space-y-1 text-sm">
                  {arr.length ? arr.map((x, i) => <li key={i} className="leading-snug">• {x}</li>)
                    : <li className="text-muted">—</li>}
                </ul>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-muted">{t("exec.basedOn").replace("{n}", String(d.call_count)).replace("{d}", String(d.period_days))}</p>
        </div>
      )}
    </div>
  );
}

/** Korelasyon içgörüleri: hangi davranış kalite puanıyla ilişkili (Pearson). */
function CorrelationsPanel() {
  const t = useT();
  const [rows, setRows] = useState<CorrelationInsight[] | null>(null);
  useEffect(() => { api.correlations(90).then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return null;
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">🔗 {t("corr.title")}</h3>
      <p className="mb-2 text-xs text-muted">{t("corr.desc")}</p>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">{t("corr.empty")}</p>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.factor} className="flex items-center gap-2 text-sm">
              <span className={`w-10 text-right font-bold tabular-nums ${r.direction === "positive" ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
                {r.corr > 0 ? "+" : ""}{r.corr}
              </span>
              <span className="flex-1">{r.insight}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const TARGET_METRICS: Record<string, string> = {
  quality: "Kalite (0-100)", csat: "CSAT (1-5)",
  zeroed_rate: "Sıfırlanma %", fcr: "İlk Temasta Çözüm %",
};

/** Hedefler & takip: kurum/temsilci metrik hedefi + gerçekleşme. */
function TargetsPanel() {
  const t = useT();
  const [rows, setRows] = useState<TargetProgress[] | null>(null);
  const [agents, setAgents] = useState<{ id: number; name: string }[]>([]);
  const [scope, setScope] = useState("tenant");
  const [scopeId, setScopeId] = useState<number | "">("");
  const [metric, setMetric] = useState("quality");
  const [value, setValue] = useState(80);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { api.targetProgress(30).then(setRows).catch(() => setRows([])); }, []);
  useEffect(() => {
    load();
    api.listAgents?.().then((a) => setAgents(a.map((x) => ({ id: x.id, name: x.name })))).catch(() => {});
  }, [load]);

  async function add() {
    setBusy(true);
    try {
      await api.createTarget({ scope, scope_id: scope === "agent" ? Number(scopeId) || null : null, metric, target_value: value });
      load();
    } catch (e) { alert(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function del(id: number) {
    try { await api.deleteTarget(id); load(); } catch { /* yoksay */ }
  }

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">🎯 {t("targets.title")}</h3>
      <p className="mb-2 text-xs text-muted">{t("targets.desc")}</p>
      {rows && rows.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center gap-2 text-sm">
              <span className={`h-2 w-2 shrink-0 rounded-full ${r.actual == null ? "bg-muted" : r.met ? "bg-[var(--status-ok)]" : "bg-[var(--status-critical)]"}`} />
              <span className="flex-1 truncate">{r.scope_name} · {TARGET_METRICS[r.metric] ?? r.metric}</span>
              <span className="tabular-nums text-muted">{t("targets.target")} {r.target_value}</span>
              <span aria-hidden>→</span>
              <span className={`font-semibold tabular-nums ${r.actual == null ? "text-muted" : r.met ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
                {r.actual == null ? "—" : r.actual}
              </span>
              <button className="text-muted hover:text-[var(--status-critical)]" onClick={() => del(r.id)} aria-label="sil">×</button>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2 border-t border-hairline pt-3 text-xs">
        <select className="input text-xs" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="tenant">{t("targets.tenant")}</option>
          <option value="agent">{t("targets.agent")}</option>
        </select>
        {scope === "agent" && (
          <select className="input text-xs" value={scopeId} onChange={(e) => setScopeId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">{t("targets.selectAgent")}</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}
        <select className="input text-xs" value={metric} onChange={(e) => setMetric(e.target.value)}>
          {Object.entries(TARGET_METRICS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="number" className="input w-20 text-xs" value={value} onChange={(e) => setValue(Number(e.target.value))} />
        <button className="btn btn-primary !py-1 text-xs" disabled={busy || (scope === "agent" && scopeId === "")} onClick={add}>
          ＋ {t("common.add")}
        </button>
      </div>
    </div>
  );
}

/** Yükselen konular: bu dönem geçen döneme göre hangi konu/etiket hızla artıyor? */
function EmergingPanel() {
  const t = useT();
  const [rows, setRows] = useState<EmergingTopic[] | null>(null);
  useEffect(() => { api.emergingTopics(7).then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return null;

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink2">📈 {t("emerging.title")}</h3>
          <p className="mt-0.5 text-xs text-muted">{t("emerging.desc")}</p>
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">{t("emerging.empty")}</p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {rows.map((r, i) => (
            <div key={i} className="flex items-center gap-2 rounded-lg bg-grid/40 px-3 py-2">
              <span className="text-xs text-muted">{r.kind === "category" ? "🏷" : "🎯"}</span>
              <span className="text-sm font-medium">{CATEGORY_LABELS[r.label] ?? r.label}</span>
              <span className="text-xs tabular-nums text-muted">{r.prev_count}→{r.now_count}</span>
              <span className="badge badge-warn text-xs">▲ %{r.change_pct}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Konu keşfi: "müşteriler bu dönem NEDEN arıyor?" — kök-neden kümeleme. */
function TopicsPanel() {
  const t = useT();
  const [data, setData] = useState<TopicsResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async (refresh = false) => {
    setBusy(true); setErr("");
    try { setData(await api.topics(30, refresh)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink2">
            {t("topics.title")} <span className="text-xs font-normal text-muted">(30d)</span>
          </h3>
          <p className="mt-0.5 text-xs text-muted">{t("topics.desc")}</p>
        </div>
        <button className="btn !py-1 text-xs" disabled={busy} onClick={() => load(true)}>
          {busy ? t("topics.analyzing") : t("topics.reanalyze")}
        </button>
      </div>

      {err && <p className="mt-3 text-sm text-ink2">{err}</p>}
      {busy && !data && <p className="py-6 text-center text-sm text-muted">{t("topics.analyzing")}</p>}

      {data && data.topics.length === 0 && (
        <p className="py-6 text-center text-sm text-muted">{t("topics.empty")}</p>
      )}

      {data && data.topics.length > 0 && (
        <>
          <div className="mt-3 space-y-2">
            {data.topics.map((tp, i) => (
              <div key={i} className="rounded-lg bg-grid/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{tp.baslik}</span>
                  <span className="badge badge-info">{tp.cagri_sayisi}</span>
                  {tp.ortalama_puan != null && (
                    <span className="text-xs text-muted">{tp.ortalama_puan}</span>
                  )}
                  {Object.entries(tp.kategoriler).map(([k, n]) => (
                    <span key={k} className="badge badge-neutral text-xs">
                      {CATEGORY_LABELS[k] ?? k} ×{n}
                    </span>
                  ))}
                </div>
                {tp.kok_neden && (
                  <p className="mt-1.5 text-sm text-ink2">
                    <b>{t("topics.rootCause")}:</b> {tp.kok_neden}
                  </p>
                )}
                {tp.aksiyon && (
                  <p className="mt-1 text-sm text-ink2">
                    <b>💡 {t("topics.action")}:</b> {tp.aksiyon}
                  </p>
                )}
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {tp.ornek_cagrilar.map((ex) => (
                    <Link key={ex.id} href={`/calls/${ex.id}`}
                      className="text-xs text-series hover:underline" title={ex.ozet}>
                      #{ex.id} {ex.filename}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {data.cached && (
            <p className="mt-2 text-xs text-muted">cache 6h</p>
          )}
        </>
      )}
    </div>
  );
}

/** Koçluk etkinliği: koçluk sonrası puan gerçekten arttı mı? (Dalga 2c) */
function CoachingEffectPanel() {
  const t = useT();
  const [d, setD] = useState<CoachingEffectiveness | null>(null);
  useEffect(() => { api.coachingEffectiveness().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">🎯 {t("coacheff.title")}</h3>
      <p className="mb-2 text-xs text-muted">{t("coacheff.hint")}</p>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-grid/40 p-2">
          <div className="text-lg font-bold">{d.measurable_count}</div>
          <div className="text-[10px] text-muted">{t("coacheff.measurable")}</div>
        </div>
        <div className="rounded-lg bg-grid/40 p-2">
          <div className="text-lg font-bold text-[var(--status-ok)]">%{d.improved_rate}</div>
          <div className="text-[10px] text-muted">{t("coacheff.improved")}</div>
        </div>
        <div className="rounded-lg bg-grid/40 p-2">
          <div className={`text-lg font-bold ${d.avg_delta >= 0 ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
            {d.avg_delta > 0 ? "+" : ""}{d.avg_delta}
          </div>
          <div className="text-[10px] text-muted">{t("coacheff.avgDelta")}</div>
        </div>
      </div>
      {d.effects.slice(0, 4).map((e) => (
        <div key={e.task_id} className="mt-2 flex items-center gap-2 text-xs">
          <span className="flex-1 font-medium">{e.agent_name}</span>
          <span className="text-muted">{t("coacheff.before")} {e.before_avg}</span>
          <span aria-hidden>→</span>
          <span className="text-muted">{t("coacheff.after")} {e.after_avg}</span>
          <span className={`font-semibold ${e.improved ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
            {e.delta > 0 ? "+" : ""}{e.delta}
          </span>
        </div>
      ))}
      {d.effects.length === 0 && <p className="mt-2 text-center text-xs text-muted">{t("common.noData")}</p>}
    </div>
  );
}

/** QA inceleme kuyruğu özeti + örnek oluşturma (Dalga 2b) */
function ReviewPanel() {
  const t = useT();
  const [s, setS] = useState<ReviewStats | null>(null);
  const [users, setUsers] = useState<{ id: number; name: string; role: string }[]>([]);
  const [reviewer, setReviewer] = useState<number | "">("");
  const [reason, setReason] = useState("random");
  const [count, setCount] = useState(5);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.reviewStats().then(setS).catch(() => {});
  useEffect(() => {
    load();
    api.listUsers().then((u) => setUsers(u.filter((x) => x.role !== "agent"))).catch(() => {});
  }, []);

  async function createSample() {
    if (reviewer === "") return;
    setBusy(true); setMsg("");
    try {
      const out = await api.createSample({ reviewer_id: Number(reviewer), reason, count });
      setMsg(`${out.length} ${t("rev.assigned")}`);
      load();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">🔍 {t("review.title")}</h3>
      {s && (
        <>
          <div className="mt-2 flex items-center gap-3">
            <div className="text-3xl font-bold">%{s.completion_rate}</div>
            <div className="text-xs text-muted">{t("review.completion")} · {s.total} {t("rev.total")}</div>
          </div>
          <div className="mt-3 flex gap-2 text-center text-xs">
            {Object.entries(s.counts).map(([k, v]) => (
              <div key={k} className="flex-1 rounded-lg bg-grid/40 p-2">
                <div className="text-base font-semibold">{v}</div>
                <div className="text-[10px] text-muted">{k}</div>
              </div>
            ))}
          </div>
        </>
      )}
      {/* Örnek oluştur */}
      <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-hairline pt-3">
        <label className="text-xs">
          <span className="block text-muted">{t("rev.reviewer")}</span>
          <select value={reviewer} onChange={(e) => setReviewer(e.target.value === "" ? "" : Number(e.target.value))}
            className="mt-0.5 rounded-lg border border-hairline bg-surface2 px-2 py-1 text-sm">
            <option value="">{t("rev.select")}</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="block text-muted">{t("rev.strategy")}</span>
          <select value={reason} onChange={(e) => setReason(e.target.value)}
            className="mt-0.5 rounded-lg border border-hairline bg-surface2 px-2 py-1 text-sm">
            <option value="random">{t("wf.reason.random")}</option>
            <option value="low_confidence">{t("wf.reason.low_confidence")}</option>
            <option value="critical">{t("wf.reason.critical")}</option>
          </select>
        </label>
        <label className="text-xs">
          <span className="block text-muted">{t("rev.count")}</span>
          <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Number(e.target.value))}
            className="mt-0.5 w-16 rounded-lg border border-hairline bg-surface2 px-2 py-1 text-sm" />
        </label>
        <button className="btn btn-primary !py-1 text-xs" disabled={busy || reviewer === ""} onClick={createSample}>
          {busy ? "…" : t("rev.sampleAssign")}
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-ink2">{msg}</p>}
    </div>
  );
}
