"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";
import type { Campaign, Criterion, SimulateResult, RubricVersion } from "@/lib/types";

const GROUPS = ["Acilis", "Ihtiyac Analizi", "Cozum", "Kapanis", "Uyum", "Iletisim Kalitesi", "Kriz Yonetimi"];
const CHANNELS = [{ v: "all", l: "•" }, { v: "voice", l: "📞" }, { v: "chat", l: "💬" }];
const NEW: Partial<Criterion> = {
  name: "", description: "", group: "Iletisim Kalitesi", weight: 1.0,
  is_critical: false, critical_threshold: 3, channel_scope: "all", campaign_id: null, is_active: true,
};

export default function RubricPage() {
  const t = useT();
  const [criteria, setCriteria] = useState<Criterion[] | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Criterion>>({});
  const [newItem, setNewItem] = useState<Partial<Criterion>>({ ...NEW });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sim, setSim] = useState<SimulateResult | null>(null);
  const [simBusy, setSimBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [items, camps] = await Promise.all([
        api.listCriteria(),
        api.listCampaigns().catch(() => []),
      ]);
      setCriteria(items);
      setCampaigns(camps);
      setDrafts(Object.fromEntries(items.map((c) => [c.id, { ...c }])));
      setError("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const campName = (id: number | null) => campaigns.find((c) => c.id === id)?.name ?? t("rubric.allCampaigns");

  function setDraft(id: number, patch: Partial<Criterion>) {
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));
  }
  function dirty(c: Criterion) {
    const d = drafts[c.id];
    return d && JSON.stringify(d) !== JSON.stringify(c);
  }

  async function save(id: number) {
    setBusy(true);
    try { await api.updateCriterion(id, drafts[id]); await load(); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function remove(id: number) {
    if (!confirm(t("rubric.deleteConfirm"))) return;
    setBusy(true);
    try { await api.deleteCriterion(id); await load(); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function runSim() {
    setSimBusy(true); setError("");
    try {
      const payload = Object.values(drafts).map((d) => ({
        criterion_id: d.id, weight: d.weight, is_critical: d.is_critical,
        critical_threshold: d.critical_threshold, is_active: d.is_active,
      }));
      setSim(await api.simulateRubric(payload, 30, 200));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSimBusy(false); }
  }
  async function create() {
    if ((newItem.name ?? "").trim().length < 2 || (newItem.description ?? "").trim().length < 2) {
      setError(t("rubric.criterionRequired")); return;
    }
    setBusy(true);
    try { await api.createCriterion(newItem); setNewItem({ ...NEW }); await load(); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  if (!criteria) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">{t("rubric.title")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink2">{t("rubric.desc")}</p>
      </div>

      {error && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>{error}</p>}

      {/* What-if simülasyonu: düzenlenen (kaydedilmemiş) rubriği geçmiş çağrılarda dener */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-ink2">🧪 {t("sim.title")}</h2>
            <p className="mt-0.5 text-xs text-muted">{t("sim.desc")}</p>
          </div>
          <button className="btn btn-primary !py-1 text-xs" disabled={simBusy} onClick={runSim}>
            {simBusy ? t("sim.running") : t("sim.run")}
          </button>
        </div>
        {sim && (
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-3 text-center lg:grid-cols-4">
              <div className="rounded-lg bg-grid/40 p-2">
                <div className="text-lg font-bold tabular-nums">{sim.call_count}</div>
                <div className="text-[10px] text-muted">{t("sim.calls")}</div>
              </div>
              <div className="rounded-lg bg-grid/40 p-2">
                <div className="text-lg font-bold tabular-nums">{sim.avg_before} → {sim.avg_after}</div>
                <div className="text-[10px] text-muted">{t("sim.avg")}</div>
              </div>
              <div className="rounded-lg bg-grid/40 p-2">
                <div className={`text-lg font-bold tabular-nums ${sim.avg_after - sim.avg_before >= 0 ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
                  {sim.avg_after - sim.avg_before > 0 ? "+" : ""}{(sim.avg_after - sim.avg_before).toFixed(1)}
                </div>
                <div className="text-[10px] text-muted">{t("sim.delta")}</div>
              </div>
              <div className="rounded-lg bg-grid/40 p-2">
                <div className="text-lg font-bold tabular-nums">{sim.zeroed_before} → {sim.zeroed_after}</div>
                <div className="text-[10px] text-muted">{t("sim.zeroed")}</div>
              </div>
            </div>
            {sim.biggest_changes.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-semibold text-ink2">{t("sim.biggest")}</p>
                {sim.biggest_changes.map((ch) => (
                  <div key={ch.id} className="flex items-center gap-2 text-xs">
                    <Link href={`/calls/${ch.id}`} className="flex-1 truncate text-series hover:underline">#{ch.id} {ch.filename}</Link>
                    <span className="tabular-nums text-muted">{ch.before} → {ch.after}</span>
                    <span className={`font-semibold tabular-nums ${ch.delta >= 0 ? "text-[var(--status-ok)]" : "text-[var(--status-critical)]"}`}>
                      {ch.delta > 0 ? "+" : ""}{ch.delta}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <RubricVersions reload={load} t={t} />

      <div className="space-y-3">
        {criteria.map((c) => {
          const d = drafts[c.id] ?? c;
          return (
            <div key={c.id} className={`card p-4 ${d.is_active ? "" : "opacity-60"} ${d.is_critical ? "border-l-4" : ""}`}
              style={d.is_critical ? { borderLeftColor: "var(--status-critical)" } : undefined}>
              <div className="flex flex-wrap items-center gap-2">
                <input className="input min-w-48 flex-1 font-semibold" value={d.name}
                  onChange={(e) => setDraft(c.id, { name: e.target.value })} />
                <select className="input" value={d.group} onChange={(e) => setDraft(c.id, { group: e.target.value })}>
                  {GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
                {/* B20: "Agirlik 1.5" tek basina hicbir sey anlatmiyordu.
                    Kontrolun puana ETKISI yaninda yazili olmali. */}
                <label className="flex items-center gap-1 text-xs text-ink2"
                  title="Bu kriterin toplam puandaki payı. 2.0, ağırlığı 1.0 olan bir kriterin iki katı etki eder.">
                  {t("common.weight")}
                  <input type="number" step={0.5} min={0.1} max={10} className="input w-16 tabular-nums" value={d.weight}
                    onChange={(e) => setDraft(c.id, { weight: Number(e.target.value) })} />
                  <span className="text-[10px] text-muted">toplam puandaki payı</span>
                </label>
                <select className="input text-xs" value={d.channel_scope} onChange={(e) => setDraft(c.id, { channel_scope: e.target.value })}>
                  {CHANNELS.map((ch) => <option key={ch.v} value={ch.v}>{ch.l}</option>)}
                </select>
                <select className="input text-xs" value={d.campaign_id ?? ""} onChange={(e) => setDraft(c.id, { campaign_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">{t("rubric.allCampaigns")}</option>
                  {campaigns.map((cm) => <option key={cm.id} value={cm.id}>{cm.name}</option>)}
                </select>
              </div>
              <textarea className="input mt-2 w-full text-sm" rows={2} value={d.description}
                onChange={(e) => setDraft(c.id, { description: e.target.value })} />
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-1.5 text-sm text-ink2">
                  <input type="checkbox" checked={d.is_critical} onChange={(e) => setDraft(c.id, { is_critical: e.target.checked })} />
                  {t("rubric.critical")}
                </label>
                {d.is_critical && (
                  <label className="flex items-center gap-1 text-xs text-ink2">
                    {t("rubric.threshold")}
                    <input type="number" min={0} max={10} className="input w-16 tabular-nums" value={d.critical_threshold}
                      onChange={(e) => setDraft(c.id, { critical_threshold: Number(e.target.value) })} />
                  </label>
                )}
                {/* Kritik kriterin ne yaptigi ACIKCA yazili — tooltip'e gizlenmez */}
                {d.is_critical && (
                  <p className="basis-full text-[11px] leading-relaxed text-[var(--status-critical)]">
                    Bu kriter <strong>{d.critical_threshold}</strong> puanın altında kalırsa çağrının
                    toplam puanı <strong>0</strong> olur — diğer kriterler ne alırsa alsın.
                  </p>
                )}
                <label className="flex items-center gap-1.5 text-sm text-ink2">
                  <input type="checkbox" checked={d.is_active} onChange={(e) => setDraft(c.id, { is_active: e.target.checked })} />
                  {t("common.active")}
                </label>
                <span className="text-xs text-muted">{campName(d.campaign_id)}</span>
                <div className="ml-auto flex gap-2">
                  <button className="btn btn-primary" disabled={busy || !dirty(c)} onClick={() => save(c.id)}>{t("common.save")}</button>
                  <button className="btn" disabled={busy} onClick={() => remove(c.id)}>{t("common.delete")}</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card p-4">
        <h2 className="text-sm font-semibold text-ink2">{t("rubric.newCriterion")}</h2>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input className="input min-w-48 flex-1" placeholder={t("rubric.name")} value={newItem.name}
            onChange={(e) => setNewItem((n) => ({ ...n, name: e.target.value }))} />
          <select className="input" value={newItem.group} onChange={(e) => setNewItem((n) => ({ ...n, group: e.target.value }))}>
            {GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <label className="flex items-center gap-1 text-xs text-ink2">Ağırlık
            <input type="number" step={0.5} min={0.1} max={10} className="input w-16" value={newItem.weight}
              onChange={(e) => setNewItem((n) => ({ ...n, weight: Number(e.target.value) }))} />
          </label>
          <label className="flex items-center gap-1.5 text-sm text-ink2">
            <input type="checkbox" checked={newItem.is_critical} onChange={(e) => setNewItem((n) => ({ ...n, is_critical: e.target.checked }))} />
            Kritik
          </label>
          <button className="btn btn-primary" disabled={busy} onClick={create}>＋ {t("common.add")}</button>
        </div>
        <textarea className="input mt-2 w-full text-sm" rows={2} placeholder={t("rubric.description")}
          value={newItem.description} onChange={(e) => setNewItem((n) => ({ ...n, description: e.target.value }))} />
      </div>
    </div>
  );
}

/** Rubrik versiyonlama: mevcut hali kaydet, geçmişi gör, geri yükle (governance). */
function RubricVersions({ reload, t }: { reload: () => void; t: (k: string) => string }) {
  const [versions, setVersions] = useState<RubricVersion[] | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { api.listRubricVersions().then(setVersions).catch(() => setVersions([])); }, []);
  useEffect(() => { load(); }, [load]);

  async function save() {
    const note = prompt(t("rver.notePrompt"))?.trim() ?? "";
    setBusy(true);
    try { await api.saveRubricVersion(note); load(); } catch (e) { alert(String(e)); } finally { setBusy(false); }
  }
  async function restore(id: number) {
    if (!confirm(t("rver.restoreConfirm"))) return;
    setBusy(true);
    try { await api.restoreRubricVersion(id); reload(); load(); } catch (e) { alert(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink2">🗂 {t("rver.title")}</h2>
          <p className="mt-0.5 text-xs text-muted">{t("rver.desc")}</p>
        </div>
        <button className="btn btn-primary !py-1 text-xs" disabled={busy} onClick={save}>💾 {t("rver.save")}</button>
      </div>
      {versions && versions.length > 0 && (
        <div className="mt-3 max-h-56 space-y-1 overflow-y-auto">
          {versions.map((v) => (
            <div key={v.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-grid/40">
              <span className="text-muted">{fmtDate(v.created_at)}</span>
              <span className="flex-1 truncate">{v.note || t("rver.noNote")} · {v.criteria_count} {t("rver.criteria")}</span>
              <button className="btn !py-0.5 text-xs" disabled={busy} onClick={() => restore(v.id)}>↩ {t("rver.restore")}</button>
            </div>
          ))}
        </div>
      )}
      {versions && versions.length === 0 && <p className="mt-2 text-xs text-muted">{t("rver.empty")}</p>}
    </div>
  );
}
