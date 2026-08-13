"use client";

import { useT } from "@/components/I18nProvider";
import { useCallback, useEffect, useRef, useState } from "react";
import AITab from "@/components/AITab";
import SSOTab from "@/components/SSOTab";
import { api, fmtDate, ROLE_LABEL_KEYS, VIOLATION_LABEL_KEYS } from "@/lib/api";
import type {
  BannedWord, Campaign, KnowledgeDoc, KnowledgeHit, ProcessingStatus, UserRow, CompliancePack, Challenge,
  AuditEntry, DraftCriterion, ScorecardDraft, Branding, Team, AgentAdmin, TenantSettings, SystemInfo,
} from "@/lib/types";

const TABS = [
  { id: "processing", key: "admin.processing" },
  { id: "scorecard", key: "scorecard.title" },
  { id: "banned", key: "admin.bannedWords" },
  { id: "knowledge", key: "admin.knowledge" },
  { id: "campaigns", key: "admin.campaigns" },
  { id: "users", key: "admin.users" },
  { id: "branding", key: "brand.title" },
  { id: "settings", key: "settings.title" },
  { id: "ai", key: "ai.title" },
  { id: "sso", key: "sso.title" },
  { id: "audit", key: "audit.title" },
  { id: "demo", key: "admin.demo" },
];

export default function AdminPage() {
  const t = useT();
  const [tab, setTab] = useState("processing");
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t("admin.title")}</h1>
      <div className="flex flex-wrap gap-1 border-b border-hairline">
        {TABS.map((tb) => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            className={`px-3 py-2 text-sm font-medium ${tab === tb.id ? "border-b-2 border-series text-ink" : "text-ink2"}`}>
            {t(tb.key)}
          </button>
        ))}
      </div>
      {tab === "processing" && <ProcessingTab />}
      {tab === "scorecard" && <ScorecardTab />}
      {tab === "banned" && <BannedTab />}
      {tab === "knowledge" && <KnowledgeTab />}
      {tab === "campaigns" && <CampaignTab />}
      {tab === "users" && <UsersTab />}
      {tab === "branding" && <BrandingTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "ai" && <AITab />}
      {tab === "sso" && <SSOTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "demo" && <DemoTab />}
    </div>
  );
}

/** Santral CSV export'unu çağrılarla eşleştir (toplu içe aktarma). */
function MetadataImportCard() {
  const t = useT();
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setMsg("");
    try { const r = await api.importMetadata(f); setMsg(r.message); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); if (ref.current) ref.current.value = ""; }
  }

  return (
    <div className="card space-y-3 p-4">
      <h2 className="text-sm font-semibold text-ink2">{t("meta.title")}</h2>
      <p className="text-sm text-ink2">{t("meta.body")}</p>
      <pre className="overflow-x-auto bg-grid/50 p-2.5 text-xs">
{`dosya;temsilci;kampanya;musteri_ref
ayse.yilmaz_01.wav;ayse.yilmaz;Satış Hattı;MUS-1024`}
      </pre>
      <p className="text-xs text-muted">{t("meta.hint")}</p>
      <input ref={ref} type="file" accept=".csv" className="hidden" onChange={upload} />
      <button className="btn btn-primary" disabled={busy} onClick={() => ref.current?.click()}>
        {busy ? t("adm.processing") : t("meta.upload")}
      </button>
      {msg && <p className="text-sm text-ink2">{msg}</p>}
    </div>
  );
}

