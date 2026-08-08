"use client";

import { useT } from "@/components/I18nProvider";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { CategoryChip, ChannelChip, CrisisChip, ScoreBadge, StatusChip, ZeroedChip } from "@/components/Badges";
import StatTile from "@/components/StatTile";
import { useAuth } from "@/components/AuthProvider";
import {
  api, fetchAudioObjectUrl, fmtDate, fmtDuration, fmtTs, scoreStatus10,
  SENTIMENT_LABELS, VIOLATION_LABELS,
} from "@/lib/api";
import type { CallDetail, Score, SelfAssessment } from "@/lib/types";

const SPEAKER_KEYS: Record<string, string> = { musteri: "speaker.customer", temsilci: "speaker.agent", bilinmeyen: "speaker.unknown" };
const SEVERITY: Record<string, { key: string; cls: string }> = {
  dusuk: { key: "sev.low", cls: "badge-neutral" },
  orta: { key: "sev.mid", cls: "badge-warning" },
  yuksek: { key: "sev.high", cls: "badge-critical" },
};

export default function CallDetailPage() {
  const t = useT();
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  // Aramadan gelindiyse (?t=12.5) sesin o anina atla
  const jumpTo = searchParams.get("t");
  const { me } = useAuth();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [error, setError] = useState("");
  const [audioSrc, setAudioSrc] = useState("");
  const [audioError, setAudioError] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const [autoFollow, setAutoFollow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reveal, setReveal] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  const isQuality = me && (me.role === "quality" || me.role === "admin");
  const isStaff = me && me.role !== "agent";
  const isAgentOwner = me?.role === "agent";
  const canCoach = me && (me.role === "supervisor" || me.role === "admin");

  const load = useCallback(async () => {
    try { setCall(await api.getCall(id, reveal)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, [id, reveal]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!call || call.channel !== "voice") return;
    let url = "";
    setAudioError("");
    fetchAudioObjectUrl(call.id)
      .then((u) => { url = u; setAudioSrc(u); })
      .catch((e) => setAudioError(e instanceof Error ? e.message : t("call.noAudio")));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [call?.id, call?.channel]);

  useEffect(() => {
    if (!call || call.status === "done" || call.status === "failed") return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [call, load]);

  const activeIdx = call ? call.segments.findIndex((s) => currentTime >= s.start_sec && currentTime < s.end_sec) : -1;
  useEffect(() => {
    if (autoFollow && activeRef.current) activeRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIdx, autoFollow]);

  function seek(t: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = t;
    audio.play().catch(() => {});
  }

  // Arama sonucundan gelindiyse (?t=12.5) o ana konumlan.
  // Sesli: player'i o saniyeye al (otomatik CALMAZ). Chat: ilgili mesaji vurgula.
  const [jumped, setJumped] = useState(false);
  useEffect(() => {
    if (!jumpTo || jumped || !call) return;
    const t = parseFloat(jumpTo);
    if (!Number.isFinite(t)) return;
    if (call.channel === "voice") {
      if (!audioSrc || !audioRef.current) return; // ses hazir olunca tekrar denenir
      audioRef.current.currentTime = t;
    }
    setCurrentTime(t);
    setJumped(true);
  }, [jumpTo, jumped, audioSrc, call]);

  async function rescore() {
    if (!call) return;
    setBusy(true);
    try { await api.rescoreCall(call.id); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function appeal() {
    if (!call) return;
    const reason = prompt(t("call.appealPrompt"));
    if (!reason) return;
    try { await api.createAppeal({ call_id: call.id, reason }); alert(t("call.appealSent")); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  async function assignCoaching() {
    if (!call?.agent) { alert(t("call.noAgentAssigned")); return; }
    const note = prompt(t("call.coachPrompt"));
    if (note === null) return;
    try {
      await api.createCoaching({ call_id: call.id, assignee_agent_id: call.agent.id, note });
      alert(t("call.coachAssigned"));
    } catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  if (error) return <p className="card p-6 text-sm">{t("common.error")}: {error}</p>;
  if (!call) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  const isChat = call.channel === "chat";
  const m = call.metrics ?? {};
  const sortedScores = [...call.scores].sort((a, b) => a.effective_score - b.effective_score);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{call.filename}</h1>
          <p className="mt-1 text-sm text-ink2">
            {call.agent?.name ?? t("call.noAgent")}
            {call.campaign && ` · ${call.campaign.name}`} · {fmtDuration(call.duration_sec)} · {fmtDate(call.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ChannelChip channel={call.channel} />
          <CategoryChip category={call.category} />
          {call.is_crisis && <CrisisChip />}
          {call.zeroed && <ZeroedChip />}
          <StatusChip status={call.status} />
          <span className="text-lg font-semibold"><ScoreBadge score={call.total_score} zeroed={call.zeroed} /></span>
          {isStaff && (
            <button className="btn" onClick={rescore} disabled={busy || (call.status !== "done" && call.status !== "failed")}>
              {busy ? "…" : t("call.rescore")}
            </button>
          )}
          {canCoach && call.agent && (
            <button className="btn" onClick={assignCoaching}>{t("call.assignCoaching")}</button>
          )}
          {isAgentOwner && call.status === "done" && (
            <button className="btn" onClick={appeal}>{t("call.appeal")}</button>
          )}
        </div>
      </div>

      {isStaff && <GoldenTags call={call} onSaved={load} />}

      {call.status === "failed" && call.error && (
        <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>
          {t("call.processError")}: {call.error}
        </p>
      )}

      {call.summary && <p className="card p-4 text-sm leading-relaxed text-ink2">{call.summary}</p>}

      {/* Metrikler — kanala göre */}
      {call.metrics && Object.keys(m).length > 0 && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {isChat ? (
            <>
              <StatTile label={t("metric.firstResponse")} value={`${m.ilk_yanit_sn ?? 0} sn`}  />
              <StatTile label={t("metric.avgResponse")} value={`${m.ortalama_yanit_sn ?? 0} sn`}  />
              <StatTile label={t("metric.agentMsgs")} value={String(m.temsilci_mesaj ?? 0)} hint={String(m.toplam_mesaj ?? 0)} />
              <StatTile label={t("metric.customerMsgs")} value={String(m.musteri_mesaj ?? 0)} />
            </>
          ) : (
            <>
              <StatTile label={t("metric.talkRatio")} value={`%${m.temsilci_konusma_orani ?? "—"}`} hint={`temsilci ${m.temsilci_konusma_sn ?? 0}sn · müşteri ${m.musteri_konusma_sn ?? 0}sn`} />
              <StatTile label={t("metric.interruptions")} value={String(m.temsilci_kesinti ?? 0)} hint={`müşteri: ${m.musteri_kesinti ?? 0}`} />
              <StatTile label={t("metric.silence")} value={`${m.sessizlik_sn ?? 0} sn`} hint={`en uzun ${m.en_uzun_sessizlik_sn ?? 0}sn`} />
              <StatTile label={t("metric.speechRate")} value={String(m.temsilci_kelime_dk ?? "—")} hint="kelime/dk" />
            </>
          )}
        </div>
      )}

      {/* Akustik: NASIL söyledi (ses tonu / bağırma / monotonluk) */}
      {!isChat && (m.temsilci_pitch_hz != null || m.temsilci_bagirma_sayisi != null) && (
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-ink2">{t("call.acoustic")}</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-lg bg-grid/40 p-3">
              <div className="text-xs text-ink2">{t("metric.pitch")}</div>
              <div className="text-xl font-semibold">{m.temsilci_pitch_hz ?? "—"} <span className="text-xs font-normal text-muted">Hz</span></div>
              <div className="mt-0.5 text-xs text-muted">
                {m.temsilci_monoton ? t("metric.monotone") : t("metric.lively")}
              </div>
            </div>
            <div className="rounded-lg bg-grid/40 p-3">
              <div className="text-xs text-ink2">{t("metric.agentShouting")}</div>
              <div className={`text-xl font-semibold ${(m.temsilci_bagirma_sayisi ?? 0) > 0 ? "text-[var(--status-critical)]" : ""}`}>
                {m.temsilci_bagirma_sayisi ?? 0}
              </div>
              
            </div>
            <div className="rounded-lg bg-grid/40 p-3">
              <div className="text-xs text-ink2">{t("metric.customerShouting")}</div>
              <div className="text-xl font-semibold">{m.musteri_bagirma_sayisi ?? 0}</div>
              
            </div>
            <div className="rounded-lg bg-grid/40 p-3">
              <div className="text-xs text-ink2">{t("metric.pitchVariety")}</div>
              <div className="text-xl font-semibold">{m.temsilci_tonlama_sapmasi ?? "—"} <span className="text-xs font-normal text-muted">Hz</span></div>
              
            </div>
          </div>
          {(m.temsilci_bagirma_anlari?.length || m.musteri_bagirma_anlari?.length) ? (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-ink2">{t("metric.agentShouting")}:</span>
              {(m.temsilci_bagirma_anlari ?? []).map((ts, i) => (
                <button key={`t${i}`} className="btn !px-2 !py-0.5 text-xs tabular-nums"
                  onClick={() => seek(ts)} title={t("speaker.agent")}>▶ {fmtTs(ts)} <span className="text-series">T</span></button>
              ))}
              {(m.musteri_bagirma_anlari ?? []).map((ts, i) => (
                <button key={`m${i}`} className="btn !px-2 !py-0.5 text-xs tabular-nums"
                  onClick={() => seek(ts)} title={t("speaker.customer")}>▶ {fmtTs(ts)} <span className="text-muted">M</span></button>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {/* Duygu + koçluk + CSAT */}
      {(call.sentiment_start || call.coaching || call.predicted_csat != null) && (
        <div className="card space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {call.sentiment_start && call.sentiment_end && (
              <>
                <span className="font-semibold text-ink2">{t("call.sentiment")}:</span>
                <span className={`badge ${SENTIMENT_LABELS[call.sentiment_start]?.cls ?? "badge-neutral"}`}>
                  <span className="dot" aria-hidden />{SENTIMENT_LABELS[call.sentiment_start]?.label}
                </span>
                <span aria-hidden className="text-muted">→</span>
                <span className={`badge ${SENTIMENT_LABELS[call.sentiment_end]?.cls ?? "badge-neutral"}`}>
                  <span className="dot" aria-hidden />{SENTIMENT_LABELS[call.sentiment_end]?.label}
                </span>
              </>
            )}
            {call.predicted_csat != null && (
              <span className="ml-auto text-sm text-ink2">Tahmini CSAT: <b>{call.predicted_csat}/5</b></span>
            )}
          </div>
          {call.coaching && (
            <p className="flex items-start gap-2 text-sm leading-relaxed">
              <span aria-hidden>💡</span>
              <span><span className="font-semibold text-ink2">{t("call.coaching")}: </span>{call.coaching}</span>
            </p>
          )}
        </div>
      )}

      {/* Yapay Zekâ Analizi (Dalga 1) */}
      {(call.emotion || call.churn_risk || call.next_action || call.customer_effort != null
        || (call.intent_tags?.length ?? 0) > 0) && (
        <div className="card space-y-3 p-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-ink2">🧠 {t("analytics.title")}</h2>
            {call.emotion_mismatch && (
              <span className="badge badge-warn" title={t("analytics.mismatch")}>
                <span className="dot" aria-hidden />⚠ {t("analytics.mismatch")}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {call.emotion && (
              <div className="rounded-lg bg-grid/40 p-3">
                <div className="text-xs text-ink2">{t("analytics.emotion")}</div>
                <div className="text-lg font-semibold">{t(`emotion.${call.emotion}`)}</div>
                {call.sentiment_trajectory && (
                  <div className="mt-0.5 text-xs text-muted">{t(`traj.${call.sentiment_trajectory}`)}</div>
                )}
              </div>
            )}
            {call.churn_risk && (
              <div className="rounded-lg bg-grid/40 p-3">
                <div className="text-xs text-ink2">{t("analytics.churn")}</div>
                <div className={`text-lg font-semibold ${
                  call.churn_risk === "yuksek" ? "text-[var(--status-critical)]"
                  : call.churn_risk === "orta" ? "text-[var(--status-warn)]" : ""
                }`}>{t(`risk.${call.churn_risk}`)}</div>
              </div>
            )}
            {call.customer_effort != null && (
              <div className="rounded-lg bg-grid/40 p-3" title={t("analytics.ces.hint")}>
                <div className="text-xs text-ink2">{t("analytics.ces")}</div>
                <div className="text-lg font-semibold">{call.customer_effort}<span className="text-xs font-normal text-muted">/5</span></div>
              </div>
            )}
            {call.predicted_csat != null && (
              <div className="rounded-lg bg-grid/40 p-3">
                <div className="text-xs text-ink2">CSAT</div>
                <div className="text-lg font-semibold">{call.predicted_csat}<span className="text-xs font-normal text-muted">/5</span></div>
              </div>
            )}
          </div>
          {call.next_action && (
            <p className="flex items-start gap-2 rounded-lg bg-series/10 p-3 text-sm leading-relaxed">
              <span aria-hidden>🎯</span>
              <span><span className="font-semibold text-ink2">{t("analytics.next_action")}: </span>{call.next_action}</span>
            </p>
          )}
          {(call.intent_tags?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-semibold text-ink2">{t("analytics.intents")}:</span>
              {call.intent_tags.map((tag) => (
                <span key={tag} className="badge badge-neutral text-xs">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Koçluk görevleri — kapanış döngüsü (Dalga 7) */}
      {isStaff || (me?.role === "agent" && call.agent?.id === me.agent_id) ? (
        <CoachingTasksPanel callId={call.id} isAgent={me?.role === "agent"} onChanged={load} />
      ) : null}

      {/* Temsilci öz-değerlendirmesi (Dalga 3c) */}
      {me?.role === "agent" && call.agent?.id === me.agent_id && (
        <SelfAssessmentCard callId={call.id} />
      )}

      {/* İhlaller */}
      {call.violations.length > 0 && (
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-ink2">{t("call.violations")}</h2>
          <ul className="mt-2 space-y-2">
            {call.violations.map((v, i) => {
              const sev = SEVERITY[v.severity] ?? SEVERITY.orta;
              return (
                <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                  {v.ts_sec != null && !isChat && (
                    <button className="btn shrink-0 !px-2 !py-0.5 text-xs tabular-nums" onClick={() => seek(v.ts_sec!)}>▶ {fmtTs(v.ts_sec)}</button>
                  )}
                  <span className={`badge ${sev.cls} shrink-0`}><span className="dot" aria-hidden />{t(sev.key)}</span>
                  <span className="badge badge-neutral">{VIOLATION_LABELS[v.category] ?? v.category}</span>
                  <span className="text-ink2">{t(v.speaker === "temsilci" ? "speaker.agent" : "speaker.customer")}:</span>
                  <span className="text-ink">&ldquo;{v.evidence}&rdquo;</span>
                  {v.term && <span className="text-xs text-muted">({v.term})</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Ses/transkript */}
      <div className="card p-4">
        {!isChat && audioSrc && (
          <audio ref={audioRef} controls preload="metadata" className="w-full" src={audioSrc}
            onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)} />
        )}
        {!isChat && !audioSrc && (
          <p className="rounded-lg bg-grid/50 p-3 text-sm text-ink2">
            {audioError ? `🔇 ${t("call.noAudio")}: ${audioError}` : `⏳ ${t("call.loadingAudio")}`}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink2">
            {isChat ? t("call.chatLog") : t("call.transcript")} ({call.segments.length})
            {call.pii_masked && (
              <span className="badge badge-neutral" title={t("call.kvkkMaskActive")}>🔒 KVKK</span>
            )}
          </h2>
          <div className="flex items-center gap-3">
            {/* KVKK: transkript varsayilan maskeli; admin/kalite ham veriyi acabilir (denetime yazilir) */}
            {isQuality && call.pii_masked && (
              <button className="btn !py-1 text-xs" onClick={() => setReveal(true)}>👁 {t("call.reveal")}</button>
            )}
            {isQuality && reveal && !call.pii_masked && (
              <button className="btn !py-1 text-xs" onClick={() => setReveal(false)}>🔒 {t("call.mask")}</button>
            )}
            {!isChat && (
              <label className="flex items-center gap-1.5 text-xs text-ink2">
                <input type="checkbox" checked={autoFollow} onChange={(e) => setAutoFollow(e.target.checked)} />
                {t("call.autoFollow")}
              </label>
            )}
          </div>
        </div>
        <div className="mt-2 max-h-96 space-y-1 overflow-y-auto pr-1">
          {call.segments.map((seg, i) => (
            <button key={seg.idx} ref={i === activeIdx ? activeRef : undefined}
              onClick={() => !isChat && seek(seg.start_sec)}
              className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm ${i === activeIdx ? "bg-grid" : "hover:bg-grid/50"} ${isChat ? "cursor-default" : ""}`}>
              {!isChat && <span className="mr-2 text-xs tabular-nums text-muted">{fmtTs(seg.start_sec)}</span>}
              <span className={`mr-2 text-xs font-semibold ${seg.speaker === "temsilci" ? "text-series" : "text-ink2"}`}>
                {t(SPEAKER_KEYS[seg.speaker] ?? "speaker.unknown")}
              </span>
              <span className="text-ink">{seg.text}</span>
            </button>
          ))}
          {call.segments.length === 0 && <p className="py-6 text-center text-sm text-muted">{t("common.noData")}</p>}
        </div>
      </div>

      {isStaff && <SimilarCalls callId={call.id} />}

      {/* Puan kartları */}
      {sortedScores.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink2">{t("call.criteriaBreakdown")}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {sortedScores.map((s, idx) => (
              <ScoreCard key={idx} score={s} canOverride={!!isQuality} seek={!isChat ? seek : undefined} onSaved={load} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ score: s, canOverride, seek, onSaved }: {
  score: Score; canOverride: boolean; seek?: (t: number) => void; onSaved: () => void;
}) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(s.effective_score);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const status = scoreStatus10(s.effective_score);
  const STATUS_VAR2: Record<string, string> = {
    good: "var(--status-good)", warning: "var(--status-warning)", critical: "var(--status-critical)",
  };

  async function save() {
    if (reason.trim().length < 3) { alert(t("call.reasonMin")); return; }
    setBusy(true);
    try {
      await api.overrideScore(s.id, { override_score: val, override_reason: reason });
      setEditing(false);
      onSaved();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="card border-l-4 p-4" style={{ borderLeftColor: STATUS_VAR2[status] }}>
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <span className="text-xs text-muted">{s.criterion_group}</span>
          <h3 className="font-semibold">{s.criterion_name}</h3>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold tabular-nums">
            {s.effective_score}<span className="text-sm font-normal text-muted">/10</span>
          </div>
          {s.override_score != null && <div className="text-xs text-muted">AI: {s.score} · insan düzeltmesi</div>}
        </div>
      </div>
      <p className="mt-0.5 text-xs text-muted">ağırlık ×{s.weight}</p>
      {s.rationale && <p className="mt-2 text-sm leading-relaxed text-ink2">{s.rationale}</p>}
      {s.evidence && (
        <blockquote className="mt-2 flex items-start gap-2 rounded-lg bg-grid/50 p-2.5 text-sm italic">
          {s.evidence_ts != null && seek && (
            <button className="btn shrink-0 !px-2 !py-0.5 text-xs not-italic tabular-nums" onClick={() => seek(s.evidence_ts!)}>▶ {fmtTs(s.evidence_ts)}</button>
          )}
          <span>&ldquo;{s.evidence}&rdquo;</span>
        </blockquote>
      )}
      {s.override_reason && <p className="mt-2 text-xs text-ink2">Düzeltme gerekçesi: {s.override_reason}</p>}

      {canOverride && !editing && (
        <button className="btn mt-3 !py-0.5 text-xs" onClick={() => { setVal(s.effective_score); setReason(""); setEditing(true); }}>
          Puanı düzelt (kalibrasyon)
        </button>
      )}
      {canOverride && editing && (
        <div className="mt-3 space-y-2 rounded-lg bg-grid/40 p-3">
          <label className="flex items-center gap-2 text-sm">
            Yeni puan
            <input type="number" min={0} max={10} className="input w-20" value={val}
              onChange={(e) => setVal(Number(e.target.value))} />
          </label>
          <textarea className="input w-full text-sm" rows={2} placeholder={t("call.overrideReason")}
            value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="flex gap-2">
            <button className="btn btn-primary !py-0.5 text-xs" disabled={busy} onClick={save}>Kaydet</button>
            <button className="btn !py-0.5 text-xs" onClick={() => setEditing(false)}>{t("call.cancel")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Koçluk görevleri kapanış döngüsü: agent yorum yazıp tamamlar; staff durumu görür. */
function CoachingTasksPanel({ callId, isAgent, onChanged }: {
  callId: number; isAgent: boolean; onChanged: () => void;
}) {
  const t = useT();
  const [tasks, setTasks] = useState<import("@/lib/types").CoachingTask[] | null>(null);
  const [comment, setComment] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.listCoaching().then((all) => setTasks(all.filter((x) => x.call_id === callId))).catch(() => setTasks([]));
  }, [callId]);
  useEffect(() => { load(); }, [load]);

  async function complete(id: number) {
    const c = (comment[id] || "").trim();
    if (c.length < 3) { alert(t("coachtask.commentMin")); return; }
    setBusy(true);
    try { await api.completeCoaching(id, { agent_comment: c }); load(); onChanged(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  if (!tasks || tasks.length === 0) return null;
  return (
    <div className="card space-y-3 p-4">
      <h2 className="text-sm font-semibold text-ink2">🎯 {t("coachtask.title")}</h2>
      {tasks.map((tk) => (
        <div key={tk.id} className="rounded-lg border border-hairline p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className={`badge ${tk.status === "done" ? "badge-good" : "badge-warn"}`}>
              <span className="dot" aria-hidden />{tk.status === "done" ? t("coachtask.done") : t("coachtask.open")}
            </span>
            <span className="text-ink2">{tk.note}</span>
          </div>
          {tk.status === "done" && tk.agent_comment && (
            <p className="mt-2 rounded-lg bg-grid/40 p-2 text-xs text-ink2">
              <b>{t("coachtask.agentNote")}:</b> {tk.agent_comment}
            </p>
          )}
          {isAgent && tk.status === "open" && (
            <div className="mt-2 space-y-2">
              <textarea className="input w-full text-sm" rows={2} placeholder={t("coachtask.commentPh")}
                value={comment[tk.id] ?? ""} onChange={(e) => setComment((c) => ({ ...c, [tk.id]: e.target.value }))} />
              <button className="btn btn-primary !py-1 text-xs" disabled={busy} onClick={() => complete(tk.id)}>
                ✓ {t("coachtask.complete")}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Benzer geçmiş çağrılar: ortak niyet + kategori + puan yakınlığı (kalibrasyon/eğitim). */
function SimilarCalls({ callId }: { callId: number }) {
  const t = useT();
  const [rows, setRows] = useState<import("@/lib/types").SimilarCall[] | null>(null);
  useEffect(() => { api.similarCalls(callId, 8).then(setRows).catch(() => setRows([])); }, [callId]);
  if (!rows || rows.length === 0) return null;
  return (
    <div className="card p-4">
      <h2 className="text-sm font-semibold text-ink2">🧩 {t("similar.title")}</h2>
      <p className="mb-2 text-xs text-muted">{t("similar.desc")}</p>
      <div className="space-y-1">
        {rows.map((c) => (
          <a key={c.id} href={`/calls/${c.id}`} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-grid/50">
            <span className="w-10 text-right font-semibold tabular-nums text-series">%{Math.round(c.similarity * 100)}</span>
            <span className="flex-1 truncate">{c.agent_name ?? "—"} · {c.filename}</span>
            {c.shared_tags.slice(0, 2).map((tg) => <span key={tg} className="rounded bg-grid px-1.5 py-0.5 text-[10px] text-ink2">{tg}</span>)}
            <span className="tabular-nums text-muted">{c.total_score ?? "—"}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

/** Altin/ornek cagri isaretleme + serbest etiketleme (egitim kutuphanesi). */
function GoldenTags({ call, onSaved }: { call: CallDetail; onSaved: () => void }) {
  const t = useT();
  const [golden, setGolden] = useState(call.is_golden);
  const [tags, setTags] = useState<string[]>(call.tags ?? []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function toggleGolden() {
    setBusy(true);
    try { const r = await api.toggleGolden(call.id); setGolden(r.is_golden); onSaved(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function commit(next: string[]) {
    setBusy(true);
    try { const r = await api.setCallTags(call.id, next); setTags(r.tags ?? []); onSaved(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  function addTag() {
    const v = input.trim();
    if (!v || tags.includes(v)) { setInput(""); return; }
    setInput(""); commit([...tags, v]);
  }

  return (
    <div className="card flex flex-wrap items-center gap-2 p-3">
      <button className={`btn !py-1 text-xs ${golden ? "btn-primary" : ""}`} disabled={busy} onClick={toggleGolden}>
        {golden ? `⭐ ${t("golden.isGolden")}` : `☆ ${t("golden.mark")}`}
      </button>
      <span className="ml-1 text-xs text-ink2">{t("golden.tagsLabel")}:</span>
      {tags.map((tg) => (
        <span key={tg} className="badge badge-neutral text-xs">
          {tg}
          <button className="ml-1 text-muted hover:text-[var(--status-critical)]" disabled={busy}
            onClick={() => commit(tags.filter((x) => x !== tg))} aria-label={`${tg} sil`}>×</button>
        </span>
      ))}
      <input className="input !w-36 !py-1 text-xs" value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
        placeholder={t("golden.addTag")} disabled={busy} />
      <button className="btn !py-1 text-xs" onClick={addTag} disabled={busy}>+</button>
    </div>
  );
}

/** Temsilcinin kendi çağrısını QA'dan önce puanlaması (Dalga 3c). */
function SelfAssessmentCard({ callId }: { callId: number }) {
  const t = useT();
  const [existing, setExisting] = useState<SelfAssessment | null>(null);
  const [score, setScore] = useState(80);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.getSelfAssessment(callId).then((r) => { setExisting(r); setLoaded(true); }).catch(() => setLoaded(true));
  }, [callId]);

  async function save() {
    setBusy(true);
    try {
      const r = await api.createSelfAssessment({ call_id: callId, self_score: score, note });
      setExisting(r);
    } catch { /* zaten var veya hata */ } finally { setBusy(false); }
  }

  if (!loaded) return null;
  return (
    <div className="card space-y-2 p-4">
      <h2 className="text-sm font-semibold text-ink2">📝 {t("self.title")}</h2>
      {existing ? (
        <p className="text-sm">{t("self.yours")}: <b>{existing.self_score}/100</b>
          {existing.note && <span className="text-muted"> — {existing.note}</span>}</p>
      ) : (
        <>
          <p className="text-xs text-muted">{t("self.hint")}</p>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs">
              <span className="block text-muted">{t("self.score")}</span>
              <input type="number" min={0} max={100} value={score} onChange={(e) => setScore(Number(e.target.value))}
                className="mt-0.5 w-24 rounded-lg border border-hairline bg-surface2 px-2 py-1 text-sm" />
            </label>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="not (opsiyonel)"
              className="flex-1 rounded-lg border border-hairline bg-surface2 px-2 py-1 text-sm" />
            <button className="btn btn-primary !py-1 text-xs" disabled={busy} onClick={save}>{t("self.save")}</button>
          </div>
        </>
      )}
    </div>
  );
}
