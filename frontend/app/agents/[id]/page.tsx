"use client";

import { useT } from "@/components/I18nProvider";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import CallTable from "@/components/CallTable";
import CriteriaBars from "@/components/CriteriaBars";
import StatTile from "@/components/StatTile";
import TrendChart from "@/components/TrendChart";
import { api, authedDownload, reportUrls } from "@/lib/api";
import type { AgentScorecard, CoachingPlan } from "@/lib/types";

export default function AgentScorecardPage() {
  const t = useT();
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<AgentScorecard | null>(null);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<CoachingPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState("");

  const load = useCallback(async () => {
    try { setAgent(await api.getAgent(id)); } catch (e) { setError(String(e)); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const genPlan = useCallback(async () => {
    setPlanLoading(true); setPlanError("");
    try { setPlan(await api.coachingPlan(id)); }
    catch (e) { setPlanError(String(e)); }
    finally { setPlanLoading(false); }
  }, [id]);

  if (error) return <p className="card p-6 text-sm">{t("common.error")}: {error}</p>;
  if (!agent) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  const best = agent.criteria.length ? agent.criteria[agent.criteria.length - 1] : null;
  const worst = agent.criteria.length ? agent.criteria[0] : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{agent.name}</h1>
          {agent.team_name && <p className="text-sm text-ink2">{agent.team_name}</p>}
        </div>
        <button className="btn" onClick={() => authedDownload(reportUrls.agentPdf(agent.id), `karne_${agent.name}.pdf`)}>
          {t("agents.pdfCard")}
        </button>
      </div>

      {agent.badges.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {agent.badges.map((b, i) => (
            <span key={i} className="badge badge-info" title={b.description}>
              <span aria-hidden>{b.icon}</span> {b.name}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatTile label={t("nav.calls")} value={String(agent.call_count)} />
        <StatTile label={t("stat.avgScore")} value={agent.avg_score != null ? agent.avg_score.toFixed(1) : "—"} hint="0–100" />
        <StatTile label={t("stat.csat")} value={agent.avg_csat != null ? `${agent.avg_csat}/5` : "—"} />
        <StatTile label={t("stat.zeroed")} value={String(agent.zeroed_count)} />
        <StatTile label={t("stat.crisis")} value={String(agent.crisis_count)} />
      </div>

      <div className="card space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="flex items-start gap-2 text-sm">
            <span aria-hidden>💡</span>
            <span><span className="font-semibold text-ink2">{t("agents.weeklyCoaching")}: </span>{agent.weekly_coaching}</span>
          </h2>
          <button className="btn btn-primary shrink-0 !py-1 text-xs" onClick={genPlan} disabled={planLoading}>
            {planLoading ? t("coach.generating") : `✨ ${t("coach.button")}`}
          </button>
        </div>
        {planError && <p className="text-xs text-danger">{t("common.error")}: {planError}</p>}
        {plan && (
          <div className="border border-hairline bg-grid/40 p-3 text-sm">
            <p className="mb-2 text-xs text-muted">{t("coach.basedOn").replace("{n}", String(plan.call_count))}</p>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {plan.focus.map((f) => (
                <span key={f} className="badge badge-info">{f}</span>
              ))}
            </div>
            <p className="whitespace-pre-wrap leading-relaxed text-ink">{plan.plan}</p>
            {plan.weak_criteria.length > 0 && (
              <p className="mt-2 text-xs text-ink2">
                {t("coach.weak")}: {plan.weak_criteria.map((w) => `${w.name} (${w.avg})`).join(", ")}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <TrendChart data={agent.trend} title={t("chart.dailyAvg")} />
        <CriteriaBars items={agent.criteria} title={t("call.criteriaBreakdown")} />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink2">{t("agents.recentCalls")}</h2>
          
        </div>
        <CallTable calls={agent.recent_calls} />
      </div>
    </div>
  );
}
