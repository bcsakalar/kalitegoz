"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AIConfig, AICatalog, OllamaModel, AITestResult, PullStatus, AiUsageSummary } from "@/lib/types";
import { useT } from "@/components/I18nProvider";

const PROVIDER_META: Record<string, { icon: string; label: string; descKey: string; needsKey: boolean }> = {
  ollama: { icon: "🏠", label: "Ollama", descKey: "ai.p.ollama", needsKey: false },
  gemini: { icon: "✨", label: "Google Gemini", descKey: "ai.p.gemini", needsKey: true },
  openai: { icon: "🤖", label: "OpenAI", descKey: "ai.p.openai", needsKey: true },
  openrouter: { icon: "🔀", label: "OpenRouter", descKey: "ai.p.openrouter", needsKey: true },
};

export default function AITab() {
  const t = useT();
  const [cfg, setCfg] = useState<AIConfig | null>(null);
  const [cat, setCat] = useState<AICatalog | null>(null);
  const [installed, setInstalled] = useState<OllamaModel[]>([]);
  const [ollamaErr, setOllamaErr] = useState("");
  // duzenlenebilir yerel durum
  const [llmP, setLlmP] = useState("ollama");
  const [visP, setVisP] = useState("ollama");
  const [embP, setEmbP] = useState("ollama");
  const [llmM, setLlmM] = useState<Record<string, string>>({});
  const [visM, setVisM] = useState<Record<string, string>>({});
  const [embM, setEmbM] = useState<Record<string, string>>({});
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [pull, setPull] = useState<Record<string, PullStatus>>({});
  const [pullModel, setPullModel] = useState("");
  const [test, setTest] = useState<AITestResult | null>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const applyCfg = useCallback((c: AIConfig) => {
    setCfg(c);
    setLlmP(c.llm_provider); setVisP(c.vision_provider); setEmbP(c.embed_provider);
    setLlmM(c.llm_models || {}); setVisM(c.vision_models || {}); setEmbM(c.embed_models || {});
  }, []);

  const loadOllama = useCallback(() => {
    api.ollamaModels().then((r) => { setInstalled(r.models); setOllamaErr(r.error ?? ""); }).catch(() => {});
  }, []);

  useEffect(() => {
    api.getAiConfig().then(applyCfg).catch(() => {});
    api.aiCatalog().then(setCat).catch(() => {});
    loadOllama();
  }, [applyCfg, loadOllama]);

  // Pull ilerlemesini yokla (aktif indirme varken)
  useEffect(() => {
    const active = Object.values(pull).some((p) => !p.done);
    if (active && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const st = await api.ollamaPullStatus().catch(() => ({}));
        setPull(st);
        if (Object.values(st).length && Object.values(st).every((p) => p.done)) {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          loadOllama();
        }
      }, 1500);
    }
    return () => { if (pollRef.current && !active) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [pull, loadOllama]);

  function suggestions(kind: "llm" | "vision" | "embed", provider: string): string[] {
    if (!cat) return [];
    if (provider === "ollama") return installed.map((m) => m.name);
    const map: Record<string, string[]> = {
      "gemini:llm": cat.gemini, "gemini:vision": cat.gemini_vision, "gemini:embed": cat.gemini_embed,
      "openai:llm": cat.openai, "openai:vision": cat.openai_vision, "openai:embed": cat.openai_embed,
      "openrouter:llm": cat.openrouter, "openrouter:vision": cat.openrouter_vision, "openrouter:embed": [],
    };
    return map[`${provider}:${kind}`] || [];
  }

  async function startPull(model: string) {
    const m = model.trim(); if (!m) return;
    setPull((p) => ({ ...p, [m]: { status: "baslatiliyor", percent: 0, done: false, error: null } }));
    await api.ollamaPull(m).catch(() => {});
    setPullModel("");
    // yoklama efekti devreye girer
    const st = await api.ollamaPullStatus().catch(() => ({})); setPull(st);
  }

  async function save() {
    setBusy("save"); setMsg("");
    try {
      const enteredKeys: Record<string, string> = {};
      Object.entries(keys).forEach(([p, k]) => { if (k && k.trim()) enteredKeys[p] = k.trim(); });
      const updated = await api.putAiConfig({
        llm_provider: llmP, vision_provider: visP, embed_provider: embP,
        llm_models: llmM, vision_models: visM, embed_models: embM,
        keys: enteredKeys,
      });
      applyCfg(updated); setKeys({}); setMsg(t("ai.saved"));
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(""); }
  }

  async function runTest() {
    setBusy("test"); setTest(null);
    try { setTest(await api.aiTest(llmP)); }
    catch (e) { setTest({ ok: false, provider: llmP, model: "", error: e instanceof Error ? e.message : String(e) }); }
    finally { setBusy(""); }
  }

  if (!cfg) return <p className="text-sm text-muted">…</p>;
  const providers = cfg.providers;

  return (
    <div className="space-y-5">
      {msg && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-good)" }}>{msg}</p>}
      <p className="text-sm text-ink2">{t("ai.intro")}</p>

      {/* ---- Puanlama LLM ---- */}
      <div className="card space-y-4 p-4">
        <h2 className="text-sm font-semibold text-ink2">🧠 {t("ai.llmTitle")}</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {providers.map((p) => (
            <button key={p} onClick={() => setLlmP(p)}
              className={`card flex items-start gap-2 p-3 text-left ${llmP === p ? "border-series ring-1 ring-series" : ""}`}>
              <span className="text-xl" aria-hidden>{PROVIDER_META[p]?.icon}</span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{PROVIDER_META[p]?.label}
                  {p === "ollama" && <span className="ml-1 text-[10px] text-muted">({t("ai.default")})</span>}</span>
                <span className="block text-xs text-muted">{t(PROVIDER_META[p]?.descKey ?? "")}</span>
              </span>
            </button>
          ))}
        </div>
        <ProviderConfig kind="llm" provider={llmP} models={llmM} setModels={setLlmM}
          keys={keys} setKeys={setKeys} keysSet={cfg.keys_set} sugg={suggestions("llm", llmP)} t={t} />
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn" disabled={busy === "test"} onClick={runTest}>{busy === "test" ? t("ai.testing") : t("ai.test")}</button>
          {test && (
            <span className={`badge ${test.ok ? "badge-good" : "badge-critical"}`}>
              <span className="dot" />{test.ok ? t("ai.testOk") : t("ai.testFail")}: {test.ok ? test.model : (test.error ?? "")}
            </span>
          )}
        </div>
      </div>

      {/* ---- Vision ---- */}
      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">🖼 {t("ai.visionTitle")}</h2>
        <ProviderRow providers={cfg.vision_providers} value={visP} onChange={setVisP} t={t} />
        <ProviderConfig kind="vision" provider={visP} models={visM} setModels={setVisM}
          keys={keys} setKeys={setKeys} keysSet={cfg.keys_set} sugg={suggestions("vision", visP)} t={t} compact />
      </div>

      {/* ---- Embedding / RAG ---- */}
      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">📚 {t("ai.embedTitle")}</h2>
        <p className="text-xs" style={{ color: "var(--status-warning)" }}>⚠ {t("ai.embedWarn")}</p>
        <ProviderRow providers={cfg.embed_providers} value={embP} onChange={setEmbP} t={t} />
        <ProviderConfig kind="embed" provider={embP} models={embM} setModels={setEmbM}
          keys={keys} setKeys={setKeys} keysSet={cfg.keys_set} sugg={suggestions("embed", embP)} t={t} compact />
      </div>

      <div className="flex justify-end">
        <button className="btn btn-primary" disabled={busy === "save"} onClick={save}>{busy === "save" ? t("ai.saving") : t("ai.save")}</button>
      </div>

      {/* ---- Ollama model yonetimi ---- */}
      <div className="card space-y-4 p-4">
        <h2 className="text-sm font-semibold text-ink2">🏠 {t("ai.ollamaTitle")}</h2>
        {ollamaErr && <p className="text-sm" style={{ color: "var(--status-critical)" }}>{ollamaErr}</p>}
        <div>
          <div className="mb-1 text-xs text-ink2">{t("ai.installed")}</div>
          <div className="flex flex-wrap gap-2">
            {installed.map((m) => <span key={m.name} className="badge badge-neutral"><span className="dot" />{m.name} · {m.size}</span>)}
            {installed.length === 0 && !ollamaErr && <span className="text-xs text-muted">—</span>}
          </div>
        </div>
        {/* Ozel model indir */}
        <form onSubmit={(e) => { e.preventDefault(); startPull(pullModel); }} className="flex gap-2">
          <input className="input flex-1" placeholder="qwen2.5:14b" value={pullModel} onChange={(e) => setPullModel(e.target.value)} />
          <button className="btn btn-primary">{t("ai.pull")}</button>
        </form>
        {/* Onerilen modeller */}
        <div>
          <div className="mb-1 text-xs text-ink2">{t("ai.recommended")}</div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {cat?.ollama_recommended.map((r) => {
              const isInstalled = installed.some((m) => m.name === r.name);
              const p = pull[r.name];
              return (
                <div key={r.name} className="card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{r.name}</span>
                    <span className="text-[10px] text-muted">{r.size}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted">{r.desc}</p>
                  {isInstalled ? (
                    <span className="mt-2 inline-block text-xs" style={{ color: "var(--status-good)" }}>✓ {t("ai.installedTag")}</span>
                  ) : p && !p.done ? (
                    <div className="mt-2">
                      <div className="h-1.5 overflow-hidden bg-grid">
                        <div className="h-full bg-series" style={{ width: `${p.percent}%` }} />
                      </div>
                      <span className="text-[10px] text-muted">{p.status} {p.percent > 0 ? `%${p.percent}` : ""}</span>
                    </div>
                  ) : p && p.error ? (
                    <span className="mt-2 inline-block text-xs" style={{ color: "var(--status-critical)" }}>{p.error}</span>
                  ) : (
                    <button className="btn mt-2 !py-1 text-xs" onClick={() => startPull(r.name)}>⬇ {t("ai.pull")}</button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <UsagePanel t={t} />
    </div>
  );
}

/** AI kullanim/maliyet paneli: token, tahmini maliyet, amaca/saglayiciya gore kirilim. */
function UsagePanel({ t }: { t: (k: string) => string }) {
  const [u, setU] = useState<AiUsageSummary | null>(null);
  useEffect(() => { api.aiUsage(30).then(setU).catch(() => {}); }, []);
  if (!u) return null;
  return (
    <div className="card space-y-3 p-4">
      <h2 className="text-sm font-semibold text-ink2">📊 {t("aiusage.title")}</h2>
      <p className="text-xs text-muted">{t("aiusage.desc")}</p>
      <div className="grid grid-cols-2 gap-3 text-center lg:grid-cols-4">
        <div className="bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">{u.total_calls}</div><div className="text-[10px] text-muted">{t("aiusage.calls")}</div></div>
        <div className="bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">{u.total_tokens.toLocaleString()}</div><div className="text-[10px] text-muted">token</div></div>
        <div className="bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">${u.total_cost_usd.toFixed(2)}</div><div className="text-[10px] text-muted">{t("aiusage.cost")}</div></div>
        <div className="bg-grid/40 p-2"><div className="text-lg font-bold tabular-nums">%{u.ok_rate}</div><div className="text-[10px] text-muted">{t("aiusage.okRate")}</div></div>
      </div>
      {u.by_kind.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-muted">
              <th className="py-1">{t("aiusage.kind")}</th><th>{t("aiusage.provider")}</th>
              <th className="text-right">{t("aiusage.calls")}</th><th className="text-right">token</th>
              <th className="text-right">{t("aiusage.cost")}</th><th className="text-right">ms</th>
            </tr></thead>
            <tbody>
              {u.by_kind.map((r, i) => (
                <tr key={i} className="border-t border-hairline">
                  <td className="py-1 font-medium">{t(`aiusage.k.${r.kind}`) || r.kind}</td>
                  <td>{r.provider}</td>
                  <td className="text-right tabular-nums">{r.calls}</td>
                  <td className="text-right tabular-nums">{(r.prompt_tokens + r.completion_tokens).toLocaleString()}</td>
                  <td className="text-right tabular-nums">${r.cost_usd.toFixed(3)}</td>
                  <td className="text-right tabular-nums">{r.avg_latency_ms}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[10px] text-muted">{t("aiusage.note")}</p>
    </div>
  );
}

/** Saglayici model + (bulut ise) anahtar giris alani. */
function ProviderConfig({ kind, provider, models, setModels, keys, setKeys, keysSet, sugg, t, compact }: {
  kind: "llm" | "vision" | "embed"; provider: string;
  models: Record<string, string>; setModels: (m: Record<string, string>) => void;
  keys: Record<string, string>; setKeys: (k: Record<string, string>) => void;
  keysSet: Record<string, boolean>; sugg: string[]; t: (k: string) => string; compact?: boolean;
}) {
  const needsKey = PROVIDER_META[provider]?.needsKey;
  const listId = `sugg-${kind}-${provider}`;
  return (
    <div className={`grid gap-3 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2"}`}>
      {needsKey && (
        <label className="block">
          <span className="mb-1 block text-xs text-ink2">{PROVIDER_META[provider]?.label} {t("ai.apiKey")}
            {keysSet[provider] && <span className="ml-1 text-[10px]" style={{ color: "var(--status-good)" }}>✓ {t("ai.keySaved")}</span>}</span>
          <input className="input w-full font-mono text-xs" type="password" autoComplete="off"
            placeholder={keysSet[provider] ? t("ai.keyChange") : t("ai.keyEnter")}
            value={keys[provider] ?? ""} onChange={(e) => setKeys({ ...keys, [provider]: e.target.value })} />
        </label>
      )}
      <label className="block">
        <span className="mb-1 block text-xs text-ink2">{t("ai.model")}</span>
        <input className="input w-full" list={listId} placeholder={t("ai.modelPlaceholder")}
          value={models[provider] ?? ""} onChange={(e) => setModels({ ...models, [provider]: e.target.value })} />
        <datalist id={listId}>{sugg.map((s) => <option key={s} value={s} />)}</datalist>
      </label>
    </div>
  );
}

function ProviderRow({ providers, value, onChange, t }: {
  providers: string[]; value: string; onChange: (v: string) => void; t: (k: string) => string;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {providers.map((p) => (
        <button key={p} onClick={() => onChange(p)}
          className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium ${value === p ? "bg-series text-white" : "bg-surface-2 text-ink2"}`}>
          <span aria-hidden>{PROVIDER_META[p]?.icon}</span> {PROVIDER_META[p]?.label}
        </button>
      ))}
    </div>
  );
}
