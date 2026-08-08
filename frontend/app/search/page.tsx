"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useState } from "react";
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

  async function run(query = q) {
    if (query.trim().length < 2) { setError(t("search.placeholder")); return; }
    setBusy(true); setError("");
    try {
      const params: Record<string, string> = { q: query.trim() };
      if (speaker) params.speaker = speaker;
      if (channel) params.channel = channel;
      setRes(await api.searchTranscripts(params));
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
        <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      {res && (
        <>
          <p className="text-sm text-ink2">
            <b>&ldquo;{res.query}&rdquo;</b> — {res.total_calls} {t("search.results")} {res.total_hits} {t("search.matches")}
          </p>

          {res.items.length === 0 ? (
            <p className="card p-8 text-center text-sm text-muted">
              {t("search.noResults")}
            </p>
          ) : (
            <div className="space-y-2">
              {res.items.map((h, i) => (
                <Link
                  key={i}
                  href={`/calls/${h.call_id}?t=${h.ts_sec}`}
                  className="card block p-3 transition hover:border-series"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-semibold text-series">{h.filename}</span>
                    <ChannelChip channel={h.channel} />
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
