"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import PageHeader from "@/components/PageHeader";
import LiveAssist from "@/components/LiveAssist";
import type { AssistSuggestion, VisionStatus, VisionResult } from "@/lib/types";

const SEV_COLOR: Record<string, string> = {
  kritik: "var(--status-critical)", uyari: "var(--status-warn)", bilgi: "var(--series-1)",
};

export default function AssistPage() {
  const t = useT();
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState<AssistSuggestion[] | null>(null);
  const [busy, setBusy] = useState(false);

  // Vision
  const [vstatus, setVstatus] = useState<VisionStatus | null>(null);
  const [vresult, setVresult] = useState<VisionResult | null>(null);
  const [vbusy, setVbusy] = useState(false);
  const [verr, setVerr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.visionStatus().then(setVstatus).catch(() => {}); }, []);

  async function analyze() {
    if (!text.trim()) return;
    setBusy(true);
    try { setSuggestions(await api.assistSuggest(text)); }
    catch (e) { setSuggestions([{ kind: "error", severity: "kritik", text: String(e), detail: "" }]); }
    finally { setBusy(false); }
  }

  async function onImage(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setVbusy(true); setVerr(""); setVresult(null);
    try { setVresult(await api.visionAnalyze(f)); }
    catch (err) { setVerr(err instanceof Error ? err.message : String(err)); }
    finally { setVbusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("assist.pageTitle")} subtitle={t("assist.subtitle")} />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Canlı sufle */}
        <div className="card space-y-3 p-4">
          <div>
            <h2 className="text-sm font-semibold text-ink2">🎧 {t("assist.liveTitle")}</h2>
            <p className="text-xs text-muted">{t("assist.liveHint")}</p>
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5}
            placeholder={t("assist.placeholder")}
            className="w-full rounded-lg border border-hairline bg-surface2 p-2 text-sm" />
          <button className="btn btn-primary" onClick={analyze} disabled={busy || !text.trim()}>
            {busy ? "…" : t("assist.analyze")}
          </button>

          {/* Canlı mikrofon modu (Web Speech API + WebSocket) */}
          <div className="border-t border-hairline pt-3">
            <LiveAssist />
          </div>
          {suggestions && (
            <div className="space-y-2">
              {suggestions.length === 0 ? (
                <p className="rounded-lg bg-[var(--status-ok)]/10 p-2 text-sm text-[var(--status-ok)]">✓ {t("assist.noSuggestions")}</p>
              ) : suggestions.map((s, i) => (
                <div key={i} className="rounded-lg bg-grid/40 p-2 text-sm" style={{ borderLeft: `3px solid ${SEV_COLOR[s.severity] ?? "var(--muted)"}` }}>
                  <div className="flex items-center gap-2 text-[10px] uppercase text-muted">
                    <span style={{ color: SEV_COLOR[s.severity] }}>{t(`sev.${s.severity}`)}</span>
                    <span>{t(`kind.${s.kind}`)}</span>
                    {s.detail && <span className="ml-auto normal-case">{s.detail}</span>}
                  </div>
                  <p className="mt-0.5">{s.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Vision */}
        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-ink2">🖼 {t("assist.visionTitle")}</h2>
          {vstatus && !vstatus.enabled ? (
            <p className="rounded-lg bg-[var(--status-warn)]/10 p-3 text-sm text-ink2">{t("assist.visionDisabled")}</p>
          ) : (
            <>
              <div className="text-xs text-muted">
                {vstatus && (
                  /* B18: "ollama · llama3.2-vision:11b" kullaniciya hicbir sey
                     anlatmiyor. Ne yaptigi yazilir; teknik ayrinti tooltip'te. */
                  <span
                    className="badge badge-neutral"
                    title={`Sağlayıcı: ${vstatus.provider} · Model: ${vstatus.model}`}
                  >
                    {vstatus.provider === "ollama" ? "Yerel yapay zekâ" : "Bulut yapay zekâ"} · görsel analiz
                  </span>
                )}
              </div>
              {/* B18: tarayicinin "Choose File / No file chosen" metni Turkcelestirilemez.
                  Gercek input gizlenir, gorunur tetikleyici bir <label> olur —
                  boylece hem Turkce olur hem klavyeyle erisilebilir kalir. */}
              <label
                htmlFor="kg-vision-file"
                className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] px-4 py-6 text-center transition-colors hover:border-[var(--series-1)] focus-within:ring-2 focus-within:ring-[var(--series-1)]"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files?.[0];
                  if (f && fileRef.current) {
                    const dt = new DataTransfer();
                    dt.items.add(f);
                    fileRef.current.files = dt.files;
                    fileRef.current.dispatchEvent(new Event("change", { bubbles: true }));
                  }
                }}
              >
                <span className="text-sm font-medium text-[var(--ink)]">
                  Görsel seçin veya buraya sürükleyin
                </span>
                <span className="text-[11px] text-muted">
                  PNG, JPEG veya WEBP · en fazla 10 MB
                </span>
                <input
                  id="kg-vision-file"
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={onImage}
                  className="sr-only"
                />
              </label>
              {vbusy && <p className="text-sm text-muted">{t("assist.visionAnalyzing")}</p>}
              {verr && <p className="text-sm text-[var(--status-critical)]">{verr}</p>}
              {vresult && (
                <div className="space-y-2 rounded-lg bg-grid/40 p-3 text-sm">
                  <div className="flex flex-wrap gap-2">
                    <span className="badge badge-neutral">{vresult.belge_turu}</span>
                    <span className={`badge ${vresult.kvkk_riski === "yuksek" ? "badge-critical" : vresult.kvkk_riski === "orta" ? "badge-warn" : "badge-neutral"}`}>
                      KVKK: {t(`risk.${vresult.kvkk_riski}`)}
                    </span>
                  </div>
                  <p>{vresult.aciklama}</p>
                  {vresult.hassas_veri.length > 0 && (
                    <p className="text-xs text-[var(--status-critical)]">⚠ {vresult.hassas_veri.join(", ")}</p>
                  )}
                  {vresult.ozet_not && <p className="text-xs text-muted">{vresult.ozet_not}</p>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
