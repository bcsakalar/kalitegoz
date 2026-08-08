"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AgentAdmin, OnboardingStatus, Team, UserRow } from "@/lib/types";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";
import { ROLE_LABEL_KEYS } from "@/lib/api";

const STEPS = ["brand", "teams", "agents", "invite", "rubric", "calls"] as const;
const ROLE_OPTS = ["admin", "supervisor", "quality", "agent"];

export default function OnboardingPage() {
  const t = useT();
  const router = useRouter();
  const { me } = useAuth();
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [agents, setAgents] = useState<AgentAdmin[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [criteriaCount, setCriteriaCount] = useState(0);
  const [msg, setMsg] = useState("");
  const [lastLink, setLastLink] = useState("");

  const load = useCallback(() => {
    api.onboardingStatus().then(setStatus).catch(() => {});
    api.listTeams().then(setTeams).catch(() => {});
    api.listAgentsAdmin().then(setAgents).catch(() => {});
    api.listUsers().then(setUsers).catch(() => {});
    api.listCriteria().then((c) => setCriteriaCount(c.length)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  // Marka
  const [brand, setBrand] = useState({ brand_name: "", brand_color: "#2563eb" });
  useEffect(() => { if (me) setBrand((b) => ({ ...b, brand_name: b.brand_name || me.tenant_name })); }, [me]);
  async function saveBrand() {
    setMsg("");
    try { await api.updateBranding({ brand_name: brand.brand_name, brand_color: brand.brand_color }); setMsg(t("wiz.saved")); load(); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  }
  // Ekip
  const [teamName, setTeamName] = useState("");
  async function addTeam(e: React.FormEvent) {
    e.preventDefault(); if (!teamName.trim()) return;
    try { await api.createTeam({ name: teamName.trim() }); setTeamName(""); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  // Temsilci
  const [agentForm, setAgentForm] = useState({ name: "", team_id: "" });
  async function addAgent(e: React.FormEvent) {
    e.preventDefault(); if (!agentForm.name.trim()) return;
    try { await api.createAgentAdmin({ name: agentForm.name.trim(), team_id: agentForm.team_id ? Number(agentForm.team_id) : null }); setAgentForm({ name: "", team_id: "" }); load(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }
  // Davet
  const [inv, setInv] = useState({ email: "", name: "", role: "supervisor", team_id: "" });
  async function invite(e: React.FormEvent) {
    e.preventDefault(); setMsg(""); setLastLink("");
    try {
      const r = await api.inviteUser({ email: inv.email, name: inv.name, role: inv.role, team_id: inv.team_id ? Number(inv.team_id) : null });
      setInv({ email: "", name: "", role: "supervisor", team_id: "" });
      setMsg(r.emailed ? t("org.inviteEmailed") : t("org.inviteLinkReady"));
      if (!r.emailed) setLastLink(r.invite_url);
      load();
    } catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }

  if (!me) return null;
  const done = [status?.brand_set, status?.has_teams, status?.has_agents, status?.has_users, (criteriaCount > 0), status?.has_calls];
  const doneCount = done.filter(Boolean).length;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">{t("wiz.welcome")} {me.tenant_name} 👋</h1>
        <p className="mt-1 text-ink2">{t("wiz.subtitle")}</p>
      </div>

      {/* Ilerleme */}
      <div className="card p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">{t("wiz.progress")}</span>
          <span className="text-ink2">{doneCount} / {STEPS.length}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-grid">
          <div className="h-full rounded-full bg-series transition-all" style={{ width: `${(doneCount / STEPS.length) * 100}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {STEPS.map((s, i) => (
            <button key={s} onClick={() => setStep(i)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${i === step ? "bg-series text-white" : "bg-surface-2 text-ink2"}`}>
              <span>{done[i] ? "✓" : i + 1}</span> {t(`wiz.step.${s}`)}
            </button>
          ))}
        </div>
      </div>

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

      {/* Adim govdesi */}
      <div className="card space-y-4 p-5">
        <h2 className="text-lg font-semibold">{t(`wiz.step.${STEPS[step]}`)}</h2>

        {step === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.brandHint")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block"><span className="mb-1 block text-xs text-ink2">{t("setup.orgName")}</span>
                <input className="input w-full" value={brand.brand_name} onChange={(e) => setBrand({ ...brand, brand_name: e.target.value })} /></label>
              <label className="block"><span className="mb-1 block text-xs text-ink2">{t("wiz.brandColor")}</span>
                <input type="color" className="input h-10 w-full" value={brand.brand_color} onChange={(e) => setBrand({ ...brand, brand_color: e.target.value })} /></label>
            </div>
            <button className="btn btn-primary" onClick={saveBrand}>{t("wiz.saveBrand")}</button>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.teamsHint")}</p>
            <form onSubmit={addTeam} className="flex gap-2">
              <input className="input flex-1" placeholder={t("org.teamName")} value={teamName} onChange={(e) => setTeamName(e.target.value)} />
              <button className="btn btn-primary">{t("org.add")}</button>
            </form>
            <ul className="flex flex-wrap gap-2">
              {teams.map((tm) => <li key={tm.id} className="badge badge-info"><span className="dot" />{tm.name}</li>)}
              {teams.length === 0 && <li className="text-xs text-muted">{t("org.noTeams")}</li>}
            </ul>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.agentsHint")}</p>
            <form onSubmit={addAgent} className="flex flex-wrap gap-2">
              <input className="input flex-1" placeholder={t("org.agentName")} value={agentForm.name} onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })} />
              <select className="input" value={agentForm.team_id} onChange={(e) => setAgentForm({ ...agentForm, team_id: e.target.value })}>
                <option value="">{t("org.noTeam")}</option>
                {teams.map((tm) => <option key={tm.id} value={tm.id}>{tm.name}</option>)}
              </select>
              <button className="btn btn-primary">{t("org.add")}</button>
            </form>
            <ul className="flex flex-wrap gap-2">
              {agents.map((a) => <li key={a.id} className="badge badge-neutral"><span className="dot" />{a.name}</li>)}
              {agents.length === 0 && <li className="text-xs text-muted">{t("org.noAgents")}</li>}
            </ul>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.inviteHint")}</p>
            <form onSubmit={invite} className="grid gap-2 sm:grid-cols-2">
              <input className="input" placeholder={t("org.name")} value={inv.name} required onChange={(e) => setInv({ ...inv, name: e.target.value })} />
              <input className="input" type="email" placeholder={t("org.email")} value={inv.email} required onChange={(e) => setInv({ ...inv, email: e.target.value })} />
              <select className="input" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}>
                {ROLE_OPTS.map((r) => <option key={r} value={r}>{t(ROLE_LABEL_KEYS[r] ?? r)}</option>)}
              </select>
              <select className="input" value={inv.team_id} onChange={(e) => setInv({ ...inv, team_id: e.target.value })}>
                <option value="">{t("org.noTeam")}</option>
                {teams.map((tm) => <option key={tm.id} value={tm.id}>{tm.name}</option>)}
              </select>
              <button className="btn btn-primary sm:col-span-2">{t("org.inviteBtn")}</button>
            </form>
            <ul className="text-sm text-ink2">
              {users.filter((u) => u.role !== "admin").map((u) => (
                <li key={u.id} className="flex items-center gap-2 py-0.5">
                  <span>{u.name} — {t(ROLE_LABEL_KEYS[u.role] ?? u.role)}</span>
                  {!u.password_set && <span className="badge badge-warning !py-0"><span className="dot" />{t("org.pendingInvite")}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.rubricHint", { n: String(criteriaCount) })}</p>
            <Link href="/rubric" className="btn btn-primary inline-flex">{t("wiz.goRubric")}</Link>
          </div>
        )}

        {step === 5 && (
          <div className="space-y-3">
            <p className="text-sm text-ink2">{t("wiz.callsHint")}</p>
            <ul className="ml-4 list-disc space-y-1 text-sm text-ink2">
              <li>{t("wiz.callWay1")}</li>
              <li>{t("wiz.callWay2")}</li>
              <li>{t("wiz.callWay3")}</li>
            </ul>
            <Link href="/" className="btn btn-primary inline-flex">{t("wiz.goCalls")}</Link>
          </div>
        )}

        {/* Gezinme */}
        <div className="flex items-center justify-between border-t border-hairline pt-4">
          <button className="btn" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>{t("wiz.back")}</button>
          {step < STEPS.length - 1 ? (
            <button className="btn btn-primary" onClick={() => setStep((s) => s + 1)}>{t("wiz.next")}</button>
          ) : (
            <button className="btn btn-primary" onClick={() => router.replace("/")}>{t("wiz.finish")}</button>
          )}
        </div>
      </div>

      <p className="text-center text-sm">
        <button className="text-ink2 hover:underline" onClick={() => router.replace("/")}>{t("wiz.skipToApp")}</button>
      </p>
    </div>
  );
}
