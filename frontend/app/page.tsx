"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import CallTable from "@/components/CallTable";
import DistBars from "@/components/DistBars";
import PageHeader from "@/components/PageHeader";
import StatTile from "@/components/StatTile";
import TrendChart from "@/components/TrendChart";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";
import {
  api, authedDownload, CATEGORY_LABEL_KEYS, CHANNEL_LABEL_KEYS, exportCsvUrl, STATUS_LABEL_KEYS,
} from "@/lib/api";
import type { AgentSummary, CallList, Overview, OnboardingStatus } from "@/lib/types";

const EMPTY = {
  date_from: "", date_to: "", agent_id: "", category: "", channel: "",
  status: "", min_score: "", max_score: "", only_crisis: "", only_zeroed: "",
  only_golden: "", tag: "",
};
type Filters = typeof EMPTY;

export default function DashboardPage() {
  const { me } = useAuth();
  const t = useT();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [calls, setCalls] = useState<CallList | null>(null);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  // "kolon:yon" — varsayilan en yeni. duration:desc = en uzun gorusmeler uste.
  const [sortBy, setSortBy] = useState("created_at:desc");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const isStaff = me && me.role !== "agent";
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkTag, setBulkTag] = useState("");

  const load = useCallback(async () => {
    try {
      const params: Record<string, string> = { page: String(page), page_size: "20" };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const [col, ord] = sortBy.split(":");
      params.sort = col;
      params.order = ord;
      const [ov, cl, ag] = await Promise.all([
        api.overview(), api.listCalls(params), api.listAgents(),
      ]);
      setOverview(ov); setCalls(cl); setAgents(ag); setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [filters, page, sortBy]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!overview || overview.processing_calls === 0) return;
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [overview, load]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try { await api.uploadCall(file, ""); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  const set = (k: keyof typeof EMPTY) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setPage(1);
      setFilters((f) => ({ ...f, [k]: e.target.value }));
    };

  const totalPages = calls ? Math.max(1, Math.ceil(calls.total / calls.page_size)) : 1;
  const activeCount = Object.values(filters).filter(Boolean).length;

  // Sayfa/filtre/sıralama değişince seçim temizlenir (görünmeyen id kalmasın)
  useEffect(() => { setSelected(new Set()); }, [page, filters, sortBy]);

  function toggleSel(id: number) {
    setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }
  function toggleAll() {
    setSelected((s) => {
      if (!calls) return s;
      const allSel = calls.items.every((c) => s.has(c.id));
      return allSel ? new Set() : new Set(calls.items.map((c) => c.id));
    });
  }
  async function doBulk(action: string) {
    if (selected.size === 0) return;
    if (action === "delete" && !confirm(t("bulk.deleteConfirm"))) return;
    let tag: string | undefined;
    if (action === "tag_add" || action === "tag_remove") {
      tag = (bulkTag.trim() || prompt(t("golden.addTag")) || "").trim();
      if (!tag) return;
    }
    try { await api.bulkCallAction(Array.from(selected), action, tag); setSelected(new Set()); setBulkTag(""); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div className="space-y-5">
      <PageHeader title={t("calls.title")}>
        {isStaff && (
          <>
            <button
              className="btn"
              onClick={() => authedDownload(
                exportCsvUrl(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))),
                "kalitegoz_cagrilar.csv",
              )}
            >
              ⬇ CSV
            </button>
            <input ref={fileRef} type="file" accept=".wav,.mp3,.m4a,.ogg,.flac" className="hidden" onChange={onUpload} />
            <button className="btn btn-primary" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? t("calls.uploading") : t("calls.upload")}
            </button>
          </>
        )}
      </PageHeader>

      {isStaff && <GettingStarted />}

      {error && (
        <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>
          {t("common.error")}: {error}
        </p>
      )}

      {overview && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <StatTile label={t("stat.totalCalls")} value={String(overview.total_calls)} />
          <StatTile label={t("stat.avgScore")} value={overview.avg_score != null ? overview.avg_score.toFixed(1) : "—"} hint="0–100" />
          <StatTile label={t("stat.csat")} value={overview.avg_csat != null ? `${overview.avg_csat}/5` : "—"} />
          <StatTile label={t("stat.crisis")} value={String(overview.crisis_calls)} />
          <StatTile label={t("stat.zeroed")} value={String(overview.zeroed_calls)} />
        </div>
      )}

      {overview && (overview.trend.length > 1 || Object.keys(overview.category_dist).length > 0) && (
        <div className="grid gap-5 lg:grid-cols-2">
          <TrendChart data={overview.trend} title={t("chart.dailyAvg")} />
          <DistBars
            title={t("chart.categoryDist")}
            items={Object.entries(overview.category_dist).sort((a, b) => b[1] - a[1])
              .map(([k, v]) => ({ label: t(CATEGORY_LABEL_KEYS[k] ?? "") || k, value: v }))}
          />
        </div>
      )}

      {/* Filtreler — sayfa kalabalik olmasin diye varsayilan KAPALI; acinca genisler.
          Aktif filtre sayisi ozette gorunur (herkes ne uyguladigini bilsin). */}
      <details className="card">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
          <span aria-hidden>🔍</span> {t("calls.filters")}
          {activeCount > 0 && (
            <span className="bg-series/10 px-2 py-0.5 text-xs font-semibold text-series">{activeCount}</span>
          )}
          <span className="ml-auto text-xs text-muted">{t("calls.filtersHint")}</span>
        </summary>
        <div className="flex flex-wrap items-end gap-3 border-t border-hairline p-3">
          <label className="text-xs text-ink2">{t("calls.filter.start")}
            <input type="date" className="input mt-1 block" value={filters.date_from} onChange={set("date_from")} />
          </label>
          <label className="text-xs text-ink2">{t("calls.filter.end")}
            <input type="date" className="input mt-1 block" value={filters.date_to} onChange={set("date_to")} />
          </label>
          <label className="text-xs text-ink2">{t("calls.channel")}
            <select className="input mt-1 block" value={filters.channel} onChange={set("channel")}>
              <option value="">{t("common.all")}</option>
              {Object.entries(CHANNEL_LABEL_KEYS).map(([k, v]) => <option key={k} value={k}>{t(v) || k}</option>)}
            </select>
          </label>
          {isStaff && (
            <label className="text-xs text-ink2">{t("calls.agent")}
              <select className="input mt-1 block" value={filters.agent_id} onChange={set("agent_id")}>
                <option value="">{t("common.all")}</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </label>
          )}
          <label className="text-xs text-ink2">{t("calls.category")}
            <select className="input mt-1 block" value={filters.category} onChange={set("category")}>
              <option value="">{t("common.all")}</option>
              {Object.entries(CATEGORY_LABEL_KEYS).map(([k, v]) => <option key={k} value={k}>{t(v) || k}</option>)}
            </select>
          </label>
          <label className="text-xs text-ink2">{t("calls.status")}
            <select className="input mt-1 block" value={filters.status} onChange={set("status")}>
              <option value="">{t("common.all")}</option>
              {Object.entries(STATUS_LABEL_KEYS).map(([k, v]) => <option key={k} value={k}>{t(v) || k}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink2">
            <input type="checkbox" checked={filters.only_crisis === "true"}
              onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, only_crisis: e.target.checked ? "true" : "" })); }} />
            {t("calls.filter.onlyCrisis")}
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink2">
            <input type="checkbox" checked={filters.only_zeroed === "true"}
              onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, only_zeroed: e.target.checked ? "true" : "" })); }} />
            {t("calls.filter.onlyZeroed")}
          </label>
          <label className="flex items-center gap-1.5 text-xs text-ink2">
            <input type="checkbox" checked={filters.only_golden === "true"}
              onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, only_golden: e.target.checked ? "true" : "" })); }} />
            ⭐ {t("golden.filter")}
          </label>
          <label className="text-xs text-ink2">{t("golden.tagLabel")}
            <input className="input mt-1 block" value={filters.tag} onChange={set("tag")} placeholder={t("golden.tagPh")} />
          </label>
          <button className="btn" onClick={() => { setFilters(EMPTY); setPage(1); }}>{t("common.clear")}</button>
        </div>
      </details>

      <SavedViews filters={filters} apply={(f) => { setFilters(f); setPage(1); }} t={t} />

      {/* Siralama + sonuc sayisi — sade ve belirgin. Uzun gorusmeleri buradan sirala. */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <p className="text-sm text-ink2">
          {calls && (<><span className="font-semibold text-ink">{calls.total}</span> {t("common.records")}</>)}
        </p>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-ink2">{t("calls.sortBy")}</span>
          <select className="input" value={sortBy} onChange={(e) => { setPage(1); setSortBy(e.target.value); }}>
            <option value="created_at:desc">{t("sort.newest")}</option>
            <option value="created_at:asc">{t("sort.oldest")}</option>
            <option value="duration:desc">{t("sort.durationDesc")}</option>
            <option value="duration:asc">{t("sort.durationAsc")}</option>
            <option value="score:desc">{t("sort.scoreDesc")}</option>
            <option value="score:asc">{t("sort.scoreAsc")}</option>
          </select>
        </label>
      </div>

      {isStaff && selected.size > 0 && (
        <div className="card flex flex-wrap items-center gap-2 border-l-4 p-3" style={{ borderLeftColor: "var(--series-1)" }}>
          <span className="text-sm font-semibold">{selected.size} {t("bulk.selected")}</span>
          <button className="btn !py-1 text-xs" onClick={() => doBulk("golden_on")}>⭐ {t("bulk.goldenOn")}</button>
          <button className="btn !py-1 text-xs" onClick={() => doBulk("golden_off")}>☆ {t("bulk.goldenOff")}</button>
          <input className="input !w-32 !py-1 text-xs" value={bulkTag} onChange={(e) => setBulkTag(e.target.value)} placeholder={t("golden.addTag")} />
          <button className="btn !py-1 text-xs" onClick={() => doBulk("tag_add")}>＋ {t("bulk.tagAdd")}</button>
          <button className="btn !py-1 text-xs" onClick={() => doBulk("tag_remove")}>− {t("bulk.tagRemove")}</button>
          <button className="btn !py-1 text-xs" style={{ color: "var(--status-critical)" }} onClick={() => doBulk("delete")}>🗑 {t("common.delete")}</button>
          <button className="btn !py-1 text-xs" onClick={() => setSelected(new Set())}>{t("bulk.clear")}</button>
        </div>
      )}

      {calls && (
        <CallTable calls={calls.items} selectable={!!isStaff} selected={selected}
          onToggle={toggleSel} onToggleAll={toggleAll} />
      )}

      {calls && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>{t("common.prev")}</button>
          <span className="text-ink2">
            {t("common.page")} {page} / {totalPages} · {calls.total} {t("common.records")}
          </span>
          <button className="btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>{t("common.next")}</button>
        </div>
      )}
    </div>
  );
}