function ProcessingTab() {
  const t = useT();
  const [st, setSt] = useState<ProcessingStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    api.processingStatus().then(setSt).catch((e) => setMsg(String(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!st || st.running_calls === 0) return;
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [st, load]);

  async function act(fn: () => Promise<ProcessingStatus>, note: string) {
    setBusy(true); setMsg("");
    try { const r = await fn(); setSt(r); setMsg(note); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  if (!st) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  const waiting = st.pending_calls + st.failed_calls;

  return (
    <div className="space-y-3">
      <div className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">{t("proc.title")}</h2>
            <p className="mt-1 max-w-2xl text-sm text-ink2">{t("proc.desc")}</p>
          </div>
          {st.paused
            ? <span className="badge badge-warning"><span className="dot" aria-hidden />{t("proc.paused")}</span>
            : <span className="badge badge-good"><span className="dot" aria-hidden />{t("proc.auto")}</span>}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="bg-grid/40 p-3">
            <div className="text-xs text-ink2">{t("proc.pending")}</div>
            <div className="text-2xl font-semibold">{st.pending_calls}</div>
          </div>
          <div className="bg-grid/40 p-3">
            <div className="text-xs text-ink2">{t("proc.running")}</div>
            <div className="text-2xl font-semibold">{st.running_calls}</div>
          </div>
          <div className="bg-grid/40 p-3">
            <div className="text-xs text-ink2">{t("proc.failed")}</div>
            <div className="text-2xl font-semibold">{st.failed_calls}</div>
          </div>
          <div className="bg-grid/40 p-3">
            <div className="text-xs text-ink2">{t("proc.completed")}</div>
            <div className="text-2xl font-semibold">{st.done_calls}</div>
          </div>
        </div>

        {/* Sesli isci uyarisi.

            Sesli cagrilar host'taki native worker'a gider. O calismiyorken
            "baslat" gorevleri kuyruga atar, Celery basariyla doner ve
            cagrilar sonsuza kadar bekler — hicbir hata gorunmeden. Uyari
            burada, butonun HEMEN USTUNDE duruyor. */}
        {st.voice_worker_active === false && st.pending_calls > 0 && (
          <p className="card mt-4 border-l-4 p-3 text-sm"
             style={{ borderLeftColor: "var(--status-warning)" }}>
            ⚠ {st.voice_worker_hint || t("proc.voiceWorkerOff")}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" disabled={busy || waiting === 0}
            onClick={() => act(api.startProcessing, t("proc.startedMsg"))}>
            {busy ? "…" : `${t("proc.start")}${waiting ? ` (${waiting})` : ""}`}
          </button>
          {st.paused
            ? <button className="btn" disabled={busy} onClick={() => act(api.resumeProcessing, t("proc.resumedMsg"))}>
                {t("proc.resume")}
              </button>
            : <button className="btn" disabled={busy} onClick={() => act(api.pauseProcessing, t("proc.pausedMsg"))}>
                {t("proc.pause")}
              </button>}
          <button className="btn" disabled={busy} onClick={load}>↻ {t("common.refresh")}</button>
        </div>

        {waiting === 0 && st.running_calls === 0 && <p className="mt-3 text-sm text-muted">{t("proc.allDone")}</p>}
        {st.running_calls > 0 && (
          <p className="mt-3 text-sm text-ink2">⏳ {st.running_calls} {t("proc.processingNow")}</p>
        )}
        {msg && <p className="mt-3 text-sm text-ink2">{msg}</p>}
      </div>

      <div className="card p-4 text-sm text-ink2">
        <b>{t("proc.tuneTitle")}</b> <code>.env</code> {t("proc.tuneBody")}
      </div>
    </div>
  );
}

function KnowledgeTab() {
  const t = useT();
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [stats, setStats] = useState<{ documents: number; chunks: number; rag_active: boolean } | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api.listKnowledgeDocs().then(setDocs).catch(() => {});
    api.knowledgeStats().then(setStats).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setMsg("");
    try { const d = await api.uploadKnowledgeDoc(f, ""); setMsg(`'${d.title}' ${t("kb.indexed")} (${d.chunk_count} ${t("kb.chunks")}).`); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }
  async function seedDemo() {
    setBusy(true); setMsg("");
    try { const d = await api.seedKnowledge(); setMsg(`${t("kb.demoReady")}: '${d.title}' (${d.chunk_count} ${t("kb.chunks")}).`); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }
  async function search() {
    if (q.trim().length < 2) return;
    setBusy(true);
    try { setHits(await api.searchKnowledge(q)); } catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }
  async function remove(id: number) {
    if (!confirm(t("kb.deleteConfirm"))) return;
    await api.deleteKnowledgeDoc(id); load();
  }

  return (
    <div className="space-y-3">
      <div className="card p-4 text-sm">
        <p className="text-ink2">{t("kb.intro")}</p>
        <p className="mt-2">
          {t("kb.status")}:{" "}
          {stats?.rag_active
            ? <span className="badge badge-good"><span className="dot" aria-hidden />{t("kb.ragActive")} — {stats.documents} {t("kb.docs")} / {stats.chunks} {t("kb.chunks")}</span>
            : <span className="badge badge-warning"><span className="dot" aria-hidden />{t("kb.ragEmpty")}</span>}
        </p>
      </div>

      <div className="card flex flex-wrap items-center gap-2 p-3">
        <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt" className="hidden" onChange={upload} />
        <button className="btn btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          {busy ? t("adm.processing") : t("kb.upload")}
        </button>
        <button className="btn" disabled={busy} onClick={seedDemo}>{t("kb.seedDemo")}</button>
        {msg && <span className="text-sm text-ink2">{msg}</span>}
      </div>

      {docs.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-hairline text-left text-xs uppercase text-muted">
              <th className="px-4 py-2">{t("kb.colDoc")}</th><th className="px-4 py-2">{t("kb.colFile")}</th>
              <th className="px-4 py-2">{t("kb.colChunks")}</th><th className="px-4 py-2">{t("kb.colDate")}</th><th className="px-4 py-2" /></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-b border-hairline last:border-0">
                  <td className="px-4 py-2 font-medium">{d.title}</td>
                  <td className="px-4 py-2 text-ink2">{d.source_filename}</td>
                  <td className="px-4 py-2 tabular-nums">{d.chunk_count}</td>
                  <td className="px-4 py-2 text-ink2">{fmtDate(d.created_at)}</td>
                  <td className="px-4 py-2 text-right"><button className="btn !py-0.5 text-xs" onClick={() => remove(d.id)}>{t("adm.delete")}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card p-3">
        <h3 className="text-sm font-semibold text-ink2">{t("kb.searchTitle")}</h3>
        <div className="mt-2 flex gap-2">
          <input className="input flex-1" placeholder={t("kb.searchPlaceholder")} value={q}
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
          <button className="btn" disabled={busy} onClick={search}>{t("kb.search")}</button>
        </div>
        {hits && (
          <div className="mt-3 space-y-2">
            {hits.length === 0 && <p className="text-sm text-muted">{t("kb.noMatch")}</p>}
            {hits.map((h, i) => (
              <div key={i} className="bg-grid/40 p-2.5 text-sm">
                <div className="text-xs text-muted">{h.doc_title} #{h.idx} · {t("kb.similarity")} {h.similarity}</div>
                <p className="mt-1 whitespace-pre-wrap">{h.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const CATS = ["hakaret", "kucumseme", "rakip", "yasak_vaat", "mevzuat"];
const SEVS = ["dusuk", "orta", "yuksek"];
const MATCHES = ["fuzzy", "exact", "regex"];

function BannedTab() {
  const t = useT();
  const [words, setWords] = useState<BannedWord[]>([]);
  const [nw, setNw] = useState({ term: "", category: "hakaret", severity: "orta", match_type: "fuzzy" });
  const [error, setError] = useState("");
  const load = useCallback(() => { api.listBannedWords().then(setWords).catch((e) => setError(String(e))); }, []);
  useEffect(() => { load(); }, [load]);

  async function add() {
    if (nw.term.trim().length < 1) return;
    try { await api.createBannedWord(nw); setNw({ ...nw, term: "" }); load(); }
    catch (e) { setError(String(e)); }
  }
  async function toggle(w: BannedWord) { await api.updateBannedWord(w.id, { is_active: !w.is_active }); load(); }
  async function remove(id: number) { await api.deleteBannedWord(id); load(); }

  return (
    <div className="space-y-3">
      {error && <p className="card p-3 text-sm">{error}</p>}
      <div className="card flex flex-wrap items-end gap-2 p-3">
        <input className="input flex-1" placeholder={t("bw.term")} value={nw.term}
          onChange={(e) => setNw({ ...nw, term: e.target.value })} />
        <select className="input" value={nw.category} onChange={(e) => setNw({ ...nw, category: e.target.value })}>
          {CATS.map((c) => <option key={c} value={c}>{t(VIOLATION_LABEL_KEYS[c] ?? "") || c}</option>)}
        </select>
        <select className="input" value={nw.severity} onChange={(e) => setNw({ ...nw, severity: e.target.value })}>
          {SEVS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" value={nw.match_type} onChange={(e) => setNw({ ...nw, match_type: e.target.value })}>
          {MATCHES.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <button className="btn btn-primary" onClick={add}>{t("adm.add")}</button>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-hairline text-left text-xs uppercase text-muted">
            <th className="px-4 py-2">{t("bw.colTerm")}</th><th className="px-4 py-2">{t("bw.colCategory")}</th>
            <th className="px-4 py-2">{t("bw.colSeverity")}</th><th className="px-4 py-2">{t("bw.colMatch")}</th>
            <th className="px-4 py-2">{t("adm.active")}</th><th className="px-4 py-2" /></tr></thead>
          <tbody>
            {words.map((w) => (
              <tr key={w.id} className="border-b border-hairline last:border-0">
                <td className="px-4 py-2 font-medium">{w.term}</td>
                <td className="px-4 py-2">{t(VIOLATION_LABEL_KEYS[w.category] ?? "") || w.category}</td>
                <td className="px-4 py-2">{w.severity}</td>
                <td className="px-4 py-2">{w.match_type}</td>
                <td className="px-4 py-2"><input type="checkbox" checked={w.is_active} onChange={() => toggle(w)} /></td>
                <td className="px-4 py-2 text-right"><button className="btn !py-0.5 text-xs" onClick={() => remove(w.id)}>{t("adm.delete")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CampaignTab() {
  const t = useT();
  const [camps, setCamps] = useState<Campaign[]>([]);
  const [nc, setNc] = useState({ name: "", channel: "voice", description: "" });
  const load = useCallback(() => { api.listCampaigns().then(setCamps).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  async function add() { if (nc.name.trim().length < 2) return; await api.createCampaign(nc); setNc({ name: "", channel: "voice", description: "" }); load(); }
  async function remove(id: number) { if (confirm(t("camp.deleteConfirm"))) { await api.deleteCampaign(id); load(); } }

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-end gap-2 p-3">
        <input className="input flex-1" placeholder={t("camp.name")} value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} />
        <select className="input" value={nc.channel} onChange={(e) => setNc({ ...nc, channel: e.target.value })}>
          <option value="voice">{t("adm.voice")}</option><option value="chat">{t("adm.chat")}</option>
        </select>
        <input className="input flex-1" placeholder={t("camp.description")} value={nc.description} onChange={(e) => setNc({ ...nc, description: e.target.value })} />
        <button className="btn btn-primary" onClick={add}>{t("adm.add")}</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {camps.map((c) => (
          <div key={c.id} className="card flex items-center justify-between p-3">
            <div>
              <div className="font-semibold">{c.name} <span className="text-xs text-muted">({c.channel})</span></div>
              <div className="text-xs text-ink2">{c.description}</div>
            </div>
            <button className="btn !py-0.5 text-xs" onClick={() => remove(c.id)}>{t("adm.delete")}</button>
          </div>
        ))}
      </div>
    </div>
  );
}

const ROLE_OPTS = ["admin", "supervisor", "quality", "agent"];

/** Kurum yonetimi: kullanici davet + ekip + temsilci CRUD. */
function UsersTab() {
  const t = useT();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [agents, setAgents] = useState<AgentAdmin[]>([]);
  const [lastLink, setLastLink] = useState("");
  const [msg, setMsg] = useState("");
  const [inv, setInv] = useState({ email: "", name: "", role: "agent", team_id: "", agent_id: "" });
  const [teamName, setTeamName] = useState("");
  const [agentForm, setAgentForm] = useState({ name: "", team_id: "" });

  const load = useCallback(() => {
    api.listUsers().then(setUsers).catch(() => {});
    api.listTeams().then(setTeams).catch(() => {});
    api.listAgentsAdmin().then(setAgents).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  async function invite(e: React.FormEvent) {
    e.preventDefault(); setMsg(""); setLastLink("");
    try {
      const r = await api.inviteUser({
        email: inv.email, name: inv.name, role: inv.role,
        team_id: inv.team_id ? Number(inv.team_id) : null,
        agent_id: inv.agent_id ? Number(inv.agent_id) : null,
      });
      setInv({ email: "", name: "", role: "agent", team_id: "", agent_id: "" });
      setMsg(r.emailed ? t("org.inviteEmailed") : t("org.inviteLinkReady"));
      if (!r.emailed) setLastLink(r.invite_url);
      load();
    } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function regen(id: number) {
    setMsg(""); setLastLink("");
    try { const r = await api.regenerateLink(id); setLastLink(r.invite_url); setMsg(r.emailed ? t("org.inviteEmailed") : t("org.inviteLinkReady")); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function delUser(id: number) {
    if (!confirm(t("org.delUserConfirm"))) return;
    try { await api.deleteUser(id); load(); } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function addTeam(e: React.FormEvent) {
    e.preventDefault(); if (!teamName.trim()) return;
    try { await api.createTeam({ name: teamName.trim() }); setTeamName(""); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function delTeam(id: number) {
    if (!confirm(t("org.delTeamConfirm"))) return;
    try { await api.deleteTeam(id); load(); } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function addAgent(e: React.FormEvent) {
    e.preventDefault(); if (!agentForm.name.trim()) return;
    try { await api.createAgentAdmin({ name: agentForm.name.trim(), team_id: agentForm.team_id ? Number(agentForm.team_id) : null }); setAgentForm({ name: "", team_id: "" }); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function reassignAgent(id: number, team_id: string, name: string) {
    try { await api.updateAgentAdmin(id, { name, team_id: team_id ? Number(team_id) : null }); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  async function delAgent(id: number) {
    if (!confirm(t("org.delAgentConfirm"))) return;
    try { await api.deleteAgentAdmin(id); load(); } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }

  return (
    <div className="space-y-4">
      {msg && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-good)" }}>{msg}</p>}
      {lastLink && (
        <div className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--series-1)" }}>
          <div className="mb-1 font-semibold">{t("org.linkShare")}</div>
          <div className="flex items-center gap-2">
            <input readOnly className="input w-full font-mono text-xs" value={lastLink} onFocus={(e) => e.target.select()} />
            <button className="btn" onClick={() => navigator.clipboard?.writeText(lastLink)}>{t("org.copy")}</button>
          </div>
        </div>
      )}

      {/* Kullanici davet */}
      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">👤 {t("org.inviteTitle")}</h2>
        <form onSubmit={invite} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <input className="input" placeholder={t("org.name")} value={inv.name} required onChange={(e) => setInv({ ...inv, name: e.target.value })} />
          <input className="input" type="email" placeholder={t("org.email")} value={inv.email} required onChange={(e) => setInv({ ...inv, email: e.target.value })} />
          <select className="input" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}>
            {ROLE_OPTS.map((r) => <option key={r} value={r}>{t(ROLE_LABEL_KEYS[r] ?? r)}</option>)}
          </select>
          <select className="input" value={inv.team_id} onChange={(e) => setInv({ ...inv, team_id: e.target.value })}>
            <option value="">{t("org.noTeam")}</option>
            {teams.map((tm) => <option key={tm.id} value={tm.id}>{tm.name}</option>)}
          </select>
          {inv.role === "agent" ? (
            <select className="input" value={inv.agent_id} onChange={(e) => setInv({ ...inv, agent_id: e.target.value })}>
              <option value="">{t("org.linkAgent")}</option>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          ) : <span />}
          <button className="btn btn-primary lg:col-span-1">{t("org.inviteBtn")}</button>
        </form>
      </div>

      {/* Kullanici listesi */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-hairline text-left text-xs uppercase text-muted">
            <th className="px-4 py-2">{t("usr.colName")}</th><th className="px-4 py-2">{t("usr.colEmail")}</th>
            <th className="px-4 py-2">{t("usr.colRole")}</th><th className="px-4 py-2">{t("adm.active")}</th>
            <th className="px-4 py-2"></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-hairline last:border-0">
                <td className="px-4 py-2 font-medium">{u.name}</td>
                <td className="px-4 py-2 text-ink2">{u.email}</td>
                <td className="px-4 py-2">{t(ROLE_LABEL_KEYS[u.role] ?? u.role)}</td>
                <td className="px-4 py-2">
                  {!u.password_set ? <span className="badge badge-warning"><span className="dot" />{t("org.pendingInvite")}</span>
                    : u.is_active ? "✓" : "—"}
                </td>
                <td className="px-4 py-2 text-right whitespace-nowrap">
                  <button className="text-xs text-series hover:underline" onClick={() => regen(u.id)}>{u.password_set ? t("org.resetLink") : t("org.inviteLink")}</button>
                  <button className="ml-3 text-xs text-[var(--status-critical)] hover:underline" onClick={() => delUser(u.id)}>{t("common.delete")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ekipler + Temsilciler yan yana */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-ink2">👥 {t("org.teams")}</h2>
          <form onSubmit={addTeam} className="flex gap-2">
            <input className="input flex-1" placeholder={t("org.teamName")} value={teamName} onChange={(e) => setTeamName(e.target.value)} />
            <button className="btn btn-primary">{t("org.add")}</button>
          </form>
          <ul className="divide-y divide-hairline">
            {teams.map((tm) => (
              <li key={tm.id} className="flex items-center justify-between py-2 text-sm">
                <span>{tm.name}</span>
                <button className="text-xs text-[var(--status-critical)] hover:underline" onClick={() => delTeam(tm.id)}>{t("common.delete")}</button>
              </li>
            ))}
            {teams.length === 0 && <li className="py-2 text-xs text-muted">{t("org.noTeams")}</li>}
          </ul>
        </div>

        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-ink2">🎧 {t("org.agents")}</h2>
          <form onSubmit={addAgent} className="flex flex-wrap gap-2">
            <input className="input flex-1" placeholder={t("org.agentName")} value={agentForm.name} onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })} />
            <select className="input" value={agentForm.team_id} onChange={(e) => setAgentForm({ ...agentForm, team_id: e.target.value })}>
              <option value="">{t("org.noTeam")}</option>
              {teams.map((tm) => <option key={tm.id} value={tm.id}>{tm.name}</option>)}
            </select>
            <button className="btn btn-primary">{t("org.add")}</button>
          </form>
          <ul className="divide-y divide-hairline">
            {agents.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className="flex-1 truncate">{a.name}</span>
                <select className="input !py-1 text-xs" value={a.team_id ?? ""} onChange={(e) => reassignAgent(a.id, e.target.value, a.name)}>
                  <option value="">{t("org.noTeam")}</option>
                  {teams.map((tm) => <option key={tm.id} value={tm.id}>{tm.name}</option>)}
                </select>
                <button className="text-xs text-[var(--status-critical)] hover:underline" onClick={() => delAgent(a.id)}>{t("common.delete")}</button>
              </li>
            ))}
            {agents.length === 0 && <li className="py-2 text-xs text-muted">{t("org.noAgents")}</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}

const NOTIFY_EVENTS = ["zeroing", "crisis", "banned_word", "low_score", "score_drop"];

/** Kurum-bazli ayarlar + salt-okunur sistem bilgisi. */
function SettingsTab() {
  const t = useT();
  const [s, setS] = useState<TenantSettings | null>(null);
  const [sys, setSys] = useState<SystemInfo | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.getSettings().then(setS).catch(() => {});
    api.systemInfo().then(setSys).catch(() => {});
  }, []);

  async function save() {
    if (!s) return;
    setMsg("");
    try {
      const u = await api.updateSettings({ retention_days: s.retention_days, auto_process: s.auto_process, notify_events: s.notify_events });
      setS(u); setMsg(t("wiz.saved"));
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  }
  function toggleEvent(ev: string) {
    if (!s) return;
    const has = s.notify_events.includes(ev);
    setS({ ...s, notify_events: has ? s.notify_events.filter((x) => x !== ev) : [...s.notify_events, ev] });
  }

  if (!s) return <p className="text-sm text-muted">…</p>;
  return (
    <div className="space-y-4">
      {msg && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-good)" }}>{msg}</p>}
      <div className="card space-y-4 p-4">
        <h2 className="text-sm font-semibold text-ink2">⚙️ {t("settings.orgTitle")}</h2>
        <label className="block max-w-xs"><span className="mb-1 block text-xs text-ink2">{t("settings.retention")}</span>
          <input type="number" min={1} max={3650} className="input w-full" value={s.retention_days}
            onChange={(e) => setS({ ...s, retention_days: Number(e.target.value) })} />
          <span className="mt-1 block text-xs text-muted">{t("settings.retentionHint")}</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={s.auto_process} onChange={(e) => setS({ ...s, auto_process: e.target.checked })} />
          {t("settings.autoProcess")}
        </label>
        <div>
          <div className="mb-1 text-xs text-ink2">{t("settings.notify")}</div>
          <div className="flex flex-wrap gap-3">
            {NOTIFY_EVENTS.map((ev) => (
              <label key={ev} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={s.notify_events.includes(ev)} onChange={() => toggleEvent(ev)} />
                {t(`settings.event.${ev}`)}
              </label>
            ))}
          </div>
        </div>
        <button className="btn btn-primary" onClick={save}>{t("settings.save")}</button>
      </div>

      {sys && (
        <div className="card space-y-2 p-4">
          <h2 className="text-sm font-semibold text-ink2">🖥️ {t("settings.systemTitle")}</h2>
          <p className="text-xs text-muted">{t("settings.systemHint")}</p>
          <dl className="grid gap-x-6 text-sm sm:grid-cols-2">
            <SRow k="LLM" v={`${sys.llm_provider} · ${sys.llm_model}`} />
            <SRow k="Whisper (STT)" v={`${sys.whisper_model} · ${sys.whisper_device}`} />
            <SRow k={t("settings.vision")} v={sys.vision_enabled ? t("settings.on") : t("settings.off")} />
            <SRow k="RAG" v={sys.rag_enabled ? t("settings.on") : t("settings.off")} />
            <SRow k="SSO" v={sys.sso_enabled ? t("settings.on") : t("settings.off")} />
            <SRow k={t("settings.demoMode")} v={sys.demo_mode ? t("settings.on") : t("settings.off")} />
            <SRow k={t("settings.pii")} v={sys.pii_masking ? t("settings.on") : t("settings.off")} />
            <SRow k="SMTP" v={sys.smtp_configured ? t("settings.on") : t("settings.smtpOff")} />
          </dl>
        </div>
      )}
    </div>
  );
}

function SRow({ k, v }: { k: string; v: string }) {
  return (<div className="flex justify-between border-b border-hairline py-1"><dt className="text-ink2">{k}</dt><dd className="font-medium">{v}</dd></div>);
}

function DemoTab() {
  const t = useT();
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function seed() {
    setBusy(true);
    try { const r = await api.seedHistory(); setMsg(r.message); }
    catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }
  async function demoReset() {
    if (!confirm(t("demo.resetConfirm"))) return;
    setBusy(true);
    try { const r = await api.demoReset(); setMsg(r.message); }
    catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }
  async function bulkRescore() {
    if (!confirm(t("dm.rescoreConfirm"))) return;
    setBusy(true);
    try { const r = await api.rescoreBulk(); setMsg(r.message); }
    catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3">
      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">{t("dm.rescoreTitle")}</h2>
        <p className="text-sm text-ink2">{t("dm.rescoreBody")}</p>
        <button className="btn btn-primary" disabled={busy} onClick={bulkRescore}>
          {busy ? t("dm.rescoreQueued") : t("dm.rescoreBtn")}
        </button>
      </div>

      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">{t("dm.seedTitle")}</h2>
        <p className="text-sm text-ink2">{t("dm.seedBody")}</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn" disabled={busy} onClick={seed}>{busy ? t("dm.seeding") : t("dm.seedBtn")}</button>
          <button className="btn" disabled={busy} onClick={demoReset}>{busy ? "…" : `♻ ${t("demo.reset")}`}</button>
        </div>
      </div>

      <MetadataImportCard />
      <ChallengeAdminCard />
      <CompliancePacksCard />

      <div className="card p-4">
        <h2 className="text-sm font-semibold text-ink2">{t("dm.retentionTitle")}</h2>
        <p className="mt-1 text-sm text-ink2">{t("dm.retentionBody")}</p>
      </div>

      {msg && <p className="card p-3 text-sm text-ink2">{msg}</p>}
    </div>
  );
}

/** No-code AI puan kartı üretici: doğal dil → rubrik taslağı → kaydet. */
function ScorecardTab() {
  const t = useT();
  const [prompt, setPrompt] = useState("");
  const [channel, setChannel] = useState("all");
  const [draft, setDraft] = useState<ScorecardDraft | null>(null);
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function generate() {
    if (prompt.trim().length < 10) return;
    setBusy(true); setMsg(""); setDraft(null);
    try { setDraft(await api.buildScorecard({ prompt, channel, max_criteria: 8 })); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!draft) return;
    setBusy(true); setMsg("");
    try {
      const r = await api.saveScorecard({ criteria: draft.criteria, replace_existing: replace });
      setMsg(`${r.created} ${t("scorecard.saved")}`); setDraft(null); setPrompt("");
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  function edit(i: number, patch: Partial<DraftCriterion>) {
    if (!draft) return;
    const c = draft.criteria.map((x, j) => (j === i ? { ...x, ...patch } : x));
    setDraft({ ...draft, criteria: c });
  }

  return (
    <div className="space-y-3">
      <div className="card space-y-3 p-4">
        <div>
          <h2 className="text-sm font-semibold text-ink2">✨ {t("scorecard.title")}</h2>
          <p className="text-sm text-ink2">{t("scorecard.subtitle")}</p>
        </div>
        <textarea className="input min-h-24 w-full" placeholder={t("scorecard.placeholder")}
          value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <div className="flex flex-wrap items-center gap-2">
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="all">{t("adm.allChannels")}</option>
            <option value="voice">{t("adm.voice")}</option>
            <option value="chat">{t("adm.chat")}</option>
          </select>
          <button className="btn btn-primary" disabled={busy || prompt.trim().length < 10} onClick={generate}>
            {busy && !draft ? t("scorecard.generating") : `✨ ${t("scorecard.generate")}`}
          </button>
          {msg && <span className="text-sm text-ink2">{msg}</span>}
        </div>
      </div>

      {draft && (
        <div className="card space-y-3 p-4">
          <p className="text-xs text-muted">{draft.note}</p>
          <div className="space-y-2">
            {draft.criteria.map((c, i) => (
              <div key={i} className="bg-grid/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <input className="input flex-1 !py-1 text-sm font-semibold" value={c.name}
                    onChange={(e) => edit(i, { name: e.target.value })} />
                  <span className="badge badge-neutral text-[10px]">{c.group}</span>
                  <label className="flex items-center gap-1 text-xs text-ink2">
                    {t("scorecard.weight")}
                    <input type="number" step={0.5} min={0.5} max={3} className="input !w-16 !py-0.5 text-xs"
                      value={c.weight} onChange={(e) => edit(i, { weight: Number(e.target.value) })} />
                  </label>
                  <label className="flex items-center gap-1 text-xs text-ink2">
                    <input type="checkbox" checked={c.is_critical} onChange={(e) => edit(i, { is_critical: e.target.checked })} />
                    {t("scorecard.critical")}
                  </label>
                </div>
                <textarea className="input mt-2 w-full !py-1 text-sm" value={c.description}
                  onChange={(e) => edit(i, { description: e.target.value })} />
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-1.5 text-sm text-ink2">
              <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
              {t("scorecard.replace")}
            </label>
            <button className="btn btn-primary" disabled={busy} onClick={save}>💾 {t("scorecard.save")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Beyaz etiket (white-label): tenant marka adı/renk/logo. */
function BrandingTab() {
  const t = useT();
  const [b, setB] = useState<Branding | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.getBranding().then(setB).catch(() => {}); }, []);

  function onLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f || !b) return;
    if (f.size > 200_000) { setMsg("Logo ≤ ~200 KB"); return; }
    const reader = new FileReader();
    reader.onload = () => setB({ ...b, logo_data_url: String(reader.result) });
    reader.readAsDataURL(f);
  }
  async function save() {
    if (!b) return;
    setBusy(true); setMsg("");
    try {
      const r = await api.updateBranding({ brand_name: b.brand_name, brand_color: b.brand_color, logo_data_url: b.logo_data_url });
      setB(r); setMsg(t("brand.saved"));
    } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  if (!b) return <p className="p-6 text-sm text-muted">…</p>;
  return (
    <div className="card space-y-4 p-4">
      <div>
        <h2 className="text-sm font-semibold text-ink2">🎨 {t("brand.title")}</h2>
        <p className="text-sm text-ink2">{t("brand.subtitle")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs text-ink2">{t("brand.name")}</span>
          <input className="input w-full" value={b.brand_name} onChange={(e) => setB({ ...b, brand_name: e.target.value })} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-ink2">{t("brand.color")}</span>
          <input type="color" className="h-10 w-20 border border-hairline" value={b.brand_color}
            onChange={(e) => setB({ ...b, brand_color: e.target.value })} />
        </label>
      </div>
      <div>
        <span className="mb-1 block text-xs text-ink2">{t("brand.logo")}</span>
        <div className="flex items-center gap-3">
          {b.logo_data_url && <img src={b.logo_data_url} alt="logo" className="h-10 max-w-40 object-contain" />}
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onLogo} />
          <button className="btn" onClick={() => fileRef.current?.click()}>⬆ {t("brand.logo")}</button>
          {b.logo_data_url && <button className="btn !py-1 text-xs" onClick={() => setB({ ...b, logo_data_url: null })}>{t("adm.remove")}</button>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button className="btn btn-primary" disabled={busy} onClick={save}>{t("brand.save")}</button>
        {msg && <span className="text-sm text-ink2">{msg}</span>}
      </div>
    </div>
  );
}

/** Denetim günlüğü görüntüleyici (append-only, KVKK/kurumsal). */
function AuditTab() {
  const t = useT();
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [action, setAction] = useState("");
  const [total, setTotal] = useState(0);

  const ACTIONS = ["", "login", "sso_login", "view_call", "reveal_pii", "download_audio",
    "override_score", "scorecard_save", "update_branding", "demo_reset", "rescore_bulk", "import_metadata"];

  const load = useCallback(() => {
    const params: Record<string, string> = { page: "1", page_size: "100" };
    if (action) params.action = action;
    api.auditLog(params).then((p) => { setRows(p.items); setTotal(p.total); }).catch(() => {});
  }, [action]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink2">{t("audit.subtitle")}</p>
        <select className="input" value={action} onChange={(e) => setAction(e.target.value)}>
          {ACTIONS.map((a) => <option key={a} value={a}>{a || t("audit.all")}</option>)}
        </select>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-hairline text-left text-xs uppercase text-muted">
            <th className="px-4 py-2">{t("audit.when")}</th><th className="px-4 py-2">{t("audit.who")}</th>
            <th className="px-4 py-2">{t("audit.action")}</th><th className="px-4 py-2">{t("audit.entity")}</th>
            <th className="px-4 py-2">{t("audit.ip")}</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-hairline last:border-0">
                <td className="px-4 py-2 tabular-nums text-ink2">{fmtDate(r.created_at)}</td>
                <td className="px-4 py-2">{r.user_name ?? `#${r.user_id ?? "—"}`}</td>
                <td className="px-4 py-2">
                  <span className={`badge ${r.action === "reveal_pii" ? "badge-warning" : "badge-neutral"} text-[10px]`}>{r.action}</span>
                </td>
                <td className="px-4 py-2 text-ink2">{r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                <td className="px-4 py-2 tabular-nums text-muted">{r.ip}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-muted">{t("audit.empty")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">{total} {t("aud.count")}</p>
    </div>
  );
}

/** Uyum paketleri (KVKK/PCI/…) — built-in kural setleri (Dalga 4a) */
function CompliancePacksCard() {
  const t = useT();
  const [packs, setPacks] = useState<CompliancePack[]>([]);
  useEffect(() => { api.compliancePacks().then(setPacks).catch(() => {}); }, []);
  return (
    <div className="card space-y-3 p-4">
      <div>
        <h2 className="text-sm font-semibold text-ink2">🛡 {t("compliance.title")}</h2>
        <p className="text-sm text-ink2">{t("cp.body")}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {packs.map((p) => (
          <div key={p.key} className="bg-grid/40 p-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">{p.name}</span>
              <span className="badge badge-neutral text-[10px]">{p.rules.length} {t("compliance.rules")}</span>
            </div>
            <p className="mt-1 text-xs text-muted">{p.description}</p>
            <ul className="mt-2 space-y-1">
              {p.rules.map((r) => (
                <li key={r.key} className="text-xs">
                  <span className={r.kind === "forbidden" ? "text-[var(--status-critical)]" : "text-[var(--status-good)]"}>
                    {r.kind === "forbidden" ? "⛔" : "✓"}
                  </span> {r.description}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Gamification hedefleri (challenge) tanımlama + liste (Dalga 3d) */
function ChallengeAdminCard() {
  const t = useT();
  const [list, setList] = useState<Challenge[]>([]);
  const [title, setTitle] = useState("");
  const [metric, setMetric] = useState("score_above");
  const [target, setTarget] = useState(10);
  const [reward, setReward] = useState(100);
  const [busy, setBusy] = useState(false);

  const load = () => api.listChallenges().then(setList).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create() {
    if (title.trim().length < 2) return;
    setBusy(true);
    try {
      await api.createChallenge({ title, metric, target, reward_points: reward });
      setTitle(""); load();
    } catch { /* yok say */ } finally { setBusy(false); }
  }

  const METRICS: Record<string, string> = {
    score_above: t("ch.mScoreAbove"), call_count: t("ch.mCallCount"),
    avg_score: t("ch.mAvgScore"), zero_violations: t("ch.mZeroViol"),
  };

  return (
    <div className="card space-y-3 p-4">
      <h2 className="text-sm font-semibold text-ink2">🎯 {t("challenge.create")}</h2>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs">
          <span className="block text-muted">{t("challenge.title")}</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)}
            className="mt-0.5 w-56 border border-hairline bg-surface2 px-2 py-1 text-sm" />
        </label>
        <label className="text-xs">
          <span className="block text-muted">{t("challenge.metric")}</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}
            className="mt-0.5 border border-hairline bg-surface2 px-2 py-1 text-sm">
            {Object.entries(METRICS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="block text-muted">{t("challenge.target")}</span>
          <input type="number" min={1} value={target} onChange={(e) => setTarget(Number(e.target.value))}
            className="mt-0.5 w-16 border border-hairline bg-surface2 px-2 py-1 text-sm" />
        </label>
        <label className="text-xs">
          <span className="block text-muted">{t("challenge.reward")}</span>
          <input type="number" min={0} value={reward} onChange={(e) => setReward(Number(e.target.value))}
            className="mt-0.5 w-20 border border-hairline bg-surface2 px-2 py-1 text-sm" />
        </label>
        <button className="btn btn-primary !py-1 text-xs" disabled={busy || title.trim().length < 2} onClick={create}>
          {t("challenge.add")}
        </button>
      </div>
      {list.length > 0 && (
        <ul className="space-y-1 text-sm">
          {list.map((c) => (
            <li key={c.id} className="flex items-center gap-2">
              <span className="flex-1">{c.title}</span>
              <span className="text-xs text-muted">{METRICS[c.metric]} · {t("challenge.target")} {c.target} · +{c.reward_points}p</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
