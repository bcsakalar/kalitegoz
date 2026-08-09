"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingRegion } from "@/components/EmptyState";
import { useAuth } from "@/components/AuthProvider";
import { CategoryChip, ChannelChip, ScoreBadge } from "@/components/Badges";
import { api, CHANNEL_LABELS, fmtDate, fmtTs } from "@/lib/api";
import type { TranscriptSearchResult } from "@/lib/types";

// Kalite ekibinin en sık aradıkları — tek tıkla çalışsın
const PRESETS = [
  { q: "avukat", label: "avukat (hukuki tehdit)" },
  { q: "tüketici hakem", label: "tüketici hakem heyeti" },
  { q: "iptal ediyorum", label: "iptal ediyorum" },
  { q: "garanti ederim", label: "garanti ederim (yasak vaat)" },
  { q: "şikayet ed", label: "şikayet edeceğim" },
  { q: "KVKK", label: "KVKK anonsu" },
];

export default function SearchPage() {
  const t = useT();
  const { me } = useAuth();
  const [q, setQ] = useState("");
  const [speaker, setSpeaker] = useState("");
  const [channel, setChannel] = useState("");
  const [res, setRes] = useState<TranscriptSearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // B23: son aramalar. Kalite ekibi ayni ifadeleri tekrar tekrar arar;
  // her seferinde yeniden yazdirmak gereksiz surtunmedir.
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("kg_recent_searches");
      if (raw) setRecent(JSON.parse(raw) as string[]);
    } catch { /* bozuk kayit gorulmezden gelinir */ }
  }, []);

  const remember = useCallback((query: string) => {
    setRecent((prev) => {
      const next = [query, ...prev.filter((x) => x !== query)].slice(0, 6);
      try { localStorage.setItem("kg_recent_searches", JSON.stringify(next)); } catch { /* kota dolu */ }
      return next;
    });
  }, []);

  async function run(query = q) {
    if (query.trim().length < 2) { setError(t("search.placeholder")); return; }
    setBusy(true); setError("");
    try {
      const params: Record<string, string> = { q: query.trim() };
      if (speaker) params.speaker = speaker;
      if (channel) params.channel = channel;
      setRes(await api.searchTranscripts(params));
      remember(query.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  function highlight(text: string, term: string) {
    const i = text.toLocaleLowerCase("tr").indexOf(term.toLocaleLowerCase("tr"));
    if (i === -1) return <>{text}</>;
    return (
      <>
        {text.slice(0, i)}
        <mark className="rounded bg-[rgba(250,178,25,0.35)] px-0.5 text-ink">
          {text.slice(i, i + term.length)}
        </mark>
        {text.slice(i + term.length)}
      </>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">{t("search.title")}</h1>
        <p className="mt-1 text-sm text-ink2">
          {t("search.desc")}
          {me?.role === "agent" && ` ${t("search.agentScope")}`}
        </p>
      </div>

      <div className="card space-y-3 p-3">
        <div className="flex flex-wrap gap-2">
          <input
            className="input min-w-64 flex-1"
            placeholder={t("search.placeholder")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
          <select className="input" value={speaker} onChange={(e) => setSpeaker(e.target.value)}>
            <option value="">{t("search.everyone")}</option>
            <option value="temsilci">{t("search.agentSaid")}</option>
            <option value="musteri">{t("search.customerSaid")}</option>
          </select>
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="">{t("common.all")}</option>
            <option value="voice">{CHANNEL_LABELS.voice}</option>
            <option value="chat">{CHANNEL_LABELS.chat}</option>
          </select>
          <button className="btn btn-primary" disabled={busy} onClick={() => run()}>
            {busy ? `${t("common.search")}…` : `🔍 ${t("common.search")}`}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">{t("search.presets")}</span>
          {PRESETS.map((p) => (
            <button key={p.q} className="btn !py-0.5 text-xs"
              onClick={() => { setQ(p.q); run(p.q); }}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="card">
          <ErrorState
            what="Arama yapılamadı."
            next="En az 2 karakter yazın ve tekrar deneyin. Sorun sürerse sayfayı yenileyin."
            onRetry={() => run()}
          />
        </div>
      )}

      {/* Yukleniyor — iskelet, spinner degil */}
      {busy && !res && <div className="card p-3"><LoadingRegion label="Aranıyor…" rows={4} /></div>}

      {/* BOS DURUM (B23): arama yapilmadan once ekran bombos kalmaz */}
      {!res && !busy && !error && (
        <div className="card">
          <EmptyState
            title="Transkriptlerde arama yapın."
            reason="Bir ifade yazın; sistem tüm çağrıların transkriptlerinde arar ve eşleşen cümleyi çevresiyle birlikte gösterir. Sonuca tıklayınca çağrı o saniyeden açılır."
            action={
              recent.length > 0 ? (
                <div className="text-left">
                  <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Son aramalarınız
                  </p>
                  <div className="flex flex-wrap justify-center gap-1.5">
                    {recent.map((r) => (
                      <button key={r} type="button" className="btn !py-0.5 text-xs"
                        onClick={() => { setQ(r); run(r); }}>
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
              ) : undefined
            }
          />
        </div>
      )}

      {res && (
        <>
          <p className="text-sm text-ink2">
            <b>&ldquo;{res.query}&rdquo;</b> — {res.total_calls} {t("search.results")} {res.total_hits} {t("search.matches")}
          </p>

          {res.items.length === 0 ? (
            <div className="card">
              <EmptyState
                title={`“${res.query}” için eşleşme bulunamadı.`}
                reason="Bu ifade hiçbir çağrı transkriptinde geçmiyor. Daha kısa bir kök deneyin (örn. 'iptal ed' yerine 'iptal') veya konuşmacı/kanal filtresini kaldırın."
              />
            </div>
          ) : (
            <div className="space-y-2">
              {res.items.map((h, i) => (
                <Link
                  key={i}
                  href={`/calls/${h.call_id}?t=${h.ts_sec}`}
                  className="card block p-3 transition hover:border-series"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-mono font-semibold tabular-nums text-series">
                      #{String(h.call_id).padStart(4, "0")}
                    </span>
                    <ChannelChip channel={h.channel} compact />
                    <span className="text-ink2">{h.agent_name ?? "—"}</span>
                    <CategoryChip category={h.category} />
                    <ScoreBadge score={h.total_score} />
                    <span className="text-muted">{fmtDate(h.created_at)}</span>
                    {h.match_count > 1 && (
                      <span className="badge badge-info">{h.match_count} eşleşme</span>
                    )}
                  </div>
                  <div className="mt-2 flex items-start gap-2 text-sm">
                    <span className="btn shrink-0 !px-2 !py-0.5 text-xs tabular-nums">
                      ▶ {fmtTs(h.ts_sec)}
                    </span>
                    <span className={`shrink-0 text-xs font-semibold ${h.speaker === "temsilci" ? "text-series" : "text-ink2"}`}>
                      {h.speaker === "temsilci" ? t("role.agent") : t("common.customer")}:
                    </span>
                    <span className="text-ink">{highlight(h.text, res.query)}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