/** Yeni kurum icin rehberli ilk kullanim — kurulum tamamlanana kadar gorunur. */
function GettingStarted() {
  const t = useT();
  const [st, setSt] = useState<OnboardingStatus | null>(null);
  useEffect(() => { api.onboardingStatus().then(setSt).catch(() => {}); }, []);
  if (!st || st.complete) return null;
  const items = [
    { done: st.brand_set, key: "gs.brand" },
    { done: st.has_teams, key: "gs.teams" },
    { done: st.has_agents, key: "gs.agents" },
    { done: st.has_users, key: "gs.invite" },
    { done: st.has_rubric, key: "gs.rubric" },
    { done: st.has_calls, key: "gs.calls" },
  ];
  const doneN = items.filter((i) => i.done).length;
  return (
    <div className="card border-l-4 p-4" style={{ borderLeftColor: "var(--series-1)" }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">🚀 {t("gs.title")}</h2>
          <p className="text-sm text-ink2">{t("gs.subtitle", { done: String(doneN), total: String(items.length) })}</p>
        </div>
        <Link href="/onboarding" className="btn btn-primary">{t("gs.continue")}</Link>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((i) => (
          <span key={i.key} className={`badge ${i.done ? "badge-good" : "badge-neutral"}`}>
            <span className="dot" />{i.done ? "✓ " : ""}{t(i.key)}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Kayıtlı görünümler: mevcut filtreyi isimle localStorage'a kaydet, tek tıkla uygula. */
function SavedViews({ filters, apply, t }: {
  filters: Filters; apply: (f: Filters) => void; t: (k: string) => string;
}) {
  const KEY = "kg_saved_views";
  const [views, setViews] = useState<{ name: string; filters: Filters }[]>([]);
  useEffect(() => {
    try { setViews(JSON.parse(localStorage.getItem(KEY) || "[]")); } catch { setViews([]); }
  }, []);
  function persist(next: { name: string; filters: Filters }[]) {
    setViews(next); localStorage.setItem(KEY, JSON.stringify(next));
  }
  function save() {
    const active = Object.values(filters).some(Boolean);
    if (!active) { alert(t("views.needFilter")); return; }
    const name = prompt(t("views.namePrompt"))?.trim();
    if (!name) return;
    persist([...views.filter((v) => v.name !== name), { name, filters }]);
  }
  return (
    <div className="flex flex-wrap items-center gap-2 px-1">
      <span className="text-xs text-muted">⭐ {t("views.title")}:</span>
      {views.length === 0 && <span className="text-xs text-muted">{t("views.empty")}</span>}
      {views.map((v) => (
        <span key={v.name} className="inline-flex items-center gap-1 bg-grid px-2.5 py-1 text-xs">
          <button className="font-medium hover:text-series" onClick={() => apply({ ...EMPTY, ...v.filters })}>{v.name}</button>
          <button className="text-muted hover:text-[var(--status-critical)]" aria-label="sil"
            onClick={() => persist(views.filter((x) => x.name !== v.name))}>×</button>
        </span>
      ))}
      <button className="btn !py-0.5 text-xs" onClick={save}>＋ {t("views.save")}</button>
    </div>
  );
}
